// Read-hook tests for the store-earnings snapshot hook.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useStoreEarningsQuery } from "../useStoreEarningsQuery";
import { storeEarningsKeys } from "../queryKeys";
import * as storeEarningsApi from "../../api";
import type { StoreEarningsSummary } from "../../types";

vi.mock("../../api", () => ({
  getStoreEarnings: vi.fn(),
}));

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

const RESPONSE: StoreEarningsSummary = {
  delivered_orders: 3,
  total_items_sold: 7,
  product_revenue: "105.00",
  top_products: [
    {
      variant_id: "22222222-2222-2222-2222-222222222222",
      product_name: "Pricey",
      variant_label: "Mango · 5000 puffs",
      quantity_sold: 2,
      revenue: "100.00",
    },
  ],
};

beforeEach(() => {
  vi.mocked(storeEarningsApi.getStoreEarnings).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useStoreEarningsQuery", () => {
  it("fetches when storeId is non-empty and trims whitespace", async () => {
    vi.mocked(storeEarningsApi.getStoreEarnings).mockResolvedValue(
      RESPONSE,
    );
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useStoreEarningsQuery({ storeId: `   ${STORE_ID}  ` }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(storeEarningsApi.getStoreEarnings).toHaveBeenCalledTimes(1);
    expect(storeEarningsApi.getStoreEarnings).toHaveBeenCalledWith(
      { storeId: STORE_ID },
      expect.any(AbortSignal),
    );
    expect(result.current.data).toEqual(RESPONSE);
  });

  it("does not fetch when storeId is null", () => {
    const client = makeQueryClient();
    const { result } = renderHook(
      () => useStoreEarningsQuery({ storeId: null }),
      { wrapper: makeWrapper(client) },
    );
    expect(storeEarningsApi.getStoreEarnings).not.toHaveBeenCalled();
    expect(result.current.isPending).toBe(true);
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("does not fetch when storeId is undefined", () => {
    const client = makeQueryClient();
    renderHook(() => useStoreEarningsQuery({ storeId: undefined }), {
      wrapper: makeWrapper(client),
    });
    expect(storeEarningsApi.getStoreEarnings).not.toHaveBeenCalled();
  });

  it("does not fetch when storeId is whitespace-only", () => {
    const client = makeQueryClient();
    renderHook(() => useStoreEarningsQuery({ storeId: "    " }), {
      wrapper: makeWrapper(client),
    });
    expect(storeEarningsApi.getStoreEarnings).not.toHaveBeenCalled();
  });

  it("scopes cache by storeId", async () => {
    vi.mocked(storeEarningsApi.getStoreEarnings).mockResolvedValue(
      RESPONSE,
    );
    const client = makeQueryClient();

    renderHook(() => useStoreEarningsQuery({ storeId: STORE_ID }), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() =>
      expect(
        client.getQueryData(storeEarningsKeys.summary(STORE_ID)),
      ).toBeDefined(),
    );
    // A different storeId resolves to a different cache entry.
    expect(
      client.getQueryData(storeEarningsKeys.summary("other-id")),
    ).toBeUndefined();
  });

  it("propagates errors as isError", async () => {
    const failure = new Error("boom");
    vi.mocked(storeEarningsApi.getStoreEarnings).mockRejectedValue(
      failure,
    );
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useStoreEarningsQuery({ storeId: STORE_ID }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(failure);
  });
});
