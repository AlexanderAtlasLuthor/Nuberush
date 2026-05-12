// F2.16.4: tests for useStoreAuditQuery.
//
// Pattern mirrors useStoreInventoryLogsQuery.test.tsx: stub
// `../../api` so the hook resolves against a controlled
// `getStoreAudit` mock; render the hook under a fresh QueryClient;
// assert (a) the api function is called with the expected
// storeId + filters, (b) the cache key shape matches
// `auditKeys.storeFeed(...)`, (c) the enabled guard keeps the
// query idle for missing/blank storeId, (d) errors bubble
// unchanged, and (e) the legacy `getStoreInventoryLogs` hook is
// never invoked from this code path.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useStoreAuditQuery } from "../useStoreAuditQuery";
import { auditKeys } from "../queryKeys";
import * as auditApi from "../../api";
import type {
  AuditListResponse,
  StoreAuditFilters,
} from "../../types";

vi.mock("../../api", () => ({
  getStoreAudit: vi.fn(),
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

function emptyResponse(): AuditListResponse {
  return { items: [], total: 0, limit: 50, offset: 0 };
}

beforeEach(() => {
  vi.mocked(auditApi.getStoreAudit).mockReset();
  vi.mocked(auditApi.getStoreInventoryLogs).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Happy path
// --------------------------------------------------------------------- //

describe("useStoreAuditQuery — happy path", () => {
  it("calls getStoreAudit with storeId and filters, caches under auditKeys.storeFeed(...)", async () => {
    const response: AuditListResponse = {
      items: [
        {
          id: "evt-1",
          source: "inventory",
          store_id: STORE_ID,
          actor_id: null,
          action: "receipt",
          entity_type: "inventory_item",
          entity_id: "item-1",
          summary: "Inventory receipt: +10 units (after 10)",
          metadata: { quantity_delta: 10, quantity_after: 10 },
          created_at: "2026-05-04T08:30:00Z",
        },
      ],
      total: 1,
      limit: 25,
      offset: 0,
    };
    vi.mocked(auditApi.getStoreAudit).mockResolvedValue(response);

    const filters: StoreAuditFilters = { limit: 25, source: "inventory" };
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useStoreAuditQuery(STORE_ID, filters),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(auditApi.getStoreAudit).toHaveBeenCalledTimes(1);
    const [storeIdArg, filtersArg, signal] = vi.mocked(
      auditApi.getStoreAudit,
    ).mock.calls[0];
    expect(storeIdArg).toBe(STORE_ID);
    expect(filtersArg).toBe(filters);
    expect(signal).toBeInstanceOf(AbortSignal);

    const expectedKey = auditKeys.storeFeed(STORE_ID, filters);
    expect(client.getQueryData(expectedKey)).toBe(response);
  });

  it("defaults filters to {} when omitted (stable cache key)", async () => {
    vi.mocked(auditApi.getStoreAudit).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const { result } = renderHook(() => useStoreAuditQuery(STORE_ID), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const [storeIdArg, filtersArg] = vi.mocked(auditApi.getStoreAudit).mock
      .calls[0];
    expect(storeIdArg).toBe(STORE_ID);
    expect(filtersArg).toEqual({});

    // The cache key under the implicit-empty-filters path.
    expect(
      client.getQueryData(auditKeys.storeFeed(STORE_ID)),
    ).toEqual(emptyResponse());
  });

  it("returns the AuditListResponse from the api function unchanged", async () => {
    const response = emptyResponse();
    vi.mocked(auditApi.getStoreAudit).mockResolvedValue(response);

    const client = makeQueryClient();
    const { result } = renderHook(() => useStoreAuditQuery(STORE_ID), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBe(response);
  });

  it("propagates errors from getStoreAudit unchanged", async () => {
    const boom = new Error("boom-from-audit-api");
    vi.mocked(auditApi.getStoreAudit).mockRejectedValue(boom);

    const client = makeQueryClient();
    const { result } = renderHook(() => useStoreAuditQuery(STORE_ID), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(boom);
  });

  it("does not call the legacy getStoreInventoryLogs from this hook", async () => {
    vi.mocked(auditApi.getStoreAudit).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const { result } = renderHook(() => useStoreAuditQuery(STORE_ID), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(auditApi.getStoreInventoryLogs).not.toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------- //
// Enabled guard
// --------------------------------------------------------------------- //

describe("useStoreAuditQuery — enabled guard", () => {
  it.each([
    ["null", null],
    ["undefined", undefined],
    ["empty string", ""],
    ["whitespace only", "   "],
  ] as const)(
    "stays idle and does not call the api when storeId is %s",
    async (_label, storeId) => {
      const client = makeQueryClient();
      const { result } = renderHook(() => useStoreAuditQuery(storeId), {
        wrapper: makeWrapper(client),
      });

      expect(result.current.fetchStatus).toBe("idle");
      expect(auditApi.getStoreAudit).not.toHaveBeenCalled();
      expect(auditApi.getStoreInventoryLogs).not.toHaveBeenCalled();
    },
  );

  it("enables once storeId becomes a valid UUID-ish string", async () => {
    vi.mocked(auditApi.getStoreAudit).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const { result, rerender } = renderHook(
      ({ storeId }: { storeId: string | null }) =>
        useStoreAuditQuery(storeId),
      { wrapper: makeWrapper(client), initialProps: { storeId: null } },
    );

    expect(result.current.fetchStatus).toBe("idle");
    expect(auditApi.getStoreAudit).not.toHaveBeenCalled();

    rerender({ storeId: STORE_ID });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(auditApi.getStoreAudit).toHaveBeenCalledTimes(1);
  });
});

// --------------------------------------------------------------------- //
// Query key wiring
// --------------------------------------------------------------------- //

describe("useStoreAuditQuery — query key wiring", () => {
  it("trims the storeId before keying the cache", async () => {
    vi.mocked(auditApi.getStoreAudit).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useStoreAuditQuery(`  ${STORE_ID}  `, { limit: 10 }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Trimmed in both the key and the api call.
    const [storeIdArg] = vi.mocked(auditApi.getStoreAudit).mock.calls[0];
    expect(storeIdArg).toBe(STORE_ID);
    expect(
      client.getQueryData(auditKeys.storeFeed(STORE_ID, { limit: 10 })),
    ).toEqual(emptyResponse());
  });
});
