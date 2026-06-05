// F2.20.5: tests for the real Admin Product detail page.
//
// The page reuses canonical product detail components via the
// existing `useProductQuery` hook plus inner components that own
// their own data fetches (ProductVariantsTable,
// ProductComplianceAuditPanel). We stub:
//
//   - `@/features/products/hooks` — useProductQuery + the panel hooks.
//   - The canonical detail components — stubbed to lightweight
//     stand-ins so the page render is observable without exercising
//     every inner contract (those are tested in features/products
//     directly).
//
// Coverage:
//   - Missing productId → ErrorState.
//   - Loading state.
//   - Error state with retry.
//   - Empty (no data despite success) state.
//   - Success state renders the canonical detail components.
//   - Back link points to /app/admin/products.
//   - Route productId is forwarded to useProductQuery.
//   - Architecture guard: no fetch, no auth, no store context.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import AdminProductDetailPage from "../AdminProductDetailPage";
import * as productsHooks from "@/features/products/hooks";
import type { Product } from "@/features/products/types";

vi.mock("@/features/products/hooks", () => ({
  useProductQuery: vi.fn(),
  // AdminProductApprovalPanel is stubbed below; these still need to
  // exist on the mock so other code paths that import the hooks
  // barrel (e.g. the panel under test if not stubbed) don't blow up.
  useApproveProductMutation: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
  })),
  useRejectProductMutation: vi.fn(() => ({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
    error: null,
  })),
}));

// Stub the canonical inner components so the page render is
// observable without exercising every panel's own contract. Each
// stand-in surfaces a deterministic testid so we can verify the
// page mounts the canonical detail surface.
vi.mock("@/features/products/components/ProductDetailHeader", () => ({
  ProductDetailHeader: ({ product }: { product: Product }) => (
    <div data-testid="product-detail-header">
      header:{product.name}
    </div>
  ),
}));

vi.mock("@/features/products/components/ProductActionsBar", () => ({
  ProductActionsBar: ({ product }: { product: Product }) => (
    <div data-testid="product-actions-bar">actions:{product.id}</div>
  ),
}));

vi.mock("@/features/products/components/ProductCompliancePanel", () => ({
  ProductCompliancePanel: ({ product }: { product: Product }) => (
    <div data-testid="product-compliance-panel">
      compliance:{product.compliance_status}
    </div>
  ),
}));

vi.mock("@/features/products/components/ProductVariantsTable", () => ({
  ProductVariantsTable: ({ productId }: { productId: string }) => (
    <div data-testid="product-variants-table">variants:{productId}</div>
  ),
}));

vi.mock(
  "@/features/products/components/ProductComplianceAuditPanel",
  () => ({
    ProductComplianceAuditPanel: ({
      productId,
    }: {
      productId: string;
    }) => (
      <div data-testid="product-compliance-audit-panel">
        audit:{productId}
      </div>
    ),
  }),
);

// F2.22.4.G — admin-local ProductImagePanel is stubbed at the page
// level so this test focuses on page composition; the panel has its
// own dedicated tests under ../../components/__tests__.
vi.mock("../../components/ProductImagePanel", () => ({
  ProductImagePanel: ({ product }: { product: Product }) => (
    <div data-testid="product-image-panel">image:{product.id}</div>
  ),
}));

const PRODUCT_ID = "55555555-5555-5555-5555-555555555555";

function asQueryResult(
  partial: Partial<UseQueryResult<Product>>,
): UseQueryResult<Product> {
  return {
    refetch: vi.fn(),
    isPending: false,
    isLoading: false,
    isError: false,
    isSuccess: false,
    isFetching: false,
    data: undefined,
    error: null,
    ...partial,
  } as unknown as UseQueryResult<Product>;
}

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: PRODUCT_ID,
    name: "Mango Ice",
    brand: "NubeBrand",
    category: "vape",
    description: null,
    compliance_status: "restricted",
    allowed_for_sale: true,
    is_active: true,
    hold_reason: null,
    jurisdiction: "FL",
    last_compliance_check: "2026-05-12T08:00:00Z",
    approval_status: "approved",
    proposed_by_store_id: null,
    proposed_by_user_id: null,
    reviewed_by_user_id: null,
    reviewed_at: null,
    rejection_reason: null,
    created_at: "2026-05-10T12:00:00Z",
    updated_at: "2026-05-12T08:00:00Z",
    ...overrides,
  };
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/app/admin/products/:productId"
          element={<AdminProductDetailPage />}
        />
        <Route
          path="/app/admin/products"
          element={<div>Admin products list</div>}
        />
      </Routes>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(productsHooks.useProductQuery).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Loading / error / empty / success
// --------------------------------------------------------------------- //

describe("AdminProductDetailPage — loading", () => {
  it("renders a loading state while the product query is pending", () => {
    vi.mocked(productsHooks.useProductQuery).mockReturnValue(
      asQueryResult({ isPending: true, isLoading: true }),
    );
    renderAt(`/app/admin/products/${PRODUCT_ID}`);
    expect(screen.getByRole("status")).toBeInTheDocument();
    expect(
      screen.queryByTestId("product-detail-header"),
    ).not.toBeInTheDocument();
  });
});

describe("AdminProductDetailPage — error", () => {
  it("renders an error state with retry when the product query errors", () => {
    const refetch = vi.fn();
    vi.mocked(productsHooks.useProductQuery).mockReturnValue(
      asQueryResult({
        isError: true,
        error: new Error("forbidden"),
        refetch,
      }),
    );
    renderAt(`/app/admin/products/${PRODUCT_ID}`);
    expect(screen.getByRole("alert")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});

describe("AdminProductDetailPage — empty", () => {
  it("renders an empty state when the query succeeds but returns no data", () => {
    vi.mocked(productsHooks.useProductQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: undefined }),
    );
    renderAt(`/app/admin/products/${PRODUCT_ID}`);
    expect(screen.getByText(/Product not found/i)).toBeInTheDocument();
  });
});

describe("AdminProductDetailPage — success", () => {
  it("renders the canonical detail components with backend data", () => {
    vi.mocked(productsHooks.useProductQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeProduct() }),
    );
    renderAt(`/app/admin/products/${PRODUCT_ID}`);

    expect(
      screen.getByTestId("product-detail-header"),
    ).toHaveTextContent("header:Mango Ice");
    expect(
      screen.getByTestId("product-actions-bar"),
    ).toHaveTextContent(`actions:${PRODUCT_ID}`);
    expect(
      screen.getByTestId("product-compliance-panel"),
    ).toHaveTextContent("compliance:restricted");
    expect(
      screen.getByTestId("product-variants-table"),
    ).toHaveTextContent(`variants:${PRODUCT_ID}`);
    expect(
      screen.getByTestId("product-compliance-audit-panel"),
    ).toHaveTextContent(`audit:${PRODUCT_ID}`);
  });

  it("L: renders exactly one image panel and no separate store image section", () => {
    vi.mocked(productsHooks.useProductQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeProduct() }),
    );
    renderAt(`/app/admin/products/${PRODUCT_ID}`);

    // The admin image management surface is the single ProductImagePanel.
    expect(
      screen.getAllByTestId("product-image-panel"),
    ).toHaveLength(1);
    // No duplicate read-only store image section on the admin detail page.
    expect(
      screen.queryByTestId("store-product-image"),
    ).not.toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Route wiring
// --------------------------------------------------------------------- //

describe("AdminProductDetailPage — route wiring", () => {
  it("forwards the URL :productId param to useProductQuery", () => {
    vi.mocked(productsHooks.useProductQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeProduct() }),
    );
    renderAt(`/app/admin/products/${PRODUCT_ID}`);
    expect(productsHooks.useProductQuery).toHaveBeenCalledWith(
      PRODUCT_ID,
    );
  });

  it("renders an error state when the route :productId is missing", () => {
    vi.mocked(productsHooks.useProductQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: undefined }),
    );
    // Render at the parent route directly so :productId is undefined.
    render(
      <MemoryRouter initialEntries={["/app/admin/products/"]}>
        <Routes>
          <Route
            path="/app/admin/products/"
            element={<AdminProductDetailPage />}
          />
        </Routes>
      </MemoryRouter>,
    );
    expect(screen.getByText(/Missing product id/i)).toBeInTheDocument();
  });

  it("back-link points to /app/admin/products", () => {
    vi.mocked(productsHooks.useProductQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeProduct() }),
    );
    renderAt(`/app/admin/products/${PRODUCT_ID}`);
    const backLink = screen.getByTestId("admin-product-detail-back");
    expect(backLink).toHaveAttribute("href", "/app/admin/products");
  });

  it("renders the bare productId via a font-mono span", () => {
    vi.mocked(productsHooks.useProductQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeProduct() }),
    );
    renderAt(`/app/admin/products/${PRODUCT_ID}`);
    const idSpan = screen.getByTestId("admin-product-detail-id");
    expect(idSpan).toHaveTextContent(PRODUCT_ID);
  });
});

// --------------------------------------------------------------------- //
// Architecture guard
// --------------------------------------------------------------------- //

describe("AdminProductDetailPage — architecture guard", () => {
  it("renders without an AuthProvider or StoreProvider in the tree", () => {
    // MemoryRouter is the only context provided. If the page touched
    // useAuth / useStoreContext, the render would crash.
    vi.mocked(productsHooks.useProductQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeProduct() }),
    );
    expect(() =>
      renderAt(`/app/admin/products/${PRODUCT_ID}`),
    ).not.toThrow();
  });
});
