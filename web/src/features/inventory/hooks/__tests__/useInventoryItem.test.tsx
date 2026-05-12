// F2.6.0 subfase 4: useInventoryItem tests.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useInventoryItem } from "../useInventoryItem";
import { inventoryKeys } from "../queryKeys";
import * as inventoryApi from "../../api";

vi.mock("../../api", () => ({
  getInventoryList: vi.fn(),
  getInventoryItem: vi.fn(),
  receiveStock: vi.fn(),
  adjustStock: vi.fn(),
}));

const ITEM_ID = "22222222-2222-2222-2222-222222222222";

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
  vi.mocked(inventoryApi.getInventoryItem).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useInventoryItem", () => {
  it("fires the query and caches under ['inventory','item', itemId] for a valid id", async () => {
    const fakeItem = { id: ITEM_ID, store_id: "x" } as unknown;
    vi.mocked(inventoryApi.getInventoryItem).mockResolvedValue(
      fakeItem as never,
    );
    const client = makeQueryClient();

    const { result } = renderHook(() => useInventoryItem(ITEM_ID), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(inventoryApi.getInventoryItem).toHaveBeenCalledTimes(1);
    const [args] = vi.mocked(inventoryApi.getInventoryItem).mock.calls[0];
    expect(args).toEqual({ inventoryItemId: ITEM_ID });

    expect(client.getQueryData(inventoryKeys.item(ITEM_ID))).toBe(fakeItem);
  });

  it("does not fire the query when the id is empty", async () => {
    const client = makeQueryClient();

    const { result } = renderHook(() => useInventoryItem(""), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(inventoryApi.getInventoryItem).not.toHaveBeenCalled();
  });
});
