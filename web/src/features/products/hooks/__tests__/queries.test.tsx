// F2.8.2: read-hook tests for the products module.
//
// Strategy: stub `../../api` so the queryFn never touches the real
// transport. Render each hook inside a fresh QueryClient so cache
// state is isolated between cases. We assert:
//
//   - which API function the hook calls
//   - what arguments it forwards
//   - the canonical cache key the result lands under
//   - the `enabled` guard on every id-driven hook
//   - that the sellable hook does NOT translate 422 into sellable=false

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useProductsQuery } from "../useProductsQuery";
import { useProductQuery } from "../useProductQuery";
import { useProductVariantsQuery } from "../useProductVariantsQuery";
import { useProductSellableQuery } from "../useProductSellableQuery";
import { useProductComplianceAuditQuery } from "../useProductComplianceAuditQuery";
import { productsKeys } from "../queryKeys";
import * as productsApi from "../../api";
import { ApiError } from "@/api";

vi.mock("../../api", () => ({
  listProducts: vi.fn(),
  getProduct: vi.fn(),
  getProductVariants: vi.fn(),
  getProductSellable: vi.fn(),
  getProductComplianceAudit: vi.fn(),
}));

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";

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
  vi.mocked(productsApi.listProducts).mockReset();
  vi.mocked(productsApi.getProduct).mockReset();
  vi.mocked(productsApi.getProductVariants).mockReset();
  vi.mocked(productsApi.getProductSellable).mockReset();
  vi.mocked(productsApi.getProductComplianceAudit).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// useProductsQuery
// --------------------------------------------------------------------- //

describe("useProductsQuery", () => {
  it("calls listProducts with the filters and lands the result on the canonical key", async () => {
    vi.mocked(productsApi.listProducts).mockResolvedValue([]);
    const client = makeQueryClient();
    const filters = { only_active: true, limit: 25, offset: 0 };

    const { result } = renderHook(() => useProductsQuery(filters), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(productsApi.listProducts).toHaveBeenCalledTimes(1);
    const [args] = vi.mocked(productsApi.listProducts).mock.calls[0];
    expect(args).toEqual(filters);

    const expectedKey = productsKeys.list(filters);
    expect(expectedKey).toEqual(["products", "list", filters]);
    expect(client.getQueryData(expectedKey)).toEqual([]);
  });

  it("defaults to an empty filters object when called with no args", async () => {
    vi.mocked(productsApi.listProducts).mockResolvedValue([]);
    const client = makeQueryClient();

    const { result } = renderHook(() => useProductsQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const [args] = vi.mocked(productsApi.listProducts).mock.calls[0];
    expect(args).toEqual({});
  });
});

// --------------------------------------------------------------------- //
// useProductQuery
// --------------------------------------------------------------------- //

describe("useProductQuery", () => {
  it("does not fire when the productId is empty (enabled guard)", async () => {
    const client = makeQueryClient();

    const { result } = renderHook(() => useProductQuery(""), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(productsApi.getProduct).not.toHaveBeenCalled();
  });

  it("calls getProduct with { productId } and caches under detail(id)", async () => {
    vi.mocked(productsApi.getProduct).mockResolvedValue({
      id: PRODUCT_ID,
    } as never);
    const client = makeQueryClient();

    const { result } = renderHook(() => useProductQuery(PRODUCT_ID), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(productsApi.getProduct).toHaveBeenCalledTimes(1);
    const [args] = vi.mocked(productsApi.getProduct).mock.calls[0];
    expect(args).toEqual({ productId: PRODUCT_ID });

    const cached = client.getQueryData(productsKeys.detail(PRODUCT_ID));
    expect(cached).toEqual({ id: PRODUCT_ID });
  });
});

// --------------------------------------------------------------------- //
// useProductVariantsQuery
// --------------------------------------------------------------------- //

describe("useProductVariantsQuery", () => {
  it("does not fire when the productId is empty (enabled guard)", async () => {
    const client = makeQueryClient();

    const { result } = renderHook(() => useProductVariantsQuery(""), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(productsApi.getProductVariants).not.toHaveBeenCalled();
  });

  it("calls getProductVariants and caches under variantsList(id, params)", async () => {
    vi.mocked(productsApi.getProductVariants).mockResolvedValue([]);
    const client = makeQueryClient();
    const params = { only_active: true };

    const { result } = renderHook(
      () => useProductVariantsQuery(PRODUCT_ID, params),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(productsApi.getProductVariants).toHaveBeenCalledTimes(1);
    const [args] = vi.mocked(productsApi.getProductVariants).mock.calls[0];
    expect(args).toEqual({ productId: PRODUCT_ID, only_active: true });

    const cached = client.getQueryData(
      productsKeys.variantsList(PRODUCT_ID, params),
    );
    expect(cached).toEqual([]);
  });
});

// --------------------------------------------------------------------- //
// useProductSellableQuery
// --------------------------------------------------------------------- //

describe("useProductSellableQuery", () => {
  it("does not fire when the productId is empty (enabled guard)", async () => {
    const client = makeQueryClient();

    const { result } = renderHook(() => useProductSellableQuery(""), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(productsApi.getProductSellable).not.toHaveBeenCalled();
  });

  it("resolves to { product_id, sellable: true } on the success path", async () => {
    vi.mocked(productsApi.getProductSellable).mockResolvedValue({
      product_id: PRODUCT_ID,
      sellable: true,
    });
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useProductSellableQuery(PRODUCT_ID),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual({
      product_id: PRODUCT_ID,
      sellable: true,
    });
  });

  it("propagates a 422 ApiError instead of translating it into sellable=false", async () => {
    const failingFlags = {
      is_active: true,
      allowed_for_sale: false,
      compliance_status: "banned",
    };
    vi.mocked(productsApi.getProductSellable).mockRejectedValue(
      new ApiError({
        status: 422,
        message: "Product is not sellable",
        details: failingFlags,
      }),
    );
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useProductSellableQuery(PRODUCT_ID),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.data).toBeUndefined();
    const err = result.current.error as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.details).toEqual(failingFlags);
  });
});

// --------------------------------------------------------------------- //
// useProductComplianceAuditQuery
// --------------------------------------------------------------------- //

describe("useProductComplianceAuditQuery", () => {
  it("does not fire when the productId is empty (enabled guard)", async () => {
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useProductComplianceAuditQuery(""),
      { wrapper: makeWrapper(client) },
    );

    expect(result.current.fetchStatus).toBe("idle");
    expect(productsApi.getProductComplianceAudit).not.toHaveBeenCalled();
  });

  it("calls getProductComplianceAudit and caches under complianceAudit(id)", async () => {
    vi.mocked(productsApi.getProductComplianceAudit).mockResolvedValue([]);
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useProductComplianceAuditQuery(PRODUCT_ID),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(productsApi.getProductComplianceAudit).toHaveBeenCalledTimes(1);
    const [args] = vi.mocked(productsApi.getProductComplianceAudit).mock
      .calls[0];
    expect(args).toEqual({ productId: PRODUCT_ID });

    const cached = client.getQueryData(
      productsKeys.complianceAudit(PRODUCT_ID),
    );
    expect(cached).toEqual([]);
  });
});
