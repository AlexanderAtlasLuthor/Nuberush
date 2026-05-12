// F2.6.0 subfase 4: receive + adjust mutation tests.
//
// We spy on `queryClient.invalidateQueries` rather than seeding the
// cache and re-checking `isInvalidated`, because the spy expresses the
// hook's actual contract — *which keys did onSuccess invalidate* —
// in the assertions, not implicitly through cache state.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useReceiveStockMutation } from "../useReceiveStockMutation";
import { useAdjustStockMutation } from "../useAdjustStockMutation";
import { useDamageStockMutation } from "../useDamageStockMutation";
import { useUpdateInventoryThresholdMutation } from "../useUpdateInventoryThresholdMutation";
import { useUpdateInventoryStatusMutation } from "../useUpdateInventoryStatusMutation";
import { inventoryKeys } from "../queryKeys";
import * as inventoryApi from "../../api";

vi.mock("../../api", () => ({
  getInventoryList: vi.fn(),
  getInventoryItem: vi.fn(),
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

beforeEach(() => {
  vi.mocked(inventoryApi.receiveStock).mockReset();
  vi.mocked(inventoryApi.adjustStock).mockReset();
  vi.mocked(inventoryApi.damageStock).mockReset();
  vi.mocked(inventoryApi.updateInventoryThreshold).mockReset();
  vi.mocked(inventoryApi.updateInventoryStatus).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// useReceiveStockMutation
// --------------------------------------------------------------------- //

describe("useReceiveStockMutation", () => {
  it("calls receiveStock with the variables passed to mutate()", async () => {
    vi.mocked(inventoryApi.receiveStock).mockResolvedValue({
      id: ITEM_ID,
    } as never);

    const client = makeQueryClient();
    const { result } = renderHook(() => useReceiveStockMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      inventoryItemId: ITEM_ID,
      body: { quantity: 5, reason: "supplier delivery" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(inventoryApi.receiveStock).toHaveBeenCalledTimes(1);
    expect(inventoryApi.receiveStock).toHaveBeenCalledWith({
      inventoryItemId: ITEM_ID,
      body: { quantity: 5, reason: "supplier delivery" },
    });
  });

  it("invalidates ['inventory','list'] and ['inventory','item', itemId] on success", async () => {
    vi.mocked(inventoryApi.receiveStock).mockResolvedValue({
      id: ITEM_ID,
    } as never);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useReceiveStockMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      inventoryItemId: ITEM_ID,
      body: { quantity: 1 },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: inventoryKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: inventoryKeys.item(ITEM_ID),
    });
    // Sanity: exactly the two onSuccess invalidations, no extras.
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// useAdjustStockMutation
// --------------------------------------------------------------------- //

describe("useAdjustStockMutation", () => {
  it("calls adjustStock with the variables passed to mutate()", async () => {
    vi.mocked(inventoryApi.adjustStock).mockResolvedValue({
      id: ITEM_ID,
    } as never);

    const client = makeQueryClient();
    const { result } = renderHook(() => useAdjustStockMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      inventoryItemId: ITEM_ID,
      body: { delta: -2, reason: "physical recount" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(inventoryApi.adjustStock).toHaveBeenCalledTimes(1);
    expect(inventoryApi.adjustStock).toHaveBeenCalledWith({
      inventoryItemId: ITEM_ID,
      body: { delta: -2, reason: "physical recount" },
    });
  });

  it("invalidates ['inventory','list'] and ['inventory','item', itemId] on success", async () => {
    vi.mocked(inventoryApi.adjustStock).mockResolvedValue({
      id: ITEM_ID,
    } as never);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useAdjustStockMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      inventoryItemId: ITEM_ID,
      body: { delta: 4, reason: "found extra units" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: inventoryKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: inventoryKeys.item(ITEM_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// useDamageStockMutation
// --------------------------------------------------------------------- //

describe("useDamageStockMutation", () => {
  it("calls damageStock with the variables passed to mutate()", async () => {
    vi.mocked(inventoryApi.damageStock).mockResolvedValue({
      id: ITEM_ID,
    } as never);

    const client = makeQueryClient();
    const { result } = renderHook(() => useDamageStockMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      inventoryItemId: ITEM_ID,
      body: { quantity: 2, reason: "broken item" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(inventoryApi.damageStock).toHaveBeenCalledTimes(1);
    expect(inventoryApi.damageStock).toHaveBeenCalledWith({
      inventoryItemId: ITEM_ID,
      body: { quantity: 2, reason: "broken item" },
    });
  });

  it("invalidates ['inventory','list'] and ['inventory','item', itemId] on success", async () => {
    vi.mocked(inventoryApi.damageStock).mockResolvedValue({
      id: ITEM_ID,
    } as never);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useDamageStockMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      inventoryItemId: ITEM_ID,
      body: { quantity: 1, reason: "spilled" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: inventoryKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: inventoryKeys.item(ITEM_ID),
    });
    // Regression guard: exactly the two onSuccess invalidations.
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// useUpdateInventoryThresholdMutation
// --------------------------------------------------------------------- //

describe("useUpdateInventoryThresholdMutation", () => {
  it("calls updateInventoryThreshold with the variables passed to mutate()", async () => {
    vi.mocked(inventoryApi.updateInventoryThreshold).mockResolvedValue({
      id: ITEM_ID,
    } as never);

    const client = makeQueryClient();
    const { result } = renderHook(
      () => useUpdateInventoryThresholdMutation(),
      { wrapper: makeWrapper(client) },
    );

    result.current.mutate({
      inventoryItemId: ITEM_ID,
      body: { reorder_threshold: 12 },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(inventoryApi.updateInventoryThreshold).toHaveBeenCalledTimes(1);
    expect(inventoryApi.updateInventoryThreshold).toHaveBeenCalledWith({
      inventoryItemId: ITEM_ID,
      body: { reorder_threshold: 12 },
    });
  });

  it("invalidates ['inventory','list'] and ['inventory','item', itemId] on success", async () => {
    vi.mocked(inventoryApi.updateInventoryThreshold).mockResolvedValue({
      id: ITEM_ID,
    } as never);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(
      () => useUpdateInventoryThresholdMutation(),
      { wrapper: makeWrapper(client) },
    );

    result.current.mutate({
      inventoryItemId: ITEM_ID,
      body: { reorder_threshold: 0 },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: inventoryKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: inventoryKeys.item(ITEM_ID),
    });
    // Regression guard: exactly the two onSuccess invalidations.
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// useUpdateInventoryStatusMutation
// --------------------------------------------------------------------- //

describe("useUpdateInventoryStatusMutation", () => {
  it("calls updateInventoryStatus with the variables passed to mutate()", async () => {
    vi.mocked(inventoryApi.updateInventoryStatus).mockResolvedValue({
      id: ITEM_ID,
    } as never);

    const client = makeQueryClient();
    const { result } = renderHook(
      () => useUpdateInventoryStatusMutation(),
      { wrapper: makeWrapper(client) },
    );

    result.current.mutate({
      inventoryItemId: ITEM_ID,
      body: { status: "quarantined", reason: "FDA hold" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(inventoryApi.updateInventoryStatus).toHaveBeenCalledTimes(1);
    expect(inventoryApi.updateInventoryStatus).toHaveBeenCalledWith({
      inventoryItemId: ITEM_ID,
      body: { status: "quarantined", reason: "FDA hold" },
    });
  });

  it("invalidates ['inventory','list'] and ['inventory','item', itemId] on success", async () => {
    vi.mocked(inventoryApi.updateInventoryStatus).mockResolvedValue({
      id: ITEM_ID,
    } as never);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(
      () => useUpdateInventoryStatusMutation(),
      { wrapper: makeWrapper(client) },
    );

    result.current.mutate({
      inventoryItemId: ITEM_ID,
      body: { status: "flagged", reason: "supplier issue" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: inventoryKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: inventoryKeys.item(ITEM_ID),
    });
    // Regression guard: exactly the two onSuccess invalidations.
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});
