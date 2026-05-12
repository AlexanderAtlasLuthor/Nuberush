// F2.14.4: API-layer unit tests for the store-profile module.
//
// Strategy mirrors features/users/api.test.ts and
// features/products/api.test.ts: stub `@/api` so every call resolves
// against a controlled `apiRequest` mock. We assert URL, HTTP method
// and body payload — exactly what the wire contract guarantees. No
// fetch, no React, no QueryClient.

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import { getStore, updateStore } from "./api";
import * as storeApi from "./api";
import type { StoreProfile, StoreUpdateRequest } from "./types";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const STORE_ID = "22222222-2222-2222-2222-222222222222";

const STORE_RESPONSE: StoreProfile = {
  id: STORE_ID,
  name: "Acme HQ",
  code: "ACME-HQ",
  is_active: true,
  timezone: "America/New_York",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
};

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(undefined as never);
});

// --------------------------------------------------------------------- //
// getStore
// --------------------------------------------------------------------- //

describe("getStore", () => {
  it("calls GET /stores/{storeId} with no body", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce(STORE_RESPONSE as never);

    const result = await getStore(STORE_ID);

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}`);
    // Method defaults to GET in apiRequest when not provided; we just
    // assert no body / method / explicit overrides leaked.
    expect(options?.body).toBeUndefined();
    expect(options?.method).toBeUndefined();
    expect(result).toEqual(STORE_RESPONSE);
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    vi.mocked(apiRequest).mockResolvedValueOnce(STORE_RESPONSE as never);

    await getStore(STORE_ID, controller.signal);

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("propagates errors from apiRequest unchanged", async () => {
    const boom = new Error("boom");
    vi.mocked(apiRequest).mockRejectedValueOnce(boom);

    await expect(getStore(STORE_ID)).rejects.toBe(boom);
  });
});

// --------------------------------------------------------------------- //
// updateStore
// --------------------------------------------------------------------- //

describe("updateStore", () => {
  it("calls PATCH /stores/{storeId} with the payload verbatim", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce(STORE_RESPONSE as never);
    const payload: StoreUpdateRequest = {
      name: "New Store",
      timezone: "America/Chicago",
    };

    const result = await updateStore(STORE_ID, payload);

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}`);
    expect(options?.method).toBe("PATCH");
    expect(options?.body).toEqual(payload);
    // Snake_case wire contract — no camelCase rewriting.
    const sent = options?.body as Record<string, unknown>;
    expect(Object.keys(sent).sort()).toEqual(["name", "timezone"].sort());
    expect(result).toEqual(STORE_RESPONSE);
  });

  it("supports a partial payload (name only)", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce(STORE_RESPONSE as never);

    await updateStore(STORE_ID, { name: "Solo Name" });

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.body).toEqual({ name: "Solo Name" });
  });

  it("supports a partial payload (timezone only)", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce(STORE_RESPONSE as never);

    await updateStore(STORE_ID, { timezone: "America/Chicago" });

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.body).toEqual({ timezone: "America/Chicago" });
  });

  it("sends an empty object body when given an empty payload (server-side no-op)", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce(STORE_RESPONSE as never);

    await updateStore(STORE_ID, {});

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.body).toEqual({});
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    vi.mocked(apiRequest).mockResolvedValueOnce(STORE_RESPONSE as never);

    await updateStore(STORE_ID, { name: "x" }, controller.signal);

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("propagates errors from apiRequest unchanged", async () => {
    const boom = new Error("boom");
    vi.mocked(apiRequest).mockRejectedValueOnce(boom);

    await expect(updateStore(STORE_ID, { name: "x" })).rejects.toBe(boom);
  });
});

// --------------------------------------------------------------------- //
// Public surface — guard against accidental over-build
// --------------------------------------------------------------------- //

describe("store api public surface", () => {
  it("exports only getStore + updateStore (no list/create/delete/deactivate)", () => {
    const exported = Object.keys(storeApi).sort();
    expect(exported).toEqual(["getStore", "updateStore"]);
  });

  it("does not export functions for endpoints the backend has not implemented", () => {
    const forbidden = [
      "listStores",
      "getStores",
      "createStore",
      "deleteStore",
      "deactivateStore",
      "activateStore",
      "getStoreNotificationSettings",
      "updateStoreNotificationSettings",
      "getStorePreferences",
      "updateStorePreferences",
    ];
    for (const name of forbidden) {
      expect(storeApi).not.toHaveProperty(name);
    }
  });
});
