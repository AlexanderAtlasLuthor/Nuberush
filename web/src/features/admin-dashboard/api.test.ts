// F2.19.3: API-layer unit tests for admin dashboard.
//
// Strategy mirrors features/audit/api.test.ts: stub `@/api` so every
// call resolves against a controlled `apiRequest` mock. We assert
// URL, HTTP method, the absence of query/body, signal forwarding,
// payload pass-through, and error propagation — exactly what the
// wire contract guarantees. No fetch, no React, no QueryClient.
//
// Backend endpoint (F2.19.1):
//   GET /admin/dashboard → AdminDashboardSummary

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import { getAdminDashboard } from "./api";
import * as adminDashboardApi from "./api";
import type { AdminDashboardSummary } from "./types";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(undefined as never);
});

function emptySummary(): AdminDashboardSummary {
  return {
    stores: { total: 0, active: 0, inactive: 0 },
    users: { total: 0, active: 0 },
    inventory: { low_stock_count: 0 },
    orders: {
      open_count: 0,
      by_status: {
        pending: 0,
        accepted: 0,
        preparing: 0,
        ready: 0,
        out_for_delivery: 0,
        delivered: 0,
        canceled: 0,
        returned: 0,
      },
      recent: [],
    },
    compliance: { blocked_count: 0 },
    products: { pending_approvals_count: 0 },
    recent_audit: [],
  };
}

// --------------------------------------------------------------------- //
// Wire contract
// --------------------------------------------------------------------- //

describe("getAdminDashboard", () => {
  it("calls GET /admin/dashboard via apiRequest", async () => {
    await getAdminDashboard();

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe("/admin/dashboard");
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("does not append any query string", async () => {
    await getAdminDashboard();
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).not.toMatch(/\?/);
  });

  it("does not require a storeId argument (the endpoint has no path id)", () => {
    // Compile-time check: the function must be callable with no
    // arguments. The runtime side is already exercised by every
    // other test in this file; this assertion is mostly a guard
    // against accidental signature drift.
    const result = getAdminDashboard();
    expect(result).toBeInstanceOf(Promise);
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getAdminDashboard(controller.signal);
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("does not forward an AbortSignal when none is provided", async () => {
    await getAdminDashboard();
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBeUndefined();
  });

  it("returns the AdminDashboardSummary from apiRequest unchanged", async () => {
    const response = emptySummary();
    vi.mocked(apiRequest).mockResolvedValueOnce(response as never);

    const result = await getAdminDashboard();
    expect(result).toEqual(response);
    expect(result).toBe(response);
  });

  it("returns a populated summary verbatim (no client-side aggregation)", async () => {
    const response: AdminDashboardSummary = {
      stores: { total: 5, active: 3, inactive: 2 },
      users: { total: 12, active: 10 },
      inventory: { low_stock_count: 7 },
      orders: {
        open_count: 4,
        by_status: {
          pending: 2,
          accepted: 1,
          preparing: 1,
          ready: 0,
          out_for_delivery: 0,
          delivered: 5,
          canceled: 1,
          returned: 0,
        },
        recent: [],
      },
      compliance: { blocked_count: 2 },
      products: { pending_approvals_count: 7 },
      recent_audit: [],
    };
    vi.mocked(apiRequest).mockResolvedValueOnce(response as never);

    const result = await getAdminDashboard();
    // Strict identity — we MUST NOT clone, map, or normalize.
    expect(result).toBe(response);
    expect(result.orders.open_count).toBe(4);
    expect(result.compliance.blocked_count).toBe(2);
  });

  it("propagates errors from apiRequest unchanged (no try/catch in feature layer)", async () => {
    const boom = new Error("boom-from-admin-dashboard-api");
    vi.mocked(apiRequest).mockRejectedValueOnce(boom);

    await expect(getAdminDashboard()).rejects.toBe(boom);
  });

  it("never calls /admin/operations/alerts (operations endpoint is a different feature)", async () => {
    await getAdminDashboard();
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).not.toMatch(/\/admin\/operations/);
    expect(path).not.toMatch(/alerts/);
  });

  it("never calls a store-scoped path (admin dashboard is global)", async () => {
    await getAdminDashboard();
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).not.toMatch(/\/stores\//);
  });
});

// --------------------------------------------------------------------- //
// Public surface — guard against accidental over-build
// --------------------------------------------------------------------- //

describe("admin-dashboard api public surface", () => {
  it("exports only getAdminDashboard", () => {
    expect(Object.keys(adminDashboardApi).sort()).toEqual([
      "getAdminDashboard",
    ]);
  });

  it.each([
    "getAdminOperationsAlerts",
    "createAdminDashboard",
    "updateAdminDashboard",
    "deleteAdminDashboard",
    "patchAdminDashboard",
    "refreshAdminDashboard",
    "exportAdminDashboard",
  ] as const)("does not export `%s`", (name) => {
    expect(adminDashboardApi).not.toHaveProperty(name);
  });
});
