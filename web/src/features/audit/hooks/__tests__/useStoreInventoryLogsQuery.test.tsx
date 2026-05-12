// F2.10.2: tests for the audit hooks.
//
// Pattern mirrors features/inventory/hooks/__tests__/useInventoryItemLogs.test.tsx
// and features/users/hooks/__tests__/mutations.test.tsx: stub `../../api`
// so the hook resolves against a controlled `getStoreInventoryLogs`
// mock; render the hook under a fresh QueryClient; assert (a) the
// api function is called with the documented params, (b) the cache
// key shape matches `auditKeys.storeInventoryLogs(...)`, (c) the
// enabled guard keeps the query idle for missing/blank storeId,
// (d) errors bubble unchanged, and (e) the public surface contains
// only the two F2.10.2 exports.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useStoreInventoryLogsQuery } from "../useStoreInventoryLogsQuery";
import { auditKeys } from "../queryKeys";
import * as auditHooks from "../index";
import * as auditApi from "../../api";
import type { StoreInventoryLogEntry } from "../../types";

vi.mock("../../api", () => ({
  getStoreInventoryLogs: vi.fn(),
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
    },
  });
}

function makeWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

beforeEach(() => {
  vi.mocked(auditApi.getStoreInventoryLogs).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// auditKeys — minimal shape
// --------------------------------------------------------------------- //

describe("auditKeys", () => {
  it("auditKeys.all equals ['audit']", () => {
    expect(auditKeys.all).toEqual(["audit"]);
  });

  it("auditKeys.storeInventoryLogs(storeId) defaults params to {}", () => {
    expect(auditKeys.storeInventoryLogs(STORE_ID)).toEqual([
      "audit",
      "store-inventory-logs",
      STORE_ID,
      {},
    ]);
  });

  it("auditKeys.storeInventoryLogs(storeId, { limit }) includes the limit on the key", () => {
    expect(auditKeys.storeInventoryLogs(STORE_ID, { limit: 50 })).toEqual([
      "audit",
      "store-inventory-logs",
      STORE_ID,
      { limit: 50 },
    ]);
  });

  it("exposes the F2.16 + F2.18.2B surface (legacy + store feed + admin feed)", () => {
    expect(Object.keys(auditKeys).sort()).toEqual(
      [
        "all",
        "adminFeed",
        "adminFeeds",
        "storeFeed",
        "storeFeeds",
        "storeInventoryLogs",
      ].sort(),
    );
  });

  it.each([
    "events",
    "activity",
    "feed",
    "userActivity",
    "user",
    "storeAudit",
    "orderAuditLogs",
    "inventoryItemLogs",
    "complianceAudit",
    "lists",
    "list",
    "details",
    "detail",
  ] as const)(
    "does not expose `%s` on auditKeys (covered by storeFeed / handled by sibling features)",
    (name) => {
      expect(auditKeys).not.toHaveProperty(name);
    },
  );
});

// --------------------------------------------------------------------- //
// useStoreInventoryLogsQuery — happy path
// --------------------------------------------------------------------- //

describe("useStoreInventoryLogsQuery", () => {
  it("calls getStoreInventoryLogs with storeId and limit, caches under auditKeys.storeInventoryLogs(...)", async () => {
    const fakeLogs = [{ id: "log-1" }] as unknown as StoreInventoryLogEntry[];
    vi.mocked(auditApi.getStoreInventoryLogs).mockResolvedValue(fakeLogs);
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useStoreInventoryLogsQuery({ storeId: STORE_ID, limit: 50 }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(auditApi.getStoreInventoryLogs).toHaveBeenCalledTimes(1);
    const [args, signal] = vi.mocked(auditApi.getStoreInventoryLogs).mock
      .calls[0];
    expect(args).toEqual({ storeId: STORE_ID, limit: 50 });
    // AbortSignal is forwarded.
    expect(signal).toBeInstanceOf(AbortSignal);

    const expectedKey = auditKeys.storeInventoryLogs(STORE_ID, { limit: 50 });
    expect(client.getQueryData(expectedKey)).toBe(fakeLogs);
  });

  it("uses an empty-params key when no limit is provided", async () => {
    vi.mocked(auditApi.getStoreInventoryLogs).mockResolvedValue([]);
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useStoreInventoryLogsQuery({ storeId: STORE_ID }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const [args] = vi.mocked(auditApi.getStoreInventoryLogs).mock.calls[0];
    expect(args).toEqual({ storeId: STORE_ID, limit: undefined });

    expect(
      client.getQueryData(auditKeys.storeInventoryLogs(STORE_ID)),
    ).toEqual([]);
  });

  it("returns the StoreInventoryLogEntry[] response from the api function unchanged", async () => {
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
    vi.mocked(auditApi.getStoreInventoryLogs).mockResolvedValue(response);

    const client = makeQueryClient();
    const { result } = renderHook(
      () => useStoreInventoryLogsQuery({ storeId: STORE_ID }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toBe(response);
  });

  it("propagates errors from getStoreInventoryLogs unchanged", async () => {
    const boom = new Error("boom-from-api");
    vi.mocked(auditApi.getStoreInventoryLogs).mockRejectedValue(boom);

    const client = makeQueryClient();
    const { result } = renderHook(
      () => useStoreInventoryLogsQuery({ storeId: STORE_ID }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(boom);
  });
});

// --------------------------------------------------------------------- //
// useStoreInventoryLogsQuery — enabled guard
// --------------------------------------------------------------------- //

describe("useStoreInventoryLogsQuery — enabled guard", () => {
  it.each([
    ["null", null],
    ["undefined", undefined],
    ["empty string", ""],
    ["whitespace only", "   "],
  ] as const)(
    "stays idle and does not call the api when storeId is %s",
    async (_label, storeId) => {
      const client = makeQueryClient();
      const { result } = renderHook(
        () => useStoreInventoryLogsQuery({ storeId }),
        { wrapper: makeWrapper(client) },
      );

      expect(result.current.fetchStatus).toBe("idle");
      expect(auditApi.getStoreInventoryLogs).not.toHaveBeenCalled();
    },
  );
});

// --------------------------------------------------------------------- //
// Public surface — guard against accidental over-build
// --------------------------------------------------------------------- //

describe("audit hooks public surface", () => {
  it("exports the F2.16 + F2.18.2B surface (auditKeys + three query hooks)", () => {
    expect(Object.keys(auditHooks).sort()).toEqual(
      [
        "auditKeys",
        "useAdminAuditQuery",
        "useStoreAuditQuery",
        "useStoreInventoryLogsQuery",
      ].sort(),
    );
  });

  it.each([
    "useAuditEventsQuery",
    "useGlobalAuditFeedQuery",
    "useActivityFeedQuery",
    "useUserActivityQuery",
    "useOrderAuditLogsQuery",
    "useInventoryItemLogsQuery",
    "useProductComplianceAuditQuery",
  ] as const)(
    "does not export `%s` (no matching backend endpoint or already wrapped elsewhere)",
    (name) => {
      expect(auditHooks).not.toHaveProperty(name);
    },
  );
});
