// F2.24.C7: API-layer unit tests for admin store applications.
//
// Strategy mirrors features/stores/api.test.ts: stub `@/api` so every
// call resolves against a controlled `apiRequest` mock. We assert URL,
// HTTP method and body payload — exactly what the wire contract
// guarantees. No fetch, no React, no QueryClient, no Supabase.

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import {
  approveStoreApplication,
  getStoreApplication,
  listStoreApplications,
  rejectStoreApplication,
} from "./api";
import * as applicationsApi from "./api";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const APP_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(undefined as never);
});

// --------------------------------------------------------------------- //
// listStoreApplications  (test 1, 2)
// --------------------------------------------------------------------- //

describe("listStoreApplications", () => {
  it("calls GET /admin/store-applications with no query string when empty", async () => {
    await listStoreApplications();
    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/store-applications");
    expect(options?.method ?? "GET").toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("serialises status/limit/offset/q in stable order", async () => {
    await listStoreApplications({
      limit: 10,
      offset: 20,
      status: "pending_review",
      q: "acme",
    });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      "/admin/store-applications?limit=10&offset=20&status=pending_review&q=acme",
    );
  });

  it("serialises status on its own", async () => {
    await listStoreApplications({ status: "approved" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/store-applications?status=approved");
  });

  it("drops empty q (undefined-equivalent at the wire)", async () => {
    await listStoreApplications({ q: "" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/store-applications");
  });

  it("forwards the AbortSignal", async () => {
    const ctrl = new AbortController();
    await listStoreApplications({ limit: 1 }, ctrl.signal);
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(ctrl.signal);
  });
});

// --------------------------------------------------------------------- //
// getStoreApplication  (test 3)
// --------------------------------------------------------------------- //

describe("getStoreApplication", () => {
  it("calls GET /admin/store-applications/{id}", async () => {
    await getStoreApplication(APP_ID);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/admin/store-applications/${APP_ID}`);
    expect(options?.method ?? "GET").toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("encodes the application id segment", async () => {
    await getStoreApplication("with space");
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/admin/store-applications/${encodeURIComponent("with space")}`,
    );
  });
});

// --------------------------------------------------------------------- //
// approveStoreApplication  (test 4)
// --------------------------------------------------------------------- //

describe("approveStoreApplication", () => {
  it("calls POST /admin/store-applications/{id}/approve with NO body", async () => {
    await approveStoreApplication({ applicationId: APP_ID });
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/admin/store-applications/${APP_ID}/approve`);
    expect(options?.method).toBe("POST");
    // No role / store / user / Auth fields — provisioning is server-owned.
    expect(options?.body).toBeUndefined();
  });

  it("forwards the AbortSignal", async () => {
    const ctrl = new AbortController();
    await approveStoreApplication({ applicationId: APP_ID }, ctrl.signal);
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(ctrl.signal);
  });
});

// --------------------------------------------------------------------- //
// rejectStoreApplication  (test 5)
// --------------------------------------------------------------------- //

describe("rejectStoreApplication", () => {
  it("calls POST /admin/store-applications/{id}/reject with ONLY rejection_reason", async () => {
    await rejectStoreApplication({
      applicationId: APP_ID,
      body: { rejection_reason: "Incomplete documentation" },
    });
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/admin/store-applications/${APP_ID}/reject`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual({
      rejection_reason: "Incomplete documentation",
    });
    // Exactly one key — no reviewer / store / user / role smuggling.
    expect(Object.keys(options?.body as Record<string, unknown>)).toEqual([
      "rejection_reason",
    ]);
  });

  it("forwards the AbortSignal", async () => {
    const ctrl = new AbortController();
    await rejectStoreApplication(
      { applicationId: APP_ID, body: { rejection_reason: "x" } },
      ctrl.signal,
    );
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(ctrl.signal);
  });
});

// --------------------------------------------------------------------- //
// Boundary: no Supabase, bounded public surface  (test 6)
// --------------------------------------------------------------------- //

describe("admin store-applications api — boundary", () => {
  it("does not import or use the Supabase client", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "api.ts");
    const source = fs.readFileSync(here, "utf-8");
    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/supabase/i);
    expect(code).not.toMatch(/\.from\(/);
    expect(code).not.toMatch(/\.rpc\(/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
  });

  it("exports exactly the four contract functions", () => {
    const exported = Object.keys(applicationsApi).sort();
    expect(exported).toEqual(
      [
        "approveStoreApplication",
        "getStoreApplication",
        "listStoreApplications",
        "rejectStoreApplication",
      ].sort(),
    );
  });
});
