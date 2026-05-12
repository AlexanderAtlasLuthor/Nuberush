// F2.7.0 subfase 4: useOrdersList tests.
//
// Strategy: stub `@/auth` so we can drive `useStoreContext().currentStoreId`
// per case, and stub `../../api` so the queryFn never touches the real
// transport. Each test renders the hook inside a fresh QueryClient so
// cache state is isolated between tests.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useOrdersList } from "../useOrdersList";
import { ordersKeys } from "../queryKeys";
import * as ordersApi from "../../api";
import type { StoreContextState } from "@/auth";

const mockStore: { current: StoreContextState } = {
  current: {
    currentStoreId: null,
    hasStoreContext: false,
    isStoreRequired: false,
    storeError: null,
  },
};

vi.mock("@/auth", () => ({
  useStoreContext: () => mockStore.current,
}));

vi.mock("../../api", () => ({
  getOrdersList: vi.fn(),
  getOrder: vi.fn(),
  getOrderAuditLogs: vi.fn(),
  createOrder: vi.fn(),
  transitionOrderStatus: vi.fn(),
  cancelOrder: vi.fn(),
  returnOrder: vi.fn(),
}));

function setMockStore(partial: Partial<StoreContextState>) {
  mockStore.current = { ...mockStore.current, ...partial };
}

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
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

const STORE_ID = "11111111-1111-1111-1111-111111111111";

beforeEach(() => {
  setMockStore({
    currentStoreId: null,
    hasStoreContext: false,
    isStoreRequired: false,
    storeError: null,
  });
  vi.mocked(ordersApi.getOrdersList).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useOrdersList", () => {
  it("does not fire the query when there is no currentStoreId", async () => {
    setMockStore({ currentStoreId: null });
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useOrdersList({ limit: 20, offset: 0 }),
      {
        wrapper: makeWrapper(client),
      },
    );

    expect(result.current.fetchStatus).toBe("idle");
    expect(ordersApi.getOrdersList).not.toHaveBeenCalled();
  });

  it("fires the query with the resolved storeId and forwards filters", async () => {
    setMockStore({ currentStoreId: STORE_ID, hasStoreContext: true });
    const response = { items: [], total: 0, limit: 20, offset: 0 };
    vi.mocked(ordersApi.getOrdersList).mockResolvedValue(response);
    const client = makeQueryClient();

    const params = {
      limit: 20,
      offset: 0,
      status: "pending" as const,
      created_from: "2026-01-01T00:00:00Z",
    };

    const { result } = renderHook(() => useOrdersList(params), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(ordersApi.getOrdersList).toHaveBeenCalledTimes(1);
    const [args] = vi.mocked(ordersApi.getOrdersList).mock.calls[0];
    expect(args).toEqual({
      storeId: STORE_ID,
      limit: 20,
      offset: 0,
      status: "pending",
      created_from: "2026-01-01T00:00:00Z",
      created_to: undefined,
    });
    expect(result.current.data).toEqual(response);
  });

  it("uses the canonical query key ['orders','list', storeId, params]", async () => {
    setMockStore({ currentStoreId: STORE_ID, hasStoreContext: true });
    const response = { items: [], total: 0, limit: 20, offset: 40 };
    vi.mocked(ordersApi.getOrdersList).mockResolvedValue(response);
    const client = makeQueryClient();
    const params = { limit: 20, offset: 40, status: "delivered" as const };

    const { result } = renderHook(() => useOrdersList(params), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const expectedKey = ordersKeys.list(STORE_ID, params);
    expect(expectedKey).toEqual(["orders", "list", STORE_ID, params]);

    const cached = client.getQueryData(expectedKey);
    expect(cached).toEqual(response);
  });
});
