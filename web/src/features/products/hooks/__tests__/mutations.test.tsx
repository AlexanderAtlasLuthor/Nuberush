// F2.8.2: mutation-hook tests for the products module.
//
// We spy on `queryClient.invalidateQueries` rather than seeding the
// cache and re-checking `isInvalidated`, because the spy expresses the
// hook's actual contract — *which keys did onSuccess invalidate* — in
// the assertions, not implicitly through cache state.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useCreateProductMutation } from "../useCreateProductMutation";
import { useUpdateProductMutation } from "../useUpdateProductMutation";
import { useDeleteProductMutation } from "../useDeleteProductMutation";
import { useCreateVariantMutation } from "../useCreateVariantMutation";
import { useUpdateVariantMutation } from "../useUpdateVariantMutation";
import { useDeleteVariantMutation } from "../useDeleteVariantMutation";
import { useUpdateComplianceMutation } from "../useUpdateComplianceMutation";
import { productsKeys } from "../queryKeys";
import { adminProductsQueryKeys } from "@/features/admin-products/hooks";
import * as productsApi from "../../api";

vi.mock("../../api", () => ({
  createProduct: vi.fn(),
  updateProduct: vi.fn(),
  deleteProduct: vi.fn(),
  createProductVariant: vi.fn(),
  updateProductVariant: vi.fn(),
  deleteProductVariant: vi.fn(),
  updateProductCompliance: vi.fn(),
}));

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";
const NEW_PRODUCT_ID = "33333333-3333-3333-3333-333333333333";
const VARIANT_ID = "22222222-2222-2222-2222-222222222222";

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
  vi.mocked(productsApi.createProduct).mockReset();
  vi.mocked(productsApi.updateProduct).mockReset();
  vi.mocked(productsApi.deleteProduct).mockReset();
  vi.mocked(productsApi.createProductVariant).mockReset();
  vi.mocked(productsApi.updateProductVariant).mockReset();
  vi.mocked(productsApi.deleteProductVariant).mockReset();
  vi.mocked(productsApi.updateProductCompliance).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// useCreateProductMutation
// --------------------------------------------------------------------- //

describe("useCreateProductMutation", () => {
  it("calls createProduct with variables passed to mutate()", async () => {
    vi.mocked(productsApi.createProduct).mockResolvedValue({
      id: NEW_PRODUCT_ID,
    } as never);

    const client = makeQueryClient();
    const { result } = renderHook(() => useCreateProductMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      body: { name: "Cosmic Gummies", category: "edibles" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(productsApi.createProduct).toHaveBeenCalledTimes(1);
    expect(productsApi.createProduct).toHaveBeenCalledWith({
      body: { name: "Cosmic Gummies", category: "edibles" },
    });
  });

  it("invalidates store-side lists, the new detail, and the admin-products list on success", async () => {
    vi.mocked(productsApi.createProduct).mockResolvedValue({
      id: NEW_PRODUCT_ID,
    } as never);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useCreateProductMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      body: { name: "X", category: "y" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.detail(NEW_PRODUCT_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: adminProductsQueryKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(3);
  });
});

// --------------------------------------------------------------------- //
// useUpdateProductMutation
// --------------------------------------------------------------------- //

describe("useUpdateProductMutation", () => {
  it("calls updateProduct with variables passed to mutate()", async () => {
    vi.mocked(productsApi.updateProduct).mockResolvedValue({
      id: PRODUCT_ID,
    } as never);

    const client = makeQueryClient();
    const { result } = renderHook(() => useUpdateProductMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      productId: PRODUCT_ID,
      body: { name: "Renamed" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(productsApi.updateProduct).toHaveBeenCalledTimes(1);
    expect(productsApi.updateProduct).toHaveBeenCalledWith({
      productId: PRODUCT_ID,
      body: { name: "Renamed" },
    });
  });

  it("invalidates lists() and detail(productId) on success", async () => {
    vi.mocked(productsApi.updateProduct).mockResolvedValue({
      id: PRODUCT_ID,
    } as never);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateProductMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      productId: PRODUCT_ID,
      body: { is_active: false },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.detail(PRODUCT_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// useDeleteProductMutation
// --------------------------------------------------------------------- //

describe("useDeleteProductMutation", () => {
  it("calls deleteProduct with the productId and hard flag", async () => {
    vi.mocked(productsApi.deleteProduct).mockResolvedValue(
      undefined as never,
    );

    const client = makeQueryClient();
    const { result } = renderHook(() => useDeleteProductMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ productId: PRODUCT_ID, hard: true });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(productsApi.deleteProduct).toHaveBeenCalledTimes(1);
    expect(productsApi.deleteProduct).toHaveBeenCalledWith({
      productId: PRODUCT_ID,
      hard: true,
    });
  });

  it("invalidates lists() and detail(productId) on success", async () => {
    vi.mocked(productsApi.deleteProduct).mockResolvedValue(
      undefined as never,
    );

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useDeleteProductMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ productId: PRODUCT_ID });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.detail(PRODUCT_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// useCreateVariantMutation
// --------------------------------------------------------------------- //

describe("useCreateVariantMutation", () => {
  it("injects product_id into the body so the path and body cannot desync", async () => {
    vi.mocked(productsApi.createProductVariant).mockResolvedValue({
      id: VARIANT_ID,
      product_id: PRODUCT_ID,
    } as never);

    const client = makeQueryClient();
    const { result } = renderHook(() => useCreateVariantMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      productId: PRODUCT_ID,
      body: { sku: "GUM-MIX-10", price: "12.50" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(productsApi.createProductVariant).toHaveBeenCalledTimes(1);
    expect(productsApi.createProductVariant).toHaveBeenCalledWith({
      productId: PRODUCT_ID,
      body: {
        sku: "GUM-MIX-10",
        price: "12.50",
        product_id: PRODUCT_ID,
      },
    });
  });

  it("invalidates variants(productId) and detail(productId) on success", async () => {
    vi.mocked(productsApi.createProductVariant).mockResolvedValue({
      id: VARIANT_ID,
      product_id: PRODUCT_ID,
    } as never);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useCreateVariantMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      productId: PRODUCT_ID,
      body: { sku: "GUM-MIX-20", price: "24.99" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.variants(PRODUCT_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.detail(PRODUCT_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// useUpdateVariantMutation
// --------------------------------------------------------------------- //

describe("useUpdateVariantMutation", () => {
  it("calls updateProductVariant with the variantId-only params", async () => {
    vi.mocked(productsApi.updateProductVariant).mockResolvedValue({
      id: VARIANT_ID,
      product_id: PRODUCT_ID,
    } as never);

    const client = makeQueryClient();
    const { result } = renderHook(() => useUpdateVariantMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      variantId: VARIANT_ID,
      body: { price: "15.00" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(productsApi.updateProductVariant).toHaveBeenCalledTimes(1);
    expect(productsApi.updateProductVariant).toHaveBeenCalledWith({
      variantId: VARIANT_ID,
      body: { price: "15.00" },
    });
  });

  it("invalidates variants(data.product_id) and detail(data.product_id)", async () => {
    vi.mocked(productsApi.updateProductVariant).mockResolvedValue({
      id: VARIANT_ID,
      product_id: PRODUCT_ID,
    } as never);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateVariantMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      variantId: VARIANT_ID,
      body: { is_active: false },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.variants(PRODUCT_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.detail(PRODUCT_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// useDeleteVariantMutation
// --------------------------------------------------------------------- //

describe("useDeleteVariantMutation", () => {
  it("calls deleteProductVariant with only variantId + hard (productId stays client-side)", async () => {
    vi.mocked(productsApi.deleteProductVariant).mockResolvedValue(
      undefined as never,
    );

    const client = makeQueryClient();
    const { result } = renderHook(() => useDeleteVariantMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      variantId: VARIANT_ID,
      productId: PRODUCT_ID,
      hard: true,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(productsApi.deleteProductVariant).toHaveBeenCalledTimes(1);
    expect(productsApi.deleteProductVariant).toHaveBeenCalledWith({
      variantId: VARIANT_ID,
      hard: true,
    });
  });

  it("invalidates variants(productId) and detail(productId) using the var-supplied productId", async () => {
    vi.mocked(productsApi.deleteProductVariant).mockResolvedValue(
      undefined as never,
    );

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useDeleteVariantMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      variantId: VARIANT_ID,
      productId: PRODUCT_ID,
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.variants(PRODUCT_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.detail(PRODUCT_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// useUpdateComplianceMutation
// --------------------------------------------------------------------- //

describe("useUpdateComplianceMutation", () => {
  it("calls updateProductCompliance with variables passed to mutate()", async () => {
    vi.mocked(productsApi.updateProductCompliance).mockResolvedValue({
      id: PRODUCT_ID,
    } as never);

    const client = makeQueryClient();
    const { result } = renderHook(() => useUpdateComplianceMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      productId: PRODUCT_ID,
      body: {
        compliance_status: "banned",
        allowed_for_sale: false,
        reason: "FDA recall",
      },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(productsApi.updateProductCompliance).toHaveBeenCalledTimes(1);
    expect(productsApi.updateProductCompliance).toHaveBeenCalledWith({
      productId: PRODUCT_ID,
      body: {
        compliance_status: "banned",
        allowed_for_sale: false,
        reason: "FDA recall",
      },
    });
  });

  it("invalidates detail, lists, sellable, and complianceAudit on success", async () => {
    vi.mocked(productsApi.updateProductCompliance).mockResolvedValue({
      id: PRODUCT_ID,
    } as never);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateComplianceMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      productId: PRODUCT_ID,
      body: {
        compliance_status: "restricted",
        allowed_for_sale: true,
        reason: "policy update",
      },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.detail(PRODUCT_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.sellable(PRODUCT_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: productsKeys.complianceAudit(PRODUCT_ID),
    });
    // Regression guard: exactly the four onSuccess invalidations.
    expect(invalidateSpy).toHaveBeenCalledTimes(4);
  });
});
