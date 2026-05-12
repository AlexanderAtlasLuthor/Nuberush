// F2.8.3: ProductsPage tests.
//
// Strategy: stub `../../hooks` so the page renders the mocked
// `useProductsQuery` result without touching TanStack Query, the api
// layer or the network. We render through a MemoryRouter so the
// row-level "View" Link can be exercised, and we assert the four major
// branches the page renders (loading, error, empty, success) plus the
// success-table rendering of the canonical badges.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";

import ProductsPage from "../ProductsPage";
import { ApiError } from "@/api";
import * as productsHooks from "../../hooks";
import type { Product } from "../../types";

vi.mock("../../hooks", () => ({
  useProductsQuery: vi.fn(),
  // F2.8.6: ProductFormModal (mounted by the page when "Create product"
  // is clicked) calls this mutation. Provide a stub so the conditional-
  // mount branch in the create test exercises real wiring.
  useCreateProductMutation: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    error: null,
    reset: vi.fn(),
  })),
}));

function withRouter(node: ReactNode) {
  return (
    <MemoryRouter initialEntries={["/app/store/products"]}>
      {node}
    </MemoryRouter>
  );
}

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    name: "Cosmic Gummies",
    brand: "Lunar Co.",
    category: "edibles",
    description: null,
    compliance_status: "allowed",
    allowed_for_sale: true,
    is_active: true,
    hold_reason: null,
    jurisdiction: "FL",
    last_compliance_check: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

// Build a minimal `UseQueryResult` shape via a typed cast — we only
// touch the fields the page actually reads. Using `Partial` plus a
// final `as` keeps the test readable and avoids hard-coding the full
// TanStack discriminated union for every case.
function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return partial as UseQueryResult<TData>;
}

beforeEach(() => {
  vi.mocked(productsHooks.useProductsQuery).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("ProductsPage", () => {
  it("renders the loading state while the query is pending", () => {
    vi.mocked(productsHooks.useProductsQuery).mockReturnValue(
      asQueryResult<Product[]>({
        isLoading: true,
        isError: false,
        isSuccess: false,
        data: undefined,
        error: null,
      }),
    );

    render(withRouter(<ProductsPage />));

    expect(screen.getByText(/loading products/i)).toBeInTheDocument();
    expect(screen.queryByTestId("products-row")).not.toBeInTheDocument();
  });

  it("renders the error state and offers retry when the query fails", () => {
    const refetch = vi.fn();
    vi.mocked(productsHooks.useProductsQuery).mockReturnValue(
      asQueryResult<Product[]>({
        isLoading: false,
        isError: true,
        isSuccess: false,
        data: undefined,
        error: new ApiError({
          status: 500,
          message: "Backend exploded",
        }),
        refetch: refetch as never,
      }),
    );

    render(withRouter(<ProductsPage />));

    expect(screen.getByText(/products failed to load/i)).toBeInTheDocument();
    expect(screen.getByText(/backend exploded/i)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders the empty state when the query resolves to []", () => {
    vi.mocked(productsHooks.useProductsQuery).mockReturnValue(
      asQueryResult<Product[]>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: [],
        error: null,
      }),
    );

    render(withRouter(<ProductsPage />));

    expect(screen.getByText(/no products yet/i)).toBeInTheDocument();
    expect(screen.queryByTestId("products-row")).not.toBeInTheDocument();
  });

  it("renders rows, the canonical badges, and a working detail Link on success", () => {
    const products: Product[] = [
      makeProduct({
        id: "aaaa1111-1111-1111-1111-111111111111",
        name: "Allowed-Active product",
        brand: "Brand A",
        compliance_status: "allowed",
        allowed_for_sale: true,
        is_active: true,
      }),
      makeProduct({
        id: "bbbb2222-2222-2222-2222-222222222222",
        name: "Banned-Inactive product",
        brand: null,
        compliance_status: "banned",
        allowed_for_sale: false,
        is_active: false,
      }),
    ];

    vi.mocked(productsHooks.useProductsQuery).mockReturnValue(
      asQueryResult<Product[]>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: products,
        error: null,
      }),
    );

    render(withRouter(<ProductsPage />));

    // Total counter
    expect(screen.getByTestId("products-total")).toHaveTextContent(
      "Showing 2 products",
    );

    // Both rows rendered
    const rows = screen.getAllByTestId("products-row");
    expect(rows).toHaveLength(2);

    // Row 1 — allowed / allowed_for_sale=true / active
    const row1 = rows[0];
    expect(within(row1).getByText("Allowed-Active product")).toBeInTheDocument();
    expect(within(row1).getByText("Brand A")).toBeInTheDocument();
    expect(within(row1).getByTestId("product-compliance-allowed")).toBeInTheDocument();
    expect(within(row1).getByTestId("product-allowed-yes")).toBeInTheDocument();
    expect(within(row1).getByTestId("product-status-active")).toBeInTheDocument();

    // Row 2 — banned / allowed_for_sale=false / inactive, brand fallback "—"
    const row2 = rows[1];
    expect(within(row2).getByText("Banned-Inactive product")).toBeInTheDocument();
    expect(within(row2).getByText("—")).toBeInTheDocument();
    expect(within(row2).getByTestId("product-compliance-banned")).toBeInTheDocument();
    expect(within(row2).getByTestId("product-allowed-no")).toBeInTheDocument();
    expect(within(row2).getByTestId("product-status-inactive")).toBeInTheDocument();

    // Detail Link on row 1 points at /app/store/products/{id}
    const viewLink = within(row1).getByTestId("products-row-view");
    const anchor = viewLink.querySelector("a") ?? viewLink;
    expect(anchor).toHaveAttribute(
      "href",
      "/app/store/products/aaaa1111-1111-1111-1111-111111111111",
    );
  });

  it("forwards local filter state to useProductsQuery", () => {
    vi.mocked(productsHooks.useProductsQuery).mockReturnValue(
      asQueryResult<Product[]>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: [],
        error: null,
      }),
    );

    render(withRouter(<ProductsPage />));

    // Initial render: default filters are sent verbatim.
    expect(productsHooks.useProductsQuery).toHaveBeenCalledWith({
      compliance_status: undefined,
      only_active: false,
    });

    // Toggle "only active" → re-render with only_active: true.
    vi.mocked(productsHooks.useProductsQuery).mockClear();
    fireEvent.click(screen.getByTestId("products-only-active-checkbox"));

    expect(productsHooks.useProductsQuery).toHaveBeenLastCalledWith({
      compliance_status: undefined,
      only_active: true,
    });
  });

  // F2.8.6: Create product wiring
  it("opens the create-product modal when the Create button is clicked", () => {
    vi.mocked(productsHooks.useProductsQuery).mockReturnValue(
      asQueryResult<Product[]>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: [],
        error: null,
      }),
    );

    render(withRouter(<ProductsPage />));

    // Modal not mounted before click — conditional mount keeps the
    // create-product mutation hook unsubscribed.
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("products-create-button"));

    expect(screen.getByRole("dialog")).toBeInTheDocument();
    expect(screen.getByTestId("product-create-submit")).toBeInTheDocument();
  });
});
