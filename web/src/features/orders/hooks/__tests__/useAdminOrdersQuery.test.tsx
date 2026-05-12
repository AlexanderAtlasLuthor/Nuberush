// F2.18.2C: tests for useAdminOrdersQuery.
//
// Pattern mirrors useAdminInventoryQuery.test.tsx: stub `../../api`
// so the hook resolves against a controlled `getAdminOrders` mock;
// render under a fresh QueryClient; assert (a) the api function is
// called with the expected filters, (b) the cache key shape matches
// `ordersKeys.adminList(...)`, (c) the hook is always enabled (no
// store context required), (d) errors bubble unchanged, and (e) the
// store-scoped `getOrdersList` is never invoked from this code path.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useAdminOrdersQuery } from "../useAdminOrdersQuery";
import { ordersKeys } from "../queryKeys";
import * as ordersApi from "../../api";
import type {
  AdminOrdersFilters,
  OrdersListResponse,
} from "../../types";

vi.mock("../../api", () => ({
  getAdminOrders: vi.fn(),
  getOrdersList: vi.fn(),
  getOrder: vi.fn(),
  getOrderAuditLogs: vi.fn(),
  createOrder: vi.fn(),
  transitionOrderStatus: vi.fn(),
  cancelOrder: vi.fn(),
  returnOrder: vi.fn(),
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

function emptyResponse(): OrdersListResponse {
  return { items: [], total: 0, limit: 50, offset: 0 };
}

beforeEach(() => {
  vi.mocked(ordersApi.getAdminOrders).mockReset();
  vi.mocked(ordersApi.getOrdersList).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Happy path
// --------------------------------------------------------------------- //

describe("useAdminOrdersQuery — happy path", () => {
  it("calls getAdminOrders with filters and caches under ordersKeys.adminList(...)", async () => {
    const response = emptyResponse();
    vi.mocked(ordersApi.getAdminOrders).mockResolvedValue(response);

    const filters: AdminOrdersFilters = {
      limit: 25,
      status: "pending",
    };
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminOrdersQuery(filters), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(ordersApi.getAdminOrders).toHaveBeenCalledTimes(1);
    const [filtersArg, signal] = vi.mocked(ordersApi.getAdminOrders).mock
      .calls[0];
    expect(filtersArg).toBe(filters);
    expect(signal).toBeInstanceOf(AbortSignal);

    const expectedKey = ordersKeys.adminList(filters);
    expect(client.getQueryData(expectedKey)).toBe(response);
  });

  it("defaults filters to {} when omitted (stable cache key)", async () => {
    vi.mocked(ordersApi.getAdminOrders).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminOrdersQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const [filtersArg] = vi.mocked(ordersApi.getAdminOrders).mock.calls[0];
    expect(filtersArg).toEqual({});
    expect(client.getQueryData(ordersKeys.adminList())).toEqual(
      emptyResponse(),
    );
  });

  it("scopes to one store when store_id filter is set", async () => {
    vi.mocked(ordersApi.getAdminOrders).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useAdminOrdersQuery({ store_id: STORE_ID }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(
      client.getQueryData(ordersKeys.adminList({ store_id: STORE_ID })),
    ).toEqual(emptyResponse());
    expect(ordersKeys.adminList({ store_id: STORE_ID })).not.toEqual(
      ordersKeys.adminList(),
    );
  });

  it("propagates errors from getAdminOrders unchanged", async () => {
    const boom = new Error("boom-from-admin-orders-api");
    vi.mocked(ordersApi.getAdminOrders).mockRejectedValue(boom);

    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminOrdersQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(boom);
  });

  it("does not call store-scoped getOrdersList", async () => {
    vi.mocked(ordersApi.getAdminOrders).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminOrdersQuery(), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(ordersApi.getOrdersList).not.toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------- //
// No store-context dependency
// --------------------------------------------------------------------- //

describe("useAdminOrdersQuery — no store context required", () => {
  it("fires immediately without a storeId (unlike useOrdersList)", async () => {
    vi.mocked(ordersApi.getAdminOrders).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminOrdersQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(ordersApi.getAdminOrders).toHaveBeenCalledTimes(1);
  });
});
