// F2.6.0 subfase 4: useInventoryList tests.
//
// Strategy: stub `@/auth` so we can drive `useStoreContext().currentStoreId`
// per case, and stub `../api` so the queryFn never touches the real
// transport. We render the hook inside a fresh QueryClient so cache
// state is isolated between tests.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useInventoryList } from "../useInventoryList";
import { inventoryKeys } from "../queryKeys";
import * as inventoryApi from "../../api";
import type { StoreContextState } from "@/auth";

// Module-level ref the @/auth mock reads from on every call. Each test
// flips it via setMockStore() to model admin / non-admin / unauth.
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
  getInventoryList: vi.fn(),
  getInventoryItem: vi.fn(),
  receiveStock: vi.fn(),
  adjustStock: vi.fn(),
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
  vi.mocked(inventoryApi.getInventoryList).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useInventoryList", () => {
  it("does not fire the query when there is no currentStoreId", async () => {
    setMockStore({ currentStoreId: null });
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useInventoryList({ limit: 25, offset: 0 }),
      { wrapper: makeWrapper(client) },
    );

    // enabled: false → fetchStatus is "idle", isPending stays true
    // (no data yet) but no API call has been made.
    expect(result.current.fetchStatus).toBe("idle");
    expect(inventoryApi.getInventoryList).not.toHaveBeenCalled();
  });

  it("fires the query with the resolved storeId when currentStoreId is set", async () => {
    setMockStore({ currentStoreId: STORE_ID, hasStoreContext: true });
    vi.mocked(inventoryApi.getInventoryList).mockResolvedValue({
      items: [],
      total: 0,
      limit: 25,
      offset: 0,
    });
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useInventoryList({ limit: 25, offset: 0, low_stock_only: true }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(inventoryApi.getInventoryList).toHaveBeenCalledTimes(1);
    const [args] = vi.mocked(inventoryApi.getInventoryList).mock.calls[0];
    expect(args).toEqual({
      storeId: STORE_ID,
      limit: 25,
      offset: 0,
      low_stock_only: true,
    });
    expect(result.current.data).toEqual({
      items: [],
      total: 0,
      limit: 25,
      offset: 0,
    });
  });

  it("uses the canonical query key ['inventory','list', storeId, params]", async () => {
    setMockStore({ currentStoreId: STORE_ID, hasStoreContext: true });
    vi.mocked(inventoryApi.getInventoryList).mockResolvedValue({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    });
    const client = makeQueryClient();
    const params = { limit: 50, offset: 0 };

    const { result } = renderHook(() => useInventoryList(params), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const expectedKey = inventoryKeys.list(STORE_ID, params);
    expect(expectedKey).toEqual(["inventory", "list", STORE_ID, params]);

    const cached = client.getQueryData(expectedKey);
    expect(cached).toEqual({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    });
  });
});
