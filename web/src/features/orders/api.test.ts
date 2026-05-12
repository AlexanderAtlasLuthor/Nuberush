// F2.7.0 subfase 4: API-layer unit tests for orders.
//
// Strategy: stub `@/api` so every call to the orders API resolves
// against a controlled `apiRequest` mock. We assert URL, HTTP method,
// query string and body payload — exactly what the wire contract
// guarantees, no React, no QueryClient, no transport.

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import {
  cancelOrder,
  createOrder,
  getAdminOrders,
  getOrder,
  getOrderAuditLogs,
  getOrdersList,
  returnOrder,
  transitionOrderStatus,
} from "./api";
import * as ordersApi from "./api";
import type { AdminOrdersFilters, OrdersListResponse } from "./types";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";
const ORDER_ID = "22222222-2222-2222-2222-222222222222";

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(undefined as never);
});

// --------------------------------------------------------------------- //
// getOrdersList
// --------------------------------------------------------------------- //

describe("getOrdersList", () => {
  it("calls GET /stores/{store_id}/orders with pagination params", async () => {
    await getOrdersList({ storeId: STORE_ID, limit: 20, offset: 0 });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/orders?limit=20&offset=0`);
    expect(options?.method).toBeUndefined();
    expect(options?.body).toBeUndefined();
  });

  it("appends status filter when provided", async () => {
    await getOrdersList({
      storeId: STORE_ID,
      limit: 20,
      offset: 40,
      status: "pending",
    });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/stores/${STORE_ID}/orders?limit=20&offset=40&status=pending`,
    );
  });

  it("appends created_from and created_to when provided", async () => {
    await getOrdersList({
      storeId: STORE_ID,
      limit: 20,
      offset: 0,
      created_from: "2026-01-01T00:00:00Z",
      created_to: "2026-04-29T23:59:59Z",
    });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toContain("limit=20");
    expect(path).toContain("offset=0");
    expect(path).toContain("created_from=2026-01-01T00%3A00%3A00Z");
    expect(path).toContain("created_to=2026-04-29T23%3A59%3A59Z");
  });

  it("composes status + created_from + created_to in the same query string", async () => {
    await getOrdersList({
      storeId: STORE_ID,
      limit: 50,
      offset: 100,
      status: "delivered",
      created_from: "2026-01-01T00:00:00Z",
      created_to: "2026-04-29T23:59:59Z",
    });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toMatch(/^\/stores\/[^/]+\/orders\?/);
    expect(path).toContain("limit=50");
    expect(path).toContain("offset=100");
    expect(path).toContain("status=delivered");
    expect(path).toContain("created_from=");
    expect(path).toContain("created_to=");
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getOrdersList(
      { storeId: STORE_ID, limit: 20, offset: 0 },
      controller.signal,
    );
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });
});

// --------------------------------------------------------------------- //
// getOrder
// --------------------------------------------------------------------- //

describe("getOrder", () => {
  it("calls GET /orders/{order_id} (item-scoped, NOT store-scoped)", async () => {
    await getOrder({ orderId: ORDER_ID });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/orders/${ORDER_ID}`);
    expect(path).not.toMatch(/\/stores\//);
    expect(options?.method).toBeUndefined();
    expect(options?.body).toBeUndefined();
  });
});

// --------------------------------------------------------------------- //
// getOrderAuditLogs
// --------------------------------------------------------------------- //

describe("getOrderAuditLogs", () => {
  it("calls GET /orders/{order_id}/audit-logs (kebab-case in URL)", async () => {
    await getOrderAuditLogs({ orderId: ORDER_ID });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/orders/${ORDER_ID}/audit-logs`);
    expect(options?.method).toBeUndefined();
  });
});

// --------------------------------------------------------------------- //
// createOrder
// --------------------------------------------------------------------- //

describe("createOrder", () => {
  it("calls POST /stores/{store_id}/orders with the request body", async () => {
    const body = {
      idempotency_key: "key-123",
      items: [
        {
          variant_id: "33333333-3333-3333-3333-333333333333",
          quantity: 2,
        },
      ],
      notes: "rush order",
    };
    await createOrder({ storeId: STORE_ID, body });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/orders`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual(body);
  });

  it("forwards multi-line bodies verbatim (no transformation)", async () => {
    const body = {
      idempotency_key: "key-multi",
      items: [
        { variant_id: "aaa", quantity: 1 },
        { variant_id: "bbb", quantity: 5 },
        { variant_id: "ccc", quantity: 12 },
      ],
    };
    await createOrder({ storeId: STORE_ID, body });

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect((options?.body as typeof body).items).toHaveLength(3);
    expect(options?.body).toEqual(body);
  });
});

// --------------------------------------------------------------------- //
// transitionOrderStatus
// --------------------------------------------------------------------- //

describe("transitionOrderStatus", () => {
  it("calls PATCH /orders/{order_id}/status with new_status and optional reason", async () => {
    await transitionOrderStatus({
      orderId: ORDER_ID,
      body: { new_status: "accepted", reason: "operator approval" },
    });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/orders/${ORDER_ID}/status`);
    expect(options?.method).toBe("PATCH");
    expect(options?.body).toEqual({
      new_status: "accepted",
      reason: "operator approval",
    });
  });

  it("forwards a body without reason verbatim", async () => {
    await transitionOrderStatus({
      orderId: ORDER_ID,
      body: { new_status: "preparing" },
    });
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.body).toEqual({ new_status: "preparing" });
  });
});

// --------------------------------------------------------------------- //
// cancelOrder
// --------------------------------------------------------------------- //

describe("cancelOrder", () => {
  it("calls POST /orders/{order_id}/cancel with reason", async () => {
    await cancelOrder({
      orderId: ORDER_ID,
      body: { reason: "customer changed mind" },
    });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/orders/${ORDER_ID}/cancel`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual({ reason: "customer changed mind" });
  });
});

// --------------------------------------------------------------------- //
// returnOrder
// --------------------------------------------------------------------- //

describe("returnOrder", () => {
  it("calls POST /orders/{order_id}/return with reason", async () => {
    await returnOrder({
      orderId: ORDER_ID,
      body: { reason: "defective unit" },
    });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/orders/${ORDER_ID}/return`);
    expect(options?.method).toBe("POST");
    expect(options?.body).toEqual({ reason: "defective unit" });
  });
});

// --------------------------------------------------------------------- //
// F2.18.2C: getAdminOrders — admin global orders feed
// --------------------------------------------------------------------- //

describe("getAdminOrders", () => {
  it("calls GET /admin/orders with no query when filters are empty", async () => {
    await getAdminOrders();
    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/orders");
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("serialises limit and offset (offset=0 preserved)", async () => {
    await getAdminOrders({ limit: 25, offset: 0 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/orders?limit=25&offset=0");
  });

  it("serialises status enum verbatim", async () => {
    await getAdminOrders({ status: "pending" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/orders?status=pending");
  });

  it("serialises store_id with trimming", async () => {
    await getAdminOrders({ store_id: `  ${STORE_ID}  ` });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/admin/orders?store_id=${STORE_ID}`);
  });

  it("serialises date_from and date_to with trimming", async () => {
    await getAdminOrders({
      date_from: " 2026-01-01T00:00:00Z ",
      date_to: " 2026-12-31T23:59:59Z ",
    });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/admin/orders?date_from=${encodeURIComponent("2026-01-01T00:00:00Z")}` +
        `&date_to=${encodeURIComponent("2026-12-31T23:59:59Z")}`,
    );
  });

  it("drops empty / whitespace-only string filters", async () => {
    await getAdminOrders({
      store_id: "",
      date_from: "   ",
      date_to: "",
    });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/orders");
  });

  it("combines every supported filter into a single query string", async () => {
    const filters: AdminOrdersFilters = {
      limit: 10,
      offset: 5,
      status: "delivered",
      store_id: STORE_ID,
      date_from: "2026-05-01T00:00:00Z",
      date_to: "2026-05-31T23:59:59Z",
    };
    await getAdminOrders(filters);
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/admin/orders?limit=10&offset=5&status=delivered` +
        `&store_id=${STORE_ID}` +
        `&date_from=${encodeURIComponent("2026-05-01T00:00:00Z")}` +
        `&date_to=${encodeURIComponent("2026-05-31T23:59:59Z")}`,
    );
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const ctrl = new AbortController();
    await getAdminOrders({ limit: 1 }, ctrl.signal);
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(ctrl.signal);
  });

  it("returns the OrdersListResponse from apiRequest unchanged", async () => {
    const response: OrdersListResponse = {
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    };
    vi.mocked(apiRequest).mockResolvedValueOnce(response as never);
    const result = await getAdminOrders();
    expect(result).toBe(response);
  });

  it("propagates errors from apiRequest unchanged (no try/catch)", async () => {
    const boom = new Error("boom-from-api");
    vi.mocked(apiRequest).mockRejectedValueOnce(boom);
    await expect(getAdminOrders()).rejects.toBe(boom);
  });

  it("never hits the store-scoped path (admin feed has its own URL)", async () => {
    await getAdminOrders({ store_id: STORE_ID });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).not.toContain("/stores/");
    expect(path.startsWith("/admin/orders")).toBe(true);
  });

  it("does not declare or serialize q (F2.18.1B non-shipment)", async () => {
    // TypeScript would already reject `{ q: "foo" }` against
    // AdminOrdersFilters, but lock the runtime guarantee too: if a
    // caller passes `q` via an `as any` escape, it must not be
    // serialized as a query param.
    await getAdminOrders({
      // @ts-expect-error — q is intentionally not part of AdminOrdersFilters
      q: "warehouse",
      limit: 10,
    });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).not.toMatch(/\bq=/);
    expect(path).toBe("/admin/orders?limit=10");
  });
});

// --------------------------------------------------------------------- //
// Public surface — admin endpoint exists, q is not shipped
// --------------------------------------------------------------------- //

describe("orders api public surface", () => {
  it("exposes getAdminOrders as part of the F2.18.2C surface", () => {
    expect(ordersApi).toHaveProperty("getAdminOrders");
    expect(typeof ordersApi.getAdminOrders).toBe("function");
  });

  it.each([
    "searchAdminOrders",
    "queryAdminOrders",
    "getAdminOrdersWithQ",
  ] as const)(
    "does not export `%s` (q is not part of the F2.18.1B admin orders surface)",
    (name) => {
      expect(ordersApi).not.toHaveProperty(name);
    },
  );
});
