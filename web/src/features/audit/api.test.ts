// F2.16.4: API-layer unit tests for audit.
//
// Strategy mirrors features/inventory/api.test.ts: stub `@/api` so
// every call resolves against a controlled `apiRequest` mock. We
// assert URL, HTTP method, query string, and the public surface —
// exactly what the wire contract guarantees. No fetch, no React,
// no QueryClient.
//
// Covers:
//   - legacy `getStoreInventoryLogs` (F2.10).
//   - unified `getStoreAudit` (F2.16).

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import {
  getAdminAudit,
  getStoreAudit,
  getStoreInventoryLogs,
} from "./api";
import * as auditApi from "./api";
import type {
  AdminAuditFilters,
  AuditListResponse,
  GetStoreInventoryLogsParams,
  StoreInventoryLogEntry,
} from "./types";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";
const ACTOR_ID = "22222222-2222-2222-2222-222222222222";

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(undefined as never);
});

// --------------------------------------------------------------------- //
// getStoreInventoryLogs — wire contract (F2.10, unchanged)
// --------------------------------------------------------------------- //

describe("getStoreInventoryLogs", () => {
  it("calls GET /stores/{store_id}/inventory/logs with no query when limit omitted", async () => {
    await getStoreInventoryLogs({ storeId: STORE_ID });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe(`/stores/${STORE_ID}/inventory/logs`);
    expect(path).not.toMatch(/\?/);
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("appends ?limit=N when limit is provided", async () => {
    await getStoreInventoryLogs({ storeId: STORE_ID, limit: 50 });

    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/inventory/logs?limit=50`);
    expect(options?.method).toBe("GET");
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getStoreInventoryLogs(
      { storeId: STORE_ID, limit: 25 },
      controller.signal,
    );

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("URL-encodes the storeId path segment", async () => {
    await getStoreInventoryLogs({ storeId: "store with space" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/stores/store%20with%20space/inventory/logs");
  });

  it("returns the InventoryLogEntry array from apiRequest unchanged", async () => {
    const response: StoreInventoryLogEntry[] = [
      {
        id: "log-1",
        inventory_item_id: "item-1",
        store_id: STORE_ID,
        variant_id: "variant-1",
        performed_by_user_id: "user-1",
        movement_type: "receipt",
        quantity_delta: 10,
        quantity_after: 10,
        reason: null,
        reference_type: null,
        reference_id: null,
        created_at: "2026-05-04T08:30:00Z",
      },
    ];
    vi.mocked(apiRequest).mockResolvedValueOnce(response as never);

    const result = await getStoreInventoryLogs({ storeId: STORE_ID });
    expect(result).toEqual(response);
    expect(result).toBe(response);
  });

  it("propagates errors from apiRequest unchanged (no try/catch in feature layer)", async () => {
    const boom = new Error("boom");
    vi.mocked(apiRequest).mockRejectedValueOnce(boom);

    await expect(
      getStoreInventoryLogs({ storeId: STORE_ID }),
    ).rejects.toBe(boom);
  });
});

// --------------------------------------------------------------------- //
// getStoreInventoryLogs — unsupported filters guard (F2.10)
// --------------------------------------------------------------------- //

describe("getStoreInventoryLogs — unsupported filters", () => {
  it("type signature exposes ONLY storeId and limit", () => {
    type AllowedKeys = "storeId" | "limit";
    type ParamsKeys = keyof GetStoreInventoryLogsParams;
    const _forwards: AllowedKeys = "storeId" as ParamsKeys;
    const _backwards: ParamsKeys = "limit" as AllowedKeys;
    void _forwards;
    void _backwards;
  });

  it("does not include unsupported filter keys in the request URL even if cast in", async () => {
    const polluted = {
      storeId: STORE_ID,
      limit: 5,
      user_id: "u1",
      event_type: "receipt",
      entity_type: "inventory",
      created_from: "2026-01-01",
      created_to: "2026-02-01",
      offset: 0,
      total: 100,
    } as unknown as GetStoreInventoryLogsParams;

    await getStoreInventoryLogs(polluted);

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/inventory/logs?limit=5`);
    for (const key of [
      "user_id",
      "event_type",
      "entity_type",
      "created_from",
      "created_to",
      "offset",
      "total",
    ]) {
      expect(path).not.toMatch(new RegExp(key));
    }
  });
});

// --------------------------------------------------------------------- //
// getStoreAudit — wire contract (F2.16)
// --------------------------------------------------------------------- //

describe("getStoreAudit", () => {
  it("calls GET /stores/{storeId}/audit with no query when filters omitted", async () => {
    await getStoreAudit(STORE_ID);

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/audit`);
    expect(path).not.toMatch(/\?/);
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("URL-encodes the storeId path segment", async () => {
    await getStoreAudit("store with space");
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/stores/store%20with%20space/audit");
  });

  it("serializes limit", async () => {
    await getStoreAudit(STORE_ID, { limit: 25 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/audit?limit=25`);
  });

  it("preserves an explicit offset=0", async () => {
    await getStoreAudit(STORE_ID, { offset: 0 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/audit?offset=0`);
  });

  it("serializes a non-zero offset", async () => {
    await getStoreAudit(STORE_ID, { offset: 50 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/audit?offset=50`);
  });

  it("serializes the source filter", async () => {
    await getStoreAudit(STORE_ID, { source: "order" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/audit?source=order`);
  });

  it("serializes the entity_type filter", async () => {
    await getStoreAudit(STORE_ID, { entity_type: "product" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/audit?entity_type=product`);
  });

  it("serializes a trimmed action", async () => {
    await getStoreAudit(STORE_ID, { action: "  receipt  " });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/audit?action=receipt`);
  });

  it("omits an empty action", async () => {
    await getStoreAudit(STORE_ID, { action: "" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/audit`);
  });

  it("omits a whitespace-only action", async () => {
    await getStoreAudit(STORE_ID, { action: "   " });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/audit`);
  });

  it("serializes a trimmed actor_id", async () => {
    await getStoreAudit(STORE_ID, { actor_id: `  ${ACTOR_ID}  ` });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/audit?actor_id=${ACTOR_ID}`);
  });

  it("omits an empty actor_id", async () => {
    await getStoreAudit(STORE_ID, { actor_id: "" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/audit`);
  });

  it("serializes date_from", async () => {
    await getStoreAudit(STORE_ID, {
      date_from: "2026-01-01T00:00:00+00:00",
    });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    // URLSearchParams encodes ":" → "%3A" and "+" → "%2B".
    expect(path).toBe(
      `/stores/${STORE_ID}/audit?date_from=2026-01-01T00%3A00%3A00%2B00%3A00`,
    );
  });

  it("serializes date_to", async () => {
    await getStoreAudit(STORE_ID, {
      date_to: "2026-12-31T23:59:59+00:00",
    });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/stores/${STORE_ID}/audit?date_to=2026-12-31T23%3A59%3A59%2B00%3A00`,
    );
  });

  it("omits empty date_from and date_to", async () => {
    await getStoreAudit(STORE_ID, { date_from: "  ", date_to: "" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/audit`);
  });

  it("serializes combined filters", async () => {
    await getStoreAudit(STORE_ID, {
      limit: 25,
      offset: 0,
      source: "inventory",
      entity_type: "inventory_item",
      action: "receipt",
      actor_id: ACTOR_ID,
      date_from: "2026-01-01T00:00:00+00:00",
      date_to: "2026-02-01T00:00:00+00:00",
    });
    const [path] = vi.mocked(apiRequest).mock.calls[0];

    expect(path?.startsWith(`/stores/${STORE_ID}/audit?`)).toBe(true);
    const qs = new URL(`http://x${path}`).searchParams;
    expect(qs.get("limit")).toBe("25");
    expect(qs.get("offset")).toBe("0");
    expect(qs.get("source")).toBe("inventory");
    expect(qs.get("entity_type")).toBe("inventory_item");
    expect(qs.get("action")).toBe("receipt");
    expect(qs.get("actor_id")).toBe(ACTOR_ID);
    expect(qs.get("date_from")).toBe("2026-01-01T00:00:00+00:00");
    expect(qs.get("date_to")).toBe("2026-02-01T00:00:00+00:00");
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getStoreAudit(STORE_ID, { limit: 10 }, controller.signal);
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("does not call the legacy /inventory/logs endpoint", async () => {
    await getStoreAudit(STORE_ID);
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).not.toMatch(/inventory\/logs/);
  });

  it("returns the AuditListResponse envelope unchanged", async () => {
    const response: AuditListResponse = {
      items: [
        {
          id: "evt-1",
          source: "inventory",
          store_id: STORE_ID,
          actor_id: ACTOR_ID,
          action: "receipt",
          entity_type: "inventory_item",
          entity_id: "item-1",
          summary: "Inventory receipt: +10 units (after 10)",
          metadata: {
            variant_id: "var-1",
            quantity_delta: 10,
            quantity_after: 10,
            reason: null,
            reference_type: null,
            reference_id: null,
          },
          created_at: "2026-05-04T08:30:00Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    };
    vi.mocked(apiRequest).mockResolvedValueOnce(response as never);

    const result = await getStoreAudit(STORE_ID);
    expect(result).toEqual(response);
    expect(result).toBe(response);
  });

  it("propagates errors from apiRequest unchanged", async () => {
    const boom = new Error("boom-audit");
    vi.mocked(apiRequest).mockRejectedValueOnce(boom);
    await expect(getStoreAudit(STORE_ID)).rejects.toBe(boom);
  });
});

// --------------------------------------------------------------------- //
// F2.18.2B: getAdminAudit — admin global audit feed
// --------------------------------------------------------------------- //

describe("getAdminAudit", () => {
  it("calls GET /admin/audit with no query when filters are empty", async () => {
    await getAdminAudit();
    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/audit");
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("serialises limit and offset (offset=0 preserved)", async () => {
    await getAdminAudit({ limit: 25, offset: 0 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/audit?limit=25&offset=0");
  });

  it("serialises source and entity_type", async () => {
    await getAdminAudit({
      source: "inventory",
      entity_type: "inventory_item",
    });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      "/admin/audit?source=inventory&entity_type=inventory_item",
    );
  });

  it("serialises store_id when set", async () => {
    await getAdminAudit({ store_id: STORE_ID });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/admin/audit?store_id=${STORE_ID}`);
  });

  it("drops empty store_id (whitespace collapses to no filter)", async () => {
    await getAdminAudit({ store_id: "   " });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/audit");
  });

  it("serialises action, actor_id, date_from, date_to with trimming", async () => {
    await getAdminAudit({
      action: "  receipt  ",
      actor_id: `  ${ACTOR_ID}  `,
      date_from: " 2026-01-01T00:00:00Z ",
      date_to: " 2026-12-31T23:59:59Z ",
    });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/admin/audit?action=receipt&actor_id=${ACTOR_ID}` +
        `&date_from=${encodeURIComponent("2026-01-01T00:00:00Z")}` +
        `&date_to=${encodeURIComponent("2026-12-31T23:59:59Z")}`,
    );
  });

  it("drops empty / whitespace-only string filters", async () => {
    await getAdminAudit({
      store_id: "",
      action: "",
      actor_id: "   ",
      date_from: "",
      date_to: "  ",
    });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/audit");
  });

  it("combines every filter into a single query string", async () => {
    const filters: AdminAuditFilters = {
      limit: 10,
      offset: 5,
      store_id: STORE_ID,
      source: "order",
      entity_type: "order",
      action: "order_canceled",
      actor_id: ACTOR_ID,
      date_from: "2026-05-01T00:00:00Z",
      date_to: "2026-05-31T23:59:59Z",
    };
    await getAdminAudit(filters);
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/admin/audit?limit=10&offset=5&source=order&entity_type=order` +
        `&store_id=${STORE_ID}&action=order_canceled&actor_id=${ACTOR_ID}` +
        `&date_from=${encodeURIComponent("2026-05-01T00:00:00Z")}` +
        `&date_to=${encodeURIComponent("2026-05-31T23:59:59Z")}`,
    );
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const ctrl = new AbortController();
    await getAdminAudit({ limit: 1 }, ctrl.signal);
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(ctrl.signal);
  });

  it("returns the AuditListResponse envelope from apiRequest unchanged", async () => {
    const response: AuditListResponse = {
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    };
    vi.mocked(apiRequest).mockResolvedValueOnce(response as never);
    const result = await getAdminAudit();
    expect(result).toBe(response);
  });

  it("propagates errors from apiRequest unchanged (no try/catch)", async () => {
    const boom = new Error("boom-from-api");
    vi.mocked(apiRequest).mockRejectedValueOnce(boom);
    await expect(getAdminAudit()).rejects.toBe(boom);
  });

  it("never hits the store-scoped path (admin feed has its own URL)", async () => {
    await getAdminAudit({ store_id: STORE_ID });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).not.toContain("/stores/");
    expect(path.startsWith("/admin/audit")).toBe(true);
  });
});

// --------------------------------------------------------------------- //
// Public surface — guard against accidental over-build
// --------------------------------------------------------------------- //

describe("audit api public surface", () => {
  it("exports getStoreInventoryLogs, getStoreAudit and getAdminAudit", () => {
    expect(Object.keys(auditApi).sort()).toEqual(
      ["getAdminAudit", "getStoreAudit", "getStoreInventoryLogs"].sort(),
    );
  });

  it.each([
    "getAuditEvents",
    "getGlobalAuditFeed",
    "getActivityFeed",
    "getUserActivity",
    "getOrderAuditLogs",
    "getInventoryItemLogs",
    "getProductComplianceAudit",
    "listAuditEvents",
  ] as const)(
    "does not export `%s` (no matching backend endpoint or already wrapped elsewhere)",
    (name) => {
      expect(auditApi).not.toHaveProperty(name);
    },
  );
});
