// F2.19.4: API-layer unit tests for admin operations alerts.
//
// Strategy mirrors features/admin-dashboard/api.test.ts and
// features/audit/api.test.ts: stub `@/api` so every call resolves
// against a controlled `apiRequest` mock. We assert URL, HTTP
// method, query string serialization, signal forwarding, payload
// pass-through, and error propagation — exactly what the wire
// contract guarantees. No fetch, no React, no QueryClient.
//
// Backend endpoint (F2.19.2):
//   GET /admin/operations/alerts → AdminOperationsAlertsListResponse

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import { getAdminOperationsAlerts } from "./api";
import * as adminOperationsApi from "./api";
import type {
  AdminOperationsAlertsFilters,
  AdminOperationsAlertsListResponse,
} from "./types";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(undefined as never);
});

function emptyResponse(): AdminOperationsAlertsListResponse {
  return { items: [], total: 0, limit: 50, offset: 0 };
}

// --------------------------------------------------------------------- //
// Wire contract — base call
// --------------------------------------------------------------------- //

describe("getAdminOperationsAlerts — wire contract", () => {
  it("calls GET /admin/operations/alerts with no query when filters omitted", async () => {
    await getAdminOperationsAlerts();

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];

    expect(path).toBe("/admin/operations/alerts");
    expect(path).not.toMatch(/\?/);
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("calls GET /admin/operations/alerts with empty filters object", async () => {
    await getAdminOperationsAlerts({});
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/operations/alerts");
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getAdminOperationsAlerts({ limit: 10 }, controller.signal);
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("omits the AbortSignal when none is provided", async () => {
    await getAdminOperationsAlerts();
    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBeUndefined();
  });

  it("returns the AdminOperationsAlertsListResponse unchanged", async () => {
    const response: AdminOperationsAlertsListResponse = {
      items: [
        {
          id: `low_stock:${STORE_ID}`,
          category: "low_stock",
          severity: "high",
          store_id: STORE_ID,
          entity_type: "inventory_item",
          entity_id: "44444444-4444-4444-4444-444444444444",
          summary: "Low stock: available 0 <= reorder threshold 0",
          created_at: "2026-05-12T08:00:00Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    };
    vi.mocked(apiRequest).mockResolvedValueOnce(response as never);

    const result = await getAdminOperationsAlerts();
    expect(result).toBe(response);
    expect(result).toEqual(response);
  });

  it("propagates errors from apiRequest unchanged (no try/catch in feature layer)", async () => {
    const boom = new Error("boom-from-admin-operations-api");
    vi.mocked(apiRequest).mockRejectedValueOnce(boom);

    await expect(getAdminOperationsAlerts()).rejects.toBe(boom);
  });

  it("never calls /admin/dashboard (dashboard is a different feature)", async () => {
    await getAdminOperationsAlerts();
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).not.toMatch(/\/admin\/dashboard/);
  });

  it("never calls a store-scoped path (operations alerts is admin-global)", async () => {
    await getAdminOperationsAlerts({ store_id: STORE_ID });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).not.toMatch(/^\/stores\//);
  });
});

// --------------------------------------------------------------------- //
// Query serialization
// --------------------------------------------------------------------- //

describe("getAdminOperationsAlerts — query serialization", () => {
  it("serializes limit", async () => {
    await getAdminOperationsAlerts({ limit: 25 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/operations/alerts?limit=25");
  });

  it("preserves an explicit offset=0", async () => {
    await getAdminOperationsAlerts({ offset: 0 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/operations/alerts?offset=0");
  });

  it("serializes a non-zero offset", async () => {
    await getAdminOperationsAlerts({ offset: 100 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/operations/alerts?offset=100");
  });

  it("preserves limit=0 so the backend can 422 it", async () => {
    await getAdminOperationsAlerts({ limit: 0 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/operations/alerts?limit=0");
  });

  it("serializes the category filter", async () => {
    await getAdminOperationsAlerts({ category: "low_stock" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/operations/alerts?category=low_stock");
  });

  it("serializes every locked category value verbatim", async () => {
    const categories = [
      "low_stock",
      "aging_order",
      "compliance_blocker",
      "inactive_store",
      "store_no_inventory",
    ] as const;
    for (const category of categories) {
      vi.mocked(apiRequest).mockReset();
      await getAdminOperationsAlerts({ category });
      const [path] = vi.mocked(apiRequest).mock.calls[0];
      expect(path).toBe(`/admin/operations/alerts?category=${category}`);
    }
  });

  it("serializes the severity filter", async () => {
    await getAdminOperationsAlerts({ severity: "high" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/operations/alerts?severity=high");
  });

  it("serializes every locked severity value verbatim", async () => {
    const severities = ["low", "medium", "high"] as const;
    for (const severity of severities) {
      vi.mocked(apiRequest).mockReset();
      await getAdminOperationsAlerts({ severity });
      const [path] = vi.mocked(apiRequest).mock.calls[0];
      expect(path).toBe(`/admin/operations/alerts?severity=${severity}`);
    }
  });

  it("serializes store_id when set", async () => {
    await getAdminOperationsAlerts({ store_id: STORE_ID });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/admin/operations/alerts?store_id=${STORE_ID}`,
    );
  });

  it("trims a padded store_id before serialization", async () => {
    await getAdminOperationsAlerts({ store_id: `  ${STORE_ID}  ` });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/admin/operations/alerts?store_id=${STORE_ID}`,
    );
  });

  it("drops an empty store_id", async () => {
    await getAdminOperationsAlerts({ store_id: "" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/operations/alerts");
  });

  it("drops a whitespace-only store_id", async () => {
    await getAdminOperationsAlerts({ store_id: "   " });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/operations/alerts");
  });

  it("serializes aging_minutes", async () => {
    await getAdminOperationsAlerts({ aging_minutes: 1440 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/operations/alerts?aging_minutes=1440");
  });

  it("preserves aging_minutes=0 so the backend can 422 it", async () => {
    await getAdminOperationsAlerts({ aging_minutes: 0 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/operations/alerts?aging_minutes=0");
  });

  it("preserves a non-default aging_minutes value", async () => {
    await getAdminOperationsAlerts({ aging_minutes: 60 });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/operations/alerts?aging_minutes=60");
  });

  it("drops undefined filter values", async () => {
    await getAdminOperationsAlerts({
      limit: undefined,
      offset: undefined,
      category: undefined,
      severity: undefined,
      store_id: undefined,
      aging_minutes: undefined,
    });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/operations/alerts");
  });

  it("drops null filter values (defensive — TS forbids them but JS can leak them)", async () => {
    await getAdminOperationsAlerts({
      limit: null,
      offset: null,
      category: null,
      severity: null,
      store_id: null,
      aging_minutes: null,
    } as unknown as AdminOperationsAlertsFilters);
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/operations/alerts");
  });

  it("combines every filter into a single deterministic query string", async () => {
    const filters: AdminOperationsAlertsFilters = {
      limit: 25,
      offset: 50,
      category: "aging_order",
      severity: "high",
      store_id: STORE_ID,
      aging_minutes: 60,
    };
    await getAdminOperationsAlerts(filters);
    const [path] = vi.mocked(apiRequest).mock.calls[0];

    expect(path?.startsWith("/admin/operations/alerts?")).toBe(true);
    const qs = new URL(`http://x${path}`).searchParams;
    expect(qs.get("limit")).toBe("25");
    expect(qs.get("offset")).toBe("50");
    expect(qs.get("category")).toBe("aging_order");
    expect(qs.get("severity")).toBe("high");
    expect(qs.get("store_id")).toBe(STORE_ID);
    expect(qs.get("aging_minutes")).toBe("60");
  });
});

// --------------------------------------------------------------------- //
// Public surface — guard against accidental over-build
// --------------------------------------------------------------------- //

describe("admin-operations api public surface", () => {
  it("exports only getAdminOperationsAlerts", () => {
    expect(Object.keys(adminOperationsApi).sort()).toEqual([
      "getAdminOperationsAlerts",
    ]);
  });

  it.each([
    "getAdminOperationsAlert",
    "acknowledgeAdminOperationsAlert",
    "dismissAdminOperationsAlert",
    "resolveAdminOperationsAlert",
    "snoozeAdminOperationsAlert",
    "createAdminOperationsAlert",
    "updateAdminOperationsAlert",
    "deleteAdminOperationsAlert",
    "getAdminOperationsIncidents",
    "getAdminDashboard",
  ] as const)(
    "does not export `%s` (out-of-scope or wrong feature)",
    (name) => {
      expect(adminOperationsApi).not.toHaveProperty(name);
    },
  );
});
