// F2.18.2A: API-layer unit tests for admin stores.
//
// Strategy mirrors features/users/api.test.ts: stub `@/api` so every
// call to the stores API resolves against a controlled `apiRequest`
// mock. We assert URL, HTTP method and body payload — exactly what the
// wire contract guarantees. No fetch, no React, no QueryClient.
//
// `getStore` and `updateStore` are re-exported from
// `@/features/store/api`; tests for those calls already live under
// the singular feature. Here we only confirm they are surfaced from
// the admin barrel so the public-surface test catches accidental
// removal.

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import {
  createStore,
  deactivateStore,
  listStores,
  reactivateStore,
} from "./api";
import * as storesApi from "./api";
import type {
  StoreCreateRequest,
  StoreListResponse,
  StoreProfile,
} from "./types";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const STORE_ID = "33333333-3333-3333-3333-333333333333";
const OTHER_STORE_ID = "44444444-4444-4444-4444-444444444444";

const SAMPLE_STORE: StoreProfile = {
  id: STORE_ID,
  name: "Sample Store",
  code: "smpl",
  is_active: true,
  timezone: "America/New_York",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(undefined as never);
});

// --------------------------------------------------------------------- //
// listStores
// --------------------------------------------------------------------- //

describe("listStores", () => {
  it("calls GET /stores with no query string when filters are empty", async () => {
    await listStores();
    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/stores");
    expect(options?.method ?? "GET").toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("serialises limit and offset", async () => {
    await listStores({ limit: 25, offset: 50 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/stores?limit=25&offset=50");
  });

  it("serialises is_active=true", async () => {
    await listStores({ is_active: true });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/stores?is_active=true");
  });

  it("serialises is_active=false (an explicit false is meaningful)", async () => {
    await listStores({ is_active: false });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/stores?is_active=false");
  });

  it("serialises q", async () => {
    await listStores({ q: "warehouse" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/stores?q=warehouse");
  });

  it("drops empty q (undefined-equivalent at the wire)", async () => {
    await listStores({ q: "" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/stores");
  });

  it("combines all filters in stable insertion order", async () => {
    await listStores({
      limit: 10,
      offset: 5,
      is_active: false,
      q: "n",
    });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/stores?limit=10&offset=5&is_active=false&q=n");
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const ctrl = new AbortController();
    await listStores({ limit: 1 }, ctrl.signal);
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(ctrl.signal);
  });

  it("returns the StoreListResponse from apiRequest unchanged", async () => {
    const response: StoreListResponse = {
      items: [SAMPLE_STORE],
      total: 1,
      limit: 25,
      offset: 0,
    };
    vi.mocked(apiRequest).mockResolvedValueOnce(response as never);
    const result = await listStores();
    expect(result).toEqual(response);
    expect(result).toBe(response);
  });

  it("propagates errors from apiRequest unchanged (no try/catch)", async () => {
    const boom = new Error("boom");
    vi.mocked(apiRequest).mockRejectedValueOnce(boom);
    await expect(listStores()).rejects.toBe(boom);
  });
});

// --------------------------------------------------------------------- //
// createStore
// --------------------------------------------------------------------- //

describe("createStore", () => {
  it("calls POST /stores with the request body verbatim", async () => {
    const body: StoreCreateRequest = {
      name: "Brooklyn Hub",
      code: "bk-001",
      timezone: "America/New_York",
    };
    await createStore({ body });
    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/stores");
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual(body);
  });

  it("omits timezone when not provided (backend default applies)", async () => {
    const body: StoreCreateRequest = { name: "Queens Hub", code: "qns-001" };
    await createStore({ body });
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    const sent = options?.body as Record<string, unknown>;
    expect("timezone" in sent).toBe(false);
    expect(Object.keys(sent).sort()).toEqual(["code", "name"]);
  });

  it("forwards the AbortSignal", async () => {
    const ctrl = new AbortController();
    await createStore(
      { body: { name: "x", code: "x" } },
      ctrl.signal,
    );
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(ctrl.signal);
  });

  it("returns the StoreProfile response unchanged", async () => {
    vi.mocked(apiRequest).mockResolvedValueOnce(SAMPLE_STORE as never);
    const result = await createStore({
      body: { name: "x", code: "x" },
    });
    expect(result).toBe(SAMPLE_STORE);
  });

  it("propagates errors from apiRequest unchanged", async () => {
    const boom = new Error("boom");
    vi.mocked(apiRequest).mockRejectedValueOnce(boom);
    await expect(
      createStore({ body: { name: "x", code: "x" } }),
    ).rejects.toBe(boom);
  });
});

// --------------------------------------------------------------------- //
// deactivateStore / reactivateStore
// --------------------------------------------------------------------- //

describe("deactivateStore", () => {
  it("calls POST /stores/{id}/deactivate without a body", async () => {
    await deactivateStore({ storeId: STORE_ID });
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/deactivate`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toBeUndefined();
  });

  it("encodes the store id segment", async () => {
    await deactivateStore({ storeId: "with space" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${encodeURIComponent("with space")}/deactivate`);
  });

  it("forwards the AbortSignal", async () => {
    const ctrl = new AbortController();
    await deactivateStore({ storeId: STORE_ID }, ctrl.signal);
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(ctrl.signal);
  });
});

describe("reactivateStore", () => {
  it("calls POST /stores/{id}/reactivate without a body", async () => {
    await reactivateStore({ storeId: STORE_ID });
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/reactivate`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toBeUndefined();
  });

  it("encodes the store id segment", async () => {
    await reactivateStore({ storeId: "with/slash" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/stores/${encodeURIComponent("with/slash")}/reactivate`,
    );
  });

  it("uses a distinct path from deactivate for the same store", async () => {
    await deactivateStore({ storeId: OTHER_STORE_ID });
    const deactivatePath = vi.mocked(apiRequest).mock.calls[0][0];
    vi.mocked(apiRequest).mockClear();
    await reactivateStore({ storeId: OTHER_STORE_ID });
    const reactivatePath = vi.mocked(apiRequest).mock.calls[0][0];
    expect(deactivatePath).not.toBe(reactivatePath);
  });
});

// --------------------------------------------------------------------- //
// Public surface — guard against accidental over-build
// --------------------------------------------------------------------- //

describe("stores api public surface", () => {
  it("exports the F2.18.2A admin stores surface (list + create + lifecycle + re-exported read/update)", () => {
    const exported = Object.keys(storesApi).sort();
    expect(exported).toEqual(
      [
        "createStore",
        "deactivateStore",
        "getStore",
        "listStores",
        "reactivateStore",
        "updateStore",
      ].sort(),
    );
  });

  it("does not export functions for endpoints the backend has not implemented", () => {
    // The backend deliberately does NOT have a `/admin/stores`
    // namespace, a hard-delete endpoint, or anything else listed here.
    // Adding them would either 404 at runtime or silently invent a
    // contract.
    const forbidden = [
      "deleteStore",
      "hardDeleteStore",
      "listAdminStores",
      "createAdminStore",
      "adminGetStore",
      "adminUpdateStore",
      "inviteStoreOwner",
    ];
    for (const name of forbidden) {
      expect(storesApi).not.toHaveProperty(name);
    }
  });
});
