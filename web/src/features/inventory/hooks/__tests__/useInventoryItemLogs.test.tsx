// F2.6.2 subfase 4: useInventoryItemLogs tests.
//
// Mirrors the useInventoryItem suite. The hook is read-only, so the
// assertions focus on: (a) it forwards inventoryItemId + params to the
// api function verbatim, (b) it caches under the expected key, and
// (c) the empty-id guard keeps the query idle.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useInventoryItemLogs } from "../useInventoryItemLogs";
import { inventoryKeys } from "../queryKeys";
import * as inventoryApi from "../../api";

vi.mock("../../api", () => ({
  getInventoryList: vi.fn(),
  getInventoryItem: vi.fn(),
  getInventoryItemLogs: vi.fn(),
  receiveStock: vi.fn(),
  adjustStock: vi.fn(),
  damageStock: vi.fn(),
  updateInventoryThreshold: vi.fn(),
  updateInventoryStatus: vi.fn(),
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
  vi.mocked(inventoryApi.getInventoryItemLogs).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useInventoryItemLogs", () => {
  it("calls getInventoryItemLogs and caches under inventoryKeys.itemLogs(...)", async () => {
    const fakeLogs = [{ id: "log-1" }] as unknown;
    vi.mocked(inventoryApi.getInventoryItemLogs).mockResolvedValue(
      fakeLogs as never,
    );
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useInventoryItemLogs(ITEM_ID, { limit: 20 }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(inventoryApi.getInventoryItemLogs).toHaveBeenCalledTimes(1);
    const [args] = vi.mocked(inventoryApi.getInventoryItemLogs).mock.calls[0];
    expect(args).toEqual({ inventoryItemId: ITEM_ID, limit: 20 });

    const expectedKey = inventoryKeys.itemLogs(ITEM_ID, { limit: 20 });
    expect(expectedKey).toEqual([
      "inventory",
      "item",
      ITEM_ID,
      "logs",
      { limit: 20 },
    ]);
    expect(client.getQueryData(expectedKey)).toBe(fakeLogs);
  });

  it("uses an empty-params key when no params are passed", async () => {
    vi.mocked(inventoryApi.getInventoryItemLogs).mockResolvedValue(
      [] as never,
    );
    const client = makeQueryClient();

    const { result } = renderHook(() => useInventoryItemLogs(ITEM_ID), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const [args] = vi.mocked(inventoryApi.getInventoryItemLogs).mock.calls[0];
    expect(args).toEqual({ inventoryItemId: ITEM_ID });

    expect(client.getQueryData(inventoryKeys.itemLogs(ITEM_ID))).toEqual([]);
  });

  it("does not fire the query when the id is empty", async () => {
    const client = makeQueryClient();

    const { result } = renderHook(() => useInventoryItemLogs(""), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(inventoryApi.getInventoryItemLogs).not.toHaveBeenCalled();
  });
});
