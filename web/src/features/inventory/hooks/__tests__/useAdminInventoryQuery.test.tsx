// F2.18.2C: tests for useAdminInventoryQuery.
//
// Pattern mirrors useAdminAuditQuery.test.tsx: stub `../../api` so
// the hook resolves against a controlled `getAdminInventory` mock;
// render the hook under a fresh QueryClient; assert (a) the api
// function is called with the expected filters, (b) the cache key
// shape matches `inventoryKeys.adminList(...)`, (c) the hook is
// always enabled (no store context required), (d) errors bubble
// unchanged, and (e) the store-scoped `getInventoryList` is never
// invoked from this code path.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useAdminInventoryQuery } from "../useAdminInventoryQuery";
import { inventoryKeys } from "../queryKeys";
import * as inventoryApi from "../../api";
import type {
  AdminInventoryFilters,
  InventoryListResponse,
} from "../../types";

vi.mock("../../api", () => ({
  getAdminInventory: vi.fn(),
  getInventoryList: vi.fn(),
  getInventoryItem: vi.fn(),
  getInventoryItemLogs: vi.fn(),
  receiveStock: vi.fn(),
  adjustStock: vi.fn(),
  damageStock: vi.fn(),
  updateInventoryThreshold: vi.fn(),
  updateInventoryStatus: vi.fn(),
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

function emptyResponse(): InventoryListResponse {
  return { items: [], total: 0, limit: 100, offset: 0 };
}

beforeEach(() => {
  vi.mocked(inventoryApi.getAdminInventory).mockReset();
  vi.mocked(inventoryApi.getInventoryList).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Happy path
// --------------------------------------------------------------------- //

describe("useAdminInventoryQuery — happy path", () => {
  it("calls getAdminInventory with filters and caches under inventoryKeys.adminList(...)", async () => {
    const response = emptyResponse();
    vi.mocked(inventoryApi.getAdminInventory).mockResolvedValue(response);

    const filters: AdminInventoryFilters = {
      limit: 25,
      low_stock: true,
      status: "available",
    };
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useAdminInventoryQuery(filters),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(inventoryApi.getAdminInventory).toHaveBeenCalledTimes(1);
    const [filtersArg, signal] = vi.mocked(
      inventoryApi.getAdminInventory,
    ).mock.calls[0];
    expect(filtersArg).toBe(filters);
    expect(signal).toBeInstanceOf(AbortSignal);

    const expectedKey = inventoryKeys.adminList(filters);
    expect(client.getQueryData(expectedKey)).toBe(response);
  });

  it("defaults filters to {} when omitted (stable cache key)", async () => {
    vi.mocked(inventoryApi.getAdminInventory).mockResolvedValue(
      emptyResponse(),
    );
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminInventoryQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const [filtersArg] = vi.mocked(inventoryApi.getAdminInventory).mock
      .calls[0];
    expect(filtersArg).toEqual({});
    expect(
      client.getQueryData(inventoryKeys.adminList()),
    ).toEqual(emptyResponse());
  });

  it("scopes to one store when store_id filter is set", async () => {
    vi.mocked(inventoryApi.getAdminInventory).mockResolvedValue(
      emptyResponse(),
    );
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useAdminInventoryQuery({ store_id: STORE_ID }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(
      client.getQueryData(
        inventoryKeys.adminList({ store_id: STORE_ID }),
      ),
    ).toEqual(emptyResponse());
    // Different filter snapshot → different cache slot.
    expect(
      inventoryKeys.adminList({ store_id: STORE_ID }),
    ).not.toEqual(inventoryKeys.adminList());
  });

  it("propagates errors from getAdminInventory unchanged", async () => {
    const boom = new Error("boom-from-admin-inventory-api");
    vi.mocked(inventoryApi.getAdminInventory).mockRejectedValue(boom);

    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminInventoryQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(boom);
  });

  it("does not call store-scoped getInventoryList", async () => {
    vi.mocked(inventoryApi.getAdminInventory).mockResolvedValue(
      emptyResponse(),
    );
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminInventoryQuery(), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(inventoryApi.getInventoryList).not.toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------- //
// No store-context dependency
// --------------------------------------------------------------------- //

describe("useAdminInventoryQuery — no store context required", () => {
  it("fires immediately without a storeId (unlike useInventoryList)", async () => {
    vi.mocked(inventoryApi.getAdminInventory).mockResolvedValue(
      emptyResponse(),
    );
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminInventoryQuery(), {
      wrapper: makeWrapper(client),
    });

    // No idle state — admin feed has no path id and is always enabled.
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(inventoryApi.getAdminInventory).toHaveBeenCalledTimes(1);
  });
});
