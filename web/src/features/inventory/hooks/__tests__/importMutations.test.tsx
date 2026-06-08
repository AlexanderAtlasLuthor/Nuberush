// F2.27.8: tests for the import preview/confirm mutation hooks.
//
// Mirrors mutations.test.tsx: spy on the api layer to assert the
// mutationFn pass-through, and spy on invalidateQueries to assert the
// confirm hook refreshes the inventory lists on success. The preview
// hook must NOT invalidate (it writes nothing server-side).

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useInventoryImportPreviewMutation } from "../useInventoryImportPreviewMutation";
import { useInventoryImportConfirmMutation } from "../useInventoryImportConfirmMutation";
import { inventoryKeys } from "../queryKeys";
import { productsKeys } from "@/features/products/hooks";
import { adminProductsQueryKeys } from "@/features/admin-products/hooks";
import * as inventoryApi from "../../api";

vi.mock("../../api", () => ({
  previewInventoryImport: vi.fn(),
  confirmInventoryImport: vi.fn(),
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";

function makeFile() {
  return new File([new Uint8Array([1])], "inv.xlsx", {
    type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
  });
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

beforeEach(() => {
  vi.mocked(inventoryApi.previewInventoryImport).mockReset();
  vi.mocked(inventoryApi.confirmInventoryImport).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useInventoryImportPreviewMutation", () => {
  it("passes variables to previewInventoryImport and does not invalidate", async () => {
    vi.mocked(inventoryApi.previewInventoryImport).mockResolvedValue(
      {} as never,
    );
    const client = makeQueryClient();
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(
      () => useInventoryImportPreviewMutation(),
      { wrapper: makeWrapper(client) },
    );

    const file = makeFile();
    result.current.mutate({ storeId: STORE_ID, file });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(inventoryApi.previewInventoryImport).toHaveBeenCalledWith({
      storeId: STORE_ID,
      file,
    });
    expect(spy).not.toHaveBeenCalled();
  });
});

describe("useInventoryImportConfirmMutation", () => {
  it("passes variables to confirmInventoryImport and invalidates the lists", async () => {
    vi.mocked(inventoryApi.confirmInventoryImport).mockResolvedValue(
      {} as never,
    );
    const client = makeQueryClient();
    const spy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(
      () => useInventoryImportConfirmMutation(),
      { wrapper: makeWrapper(client) },
    );

    const file = makeFile();
    result.current.mutate({ storeId: STORE_ID, file });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(inventoryApi.confirmInventoryImport).toHaveBeenCalledWith({
      storeId: STORE_ID,
      file,
    });
    expect(spy).toHaveBeenCalledWith({ queryKey: inventoryKeys.lists() });
    // F2.27.9: catalog rows may have been created, so the product lists
    // are invalidated too.
    expect(spy).toHaveBeenCalledWith({ queryKey: productsKeys.lists() });
    expect(spy).toHaveBeenCalledWith({
      queryKey: adminProductsQueryKeys.lists(),
    });
  });
});
