// F2.18.2B: tests for useAdminAuditQuery.
//
// Pattern mirrors useStoreAuditQuery.test.tsx: stub `../../api` so
// the hook resolves against a controlled `getAdminAudit` mock;
// render the hook under a fresh QueryClient; assert (a) the api
// function is called with the expected filters, (b) the cache key
// shape matches `auditKeys.adminFeed(...)`, (c) the hook is always
// enabled (no store context required), (d) errors bubble unchanged,
// and (e) neither the store-scoped feed nor the legacy logs hooks
// are invoked from this code path.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useAdminAuditQuery } from "../useAdminAuditQuery";
import { auditKeys } from "../queryKeys";
import * as auditApi from "../../api";
import type {
  AdminAuditFilters,
  AuditListResponse,
} from "../../types";

vi.mock("../../api", () => ({
  getAdminAudit: vi.fn(),
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
  vi.mocked(auditApi.getAdminAudit).mockReset();
  vi.mocked(auditApi.getStoreAudit).mockReset();
  vi.mocked(auditApi.getStoreInventoryLogs).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Happy path
// --------------------------------------------------------------------- //

describe("useAdminAuditQuery — happy path", () => {
  it("calls getAdminAudit with filters and caches under auditKeys.adminFeed(...)", async () => {
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
    vi.mocked(auditApi.getAdminAudit).mockResolvedValue(response);

    const filters: AdminAuditFilters = {
      limit: 25,
      source: "inventory",
    };
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminAuditQuery(filters), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(auditApi.getAdminAudit).toHaveBeenCalledTimes(1);
    const [filtersArg, signal] = vi.mocked(auditApi.getAdminAudit).mock
      .calls[0];
    expect(filtersArg).toBe(filters);
    expect(signal).toBeInstanceOf(AbortSignal);

    const expectedKey = auditKeys.adminFeed(filters);
    expect(client.getQueryData(expectedKey)).toBe(response);
  });

  it("defaults filters to {} when omitted (stable cache key)", async () => {
    vi.mocked(auditApi.getAdminAudit).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminAuditQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const [filtersArg] = vi.mocked(auditApi.getAdminAudit).mock.calls[0];
    expect(filtersArg).toEqual({});
    expect(client.getQueryData(auditKeys.adminFeed())).toEqual(
      emptyResponse(),
    );
  });

  it("scopes to one store when store_id filter is set (cache slot differs from unscoped)", async () => {
    vi.mocked(auditApi.getAdminAudit).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const { result: scoped } = renderHook(
      () => useAdminAuditQuery({ store_id: STORE_ID }),
      { wrapper: makeWrapper(client) },
    );
    const { result: global } = renderHook(() => useAdminAuditQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(scoped.current.isSuccess).toBe(true));
    await waitFor(() => expect(global.current.isSuccess).toBe(true));

    expect(
      client.getQueryData(auditKeys.adminFeed({ store_id: STORE_ID })),
    ).toEqual(emptyResponse());
    expect(client.getQueryData(auditKeys.adminFeed())).toEqual(
      emptyResponse(),
    );
    // Different filter snapshots → different cache slots.
    expect(auditKeys.adminFeed({ store_id: STORE_ID })).not.toEqual(
      auditKeys.adminFeed(),
    );
  });

  it("returns the AuditListResponse unchanged", async () => {
    const response = emptyResponse();
    vi.mocked(auditApi.getAdminAudit).mockResolvedValue(response);

    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminAuditQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBe(response);
  });

  it("propagates errors from getAdminAudit unchanged", async () => {
    const boom = new Error("boom-from-admin-audit-api");
    vi.mocked(auditApi.getAdminAudit).mockRejectedValue(boom);

    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminAuditQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(boom);
  });

  it("does not call getStoreAudit or getStoreInventoryLogs from this hook", async () => {
    vi.mocked(auditApi.getAdminAudit).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminAuditQuery(), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(auditApi.getStoreAudit).not.toHaveBeenCalled();
    expect(auditApi.getStoreInventoryLogs).not.toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------- //
// No store-context dependency
// --------------------------------------------------------------------- //

describe("useAdminAuditQuery — no store context required", () => {
  it("fires immediately without a storeId (unlike useStoreAuditQuery)", async () => {
    vi.mocked(auditApi.getAdminAudit).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminAuditQuery(), {
      wrapper: makeWrapper(client),
    });

    // No idle state — admin feed has no path id and is always enabled.
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(auditApi.getAdminAudit).toHaveBeenCalledTimes(1);
  });
});

// --------------------------------------------------------------------- //
// Query key wiring
// --------------------------------------------------------------------- //

describe("useAdminAuditQuery — query key wiring", () => {
  it("uses auditKeys.adminFeed(filters), never auditKeys.storeFeed(...)", async () => {
    vi.mocked(auditApi.getAdminAudit).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const filters: AdminAuditFilters = { store_id: STORE_ID, limit: 10 };
    const { result } = renderHook(() => useAdminAuditQuery(filters), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // The admin key has data.
    expect(client.getQueryData(auditKeys.adminFeed(filters))).toEqual(
      emptyResponse(),
    );
    // The store-scoped key with the same storeId is untouched.
    expect(
      client.getQueryData(auditKeys.storeFeed(STORE_ID, { limit: 10 })),
    ).toBeUndefined();
  });
});
