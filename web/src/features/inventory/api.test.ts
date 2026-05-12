// F2.6.0 subfase 4: API-layer unit tests.
//
// Strategy: stub `@/api` so every call to the inventory API resolves
// against a controlled `apiRequest` mock. We assert the URL, the HTTP
// method, and the body payload — i.e. exactly what the wire contract
// guarantees and nothing else (no fetch, no React, no QueryClient).

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import {
  adjustStock,
  damageStock,
  getAdminInventory,
  getInventoryItem,
  getInventoryItemLogs,
  getInventoryList,
  receiveStock,
  updateInventoryStatus,
  updateInventoryThreshold,
} from "./api";
import type {
  AdminInventoryFilters,
  InventoryListResponse,
} from "./types";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";
const ITEM_ID = "22222222-2222-2222-2222-222222222222";

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(undefined as never);
});

// --------------------------------------------------------------------- //
// getInventoryList
// --------------------------------------------------------------------- //

describe("getInventoryList", () => {
  it("calls GET /stores/{store_id}/inventory with limit & offset", async () => {
    await getInventoryList({ storeId: STORE_ID, limit: 25, offset: 50 });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/stores/${STORE_ID}/inventory?limit=25&offset=50`);
    // No method passed → defaults to GET in apiRequest.
    expect(options?.method).toBeUndefined();
    expect(options?.body).toBeUndefined();
  });

  it("appends low_stock_only when provided", async () => {
    await getInventoryList({
      storeId: STORE_ID,
      limit: 100,
      offset: 0,
      low_stock_only: true,
    });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/stores/${STORE_ID}/inventory?limit=100&offset=0&low_stock_only=true`,
    );
  });

  it("omits low_stock_only when undefined (no empty query param)", async () => {
    await getInventoryList({ storeId: STORE_ID, limit: 10, offset: 0 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).not.toMatch(/low_stock_only/);
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getInventoryList(
      { storeId: STORE_ID, limit: 10, offset: 0 },
      controller.signal,
    );
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });
});

// --------------------------------------------------------------------- //
// getInventoryItem
// --------------------------------------------------------------------- //

describe("getInventoryItem", () => {
  it("calls GET /inventory/{item_id} (item-scoped, NOT store-scoped)", async () => {
    await getInventoryItem({ inventoryItemId: ITEM_ID });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/inventory/${ITEM_ID}`);
    expect(path).not.toMatch(/\/stores\//);
    expect(options?.method).toBeUndefined();
    expect(options?.body).toBeUndefined();
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getInventoryItem({ inventoryItemId: ITEM_ID }, controller.signal);
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });
});

// --------------------------------------------------------------------- //
// receiveStock
// --------------------------------------------------------------------- //

describe("receiveStock", () => {
  it("calls POST /inventory/{item_id}/receive with the request body", async () => {
    await receiveStock({
      inventoryItemId: ITEM_ID,
      body: { quantity: 5, reason: "supplier delivery" },
    });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/inventory/${ITEM_ID}/receive`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual({
      quantity: 5,
      reason: "supplier delivery",
    });
  });

  it("passes through optional reference fields verbatim", async () => {
    await receiveStock({
      inventoryItemId: ITEM_ID,
      body: {
        quantity: 12,
        reference_type: "purchase_order",
        reference_id: "33333333-3333-3333-3333-333333333333",
      },
    });

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.body).toEqual({
      quantity: 12,
      reference_type: "purchase_order",
      reference_id: "33333333-3333-3333-3333-333333333333",
    });
  });
});

// --------------------------------------------------------------------- //
// adjustStock
// --------------------------------------------------------------------- //

describe("adjustStock", () => {
  it("calls POST /inventory/{item_id}/adjust with delta and reason", async () => {
    await adjustStock({
      inventoryItemId: ITEM_ID,
      body: { delta: -3, reason: "physical recount" },
    });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/inventory/${ITEM_ID}/adjust`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual({ delta: -3, reason: "physical recount" });
  });

  it("does not transform a positive delta", async () => {
    await adjustStock({
      inventoryItemId: ITEM_ID,
      body: { delta: 7, reason: "found extra units" },
    });
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect((options?.body as { delta: number }).delta).toBe(7);
  });
});

// --------------------------------------------------------------------- //
// damageStock
// --------------------------------------------------------------------- //

describe("damageStock", () => {
  it("calls POST /inventory/{item_id}/damage with quantity and reason", async () => {
    await damageStock({
      inventoryItemId: ITEM_ID,
      body: { quantity: 2, reason: "broken item" },
    });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/inventory/${ITEM_ID}/damage`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual({ quantity: 2, reason: "broken item" });
  });
});

// --------------------------------------------------------------------- //
// updateInventoryThreshold
// --------------------------------------------------------------------- //

describe("updateInventoryThreshold", () => {
  it("calls PATCH /inventory/{item_id}/threshold with reorder_threshold", async () => {
    await updateInventoryThreshold({
      inventoryItemId: ITEM_ID,
      body: { reorder_threshold: 12 },
    });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/inventory/${ITEM_ID}/threshold`);
    expect(options?.method).toBe("PATCH");
    expect(options?.body).toEqual({ reorder_threshold: 12 });
  });
});

// --------------------------------------------------------------------- //
// updateInventoryStatus
// --------------------------------------------------------------------- //

describe("getInventoryItemLogs", () => {
  it("calls GET /inventory/{item_id}/logs?limit=20 (item-scoped, no body)", async () => {
    await getInventoryItemLogs({ inventoryItemId: ITEM_ID, limit: 20 });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/inventory/${ITEM_ID}/logs?limit=20`);
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("omits the limit query param when undefined", async () => {
    await getInventoryItemLogs({ inventoryItemId: ITEM_ID });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/inventory/${ITEM_ID}/logs`);
    expect(path).not.toMatch(/limit/);
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getInventoryItemLogs(
      { inventoryItemId: ITEM_ID, limit: 5 },
      controller.signal,
    );
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });
});

describe("updateInventoryStatus", () => {
  it("calls PATCH /inventory/{item_id}/status with status and reason", async () => {
    await updateInventoryStatus({
      inventoryItemId: ITEM_ID,
      body: { status: "quarantined", reason: "FDA hold" },
    });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/inventory/${ITEM_ID}/status`);
    expect(options?.method).toBe("PATCH");
    expect(options?.body).toEqual({
      status: "quarantined",
      reason: "FDA hold",
    });
  });
});

// --------------------------------------------------------------------- //
// F2.18.2C: getAdminInventory — admin global inventory feed
// --------------------------------------------------------------------- //

const PRODUCT_ID = "33333333-3333-3333-3333-333333333333";
const VARIANT_ID = "44444444-4444-4444-4444-444444444444";

describe("getAdminInventory", () => {
  it("calls GET /admin/inventory with no query when filters are empty", async () => {
    await getAdminInventory();
    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/inventory");
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("serialises limit and offset (offset=0 preserved)", async () => {
    await getAdminInventory({ limit: 25, offset: 0 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/inventory?limit=25&offset=0");
  });

  it("serialises low_stock=true", async () => {
    await getAdminInventory({ low_stock: true });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/inventory?low_stock=true");
  });

  it("preserves explicit low_stock=false on the wire", async () => {
    await getAdminInventory({ low_stock: false });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/inventory?low_stock=false");
  });

  it("omits low_stock when undefined (backend default applies)", async () => {
    await getAdminInventory({ limit: 10 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).not.toMatch(/low_stock/);
  });

  it("serialises status enum verbatim", async () => {
    await getAdminInventory({ status: "flagged" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/inventory?status=flagged");
  });

  it("serialises store_id, q, product_id, variant_id (with trimming)", async () => {
    await getAdminInventory({
      store_id: `  ${STORE_ID}  `,
      q: "  vape  ",
      product_id: `  ${PRODUCT_ID}  `,
      variant_id: `  ${VARIANT_ID}  `,
    });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/admin/inventory?store_id=${STORE_ID}&q=vape` +
        `&product_id=${PRODUCT_ID}&variant_id=${VARIANT_ID}`,
    );
  });

  it("drops empty/whitespace string filters", async () => {
    await getAdminInventory({
      store_id: "",
      q: "   ",
      product_id: "",
      variant_id: "  ",
    });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/inventory");
  });

  it("combines every supported filter into a single query string", async () => {
    const filters: AdminInventoryFilters = {
      limit: 10,
      offset: 5,
      low_stock: true,
      status: "available",
      store_id: STORE_ID,
      q: "vape",
      product_id: PRODUCT_ID,
      variant_id: VARIANT_ID,
    };
    await getAdminInventory(filters);
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/admin/inventory?limit=10&offset=5&low_stock=true&status=available` +
        `&store_id=${STORE_ID}&q=vape` +
        `&product_id=${PRODUCT_ID}&variant_id=${VARIANT_ID}`,
    );
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const ctrl = new AbortController();
    await getAdminInventory({ limit: 1 }, ctrl.signal);
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(ctrl.signal);
  });

  it("returns the InventoryListResponse from apiRequest unchanged", async () => {
    const response: InventoryListResponse = {
      items: [],
      total: 0,
      limit: 100,
      offset: 0,
    };
    vi.mocked(apiRequest).mockResolvedValueOnce(response as never);
    const result = await getAdminInventory();
    expect(result).toBe(response);
  });

  it("propagates errors from apiRequest unchanged (no try/catch)", async () => {
    const boom = new Error("boom-from-api");
    vi.mocked(apiRequest).mockRejectedValueOnce(boom);
    await expect(getAdminInventory()).rejects.toBe(boom);
  });

  it("never hits the store-scoped path (admin feed has its own URL)", async () => {
    await getAdminInventory({ store_id: STORE_ID });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).not.toContain("/stores/");
    expect(path.startsWith("/admin/inventory")).toBe(true);
  });
});
