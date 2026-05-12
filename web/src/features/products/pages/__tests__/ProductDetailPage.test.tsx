// F2.8.4: ProductDetailPage tests.
//
// Strategy: stub `../../hooks` so the page renders mocked
// `UseQueryResult` shapes without touching TanStack Query, the api
// layer or the network. We render through a MemoryRouter + Routes so
// `useParams<{ productId: string }>()` resolves like it would in
// production. Each test exercises one render branch (loading, error,
// success+sub-sections, sellable variants, route-param missing) and
// asserts the testids the section components emit.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";
import type { UseQueryResult } from "@tanstack/react-query";

import ProductDetailPage from "../ProductDetailPage";
import { ApiError } from "@/api";
import * as productsHooks from "../../hooks";
import type {
  Product,
  ProductComplianceAuditLog,
  ProductVariant,
} from "../../types";
import type { ProductSellableResponse } from "../../api";

vi.mock("../../hooks", () => ({
  useProductQuery: vi.fn(),
  useProductVariantsQuery: vi.fn(),
  useProductComplianceAuditQuery: vi.fn(),
  useProductSellableQuery: vi.fn(),
}));

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";

function renderAt(path: string): void {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route
          path="/app/store/products/:productId"
          element={<ProductDetailPage />}
        />
        <Route path="/app/store/products" element={<div>Products list</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: PRODUCT_ID,
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

function makeVariant(overrides: Partial<ProductVariant> = {}): ProductVariant {
  return {
    id: "22222222-2222-2222-2222-222222222222",
    product_id: PRODUCT_ID,
    sku: "GUM-MIX-10",
    barcode: "0123456789",
    flavor: "mixed",
    size_label: null,
    unit_count: null,
    puff_count: null,
    thc_strength: null,
    price: "12.50",
    cost: null,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeAuditEntry(
  overrides: Partial<ProductComplianceAuditLog> = {},
): ProductComplianceAuditLog {
  return {
    id: "33333333-3333-3333-3333-333333333333",
    product_id: PRODUCT_ID,
    previous_compliance_status: "allowed",
    new_compliance_status: "restricted",
    previous_allowed_for_sale: true,
    new_allowed_for_sale: true,
    reason: "policy update",
    changed_by_user_id: "44444444-4444-4444-4444-444444444444",
    created_at: "2026-02-01T00:00:00Z",
    ...overrides,
  };
}

// Build a minimal `UseQueryResult` shape via a typed cast — we only
// touch the fields the page reads.
function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return partial as UseQueryResult<TData>;
}

// Each test seeds these defaults; specific tests override per-section.
function seedAllSuccess(): { product: Product } {
  const product = makeProduct();

  vi.mocked(productsHooks.useProductQuery).mockReturnValue(
    asQueryResult<Product>({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: product,
      error: null,
    }),
  );
  vi.mocked(productsHooks.useProductVariantsQuery).mockReturnValue(
    asQueryResult<ProductVariant[]>({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: [makeVariant()],
      error: null,
    }),
  );
  vi.mocked(productsHooks.useProductComplianceAuditQuery).mockReturnValue(
    asQueryResult<ProductComplianceAuditLog[]>({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: [makeAuditEntry()],
      error: null,
    }),
  );
  vi.mocked(productsHooks.useProductSellableQuery).mockReturnValue(
    asQueryResult<ProductSellableResponse>({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: { product_id: PRODUCT_ID, sellable: true },
      error: null,
    }),
  );

  return { product };
}

beforeEach(() => {
  vi.mocked(productsHooks.useProductQuery).mockReset();
  vi.mocked(productsHooks.useProductVariantsQuery).mockReset();
  vi.mocked(productsHooks.useProductComplianceAuditQuery).mockReset();
  vi.mocked(productsHooks.useProductSellableQuery).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Page-level branches
// --------------------------------------------------------------------- //

describe("ProductDetailPage — page-level states", () => {
  it("renders the loading state while the product query is pending", () => {
    vi.mocked(productsHooks.useProductQuery).mockReturnValue(
      asQueryResult<Product>({
        isLoading: true,
        isError: false,
        isSuccess: false,
        data: undefined,
        error: null,
      }),
    );

    renderAt(`/app/store/products/${PRODUCT_ID}`);

    expect(screen.getByText(/loading product/i)).toBeInTheDocument();
    // Sub-section panels must NOT have rendered yet.
    expect(productsHooks.useProductVariantsQuery).not.toHaveBeenCalled();
    expect(productsHooks.useProductComplianceAuditQuery).not.toHaveBeenCalled();
    expect(productsHooks.useProductSellableQuery).not.toHaveBeenCalled();
  });

  it("renders the error state when the product query fails", () => {
    vi.mocked(productsHooks.useProductQuery).mockReturnValue(
      asQueryResult<Product>({
        isLoading: false,
        isError: true,
        isSuccess: false,
        data: undefined,
        error: new ApiError({ status: 404, message: "Product not found" }),
        refetch: vi.fn() as never,
      }),
    );

    renderAt(`/app/store/products/${PRODUCT_ID}`);

    expect(screen.getByText(/product failed to load/i)).toBeInTheDocument();
    expect(screen.getByText(/product not found/i)).toBeInTheDocument();
  });

  it("renders an explicit error when the route param is missing", () => {
    // Mounted directly at /app/store/products with no productId param; the
    // matched Route is the list stub, but rendering the page through a
    // catch-all without the param exercises the empty-id branch.
    render(
      <MemoryRouter initialEntries={["/app/store/products/"]}>
        <Routes>
          <Route path="/app/store/products/:productId" element={<ProductDetailPage />} />
          <Route path="/app/store/products" element={<ProductDetailPage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByText(/missing product id/i)).toBeInTheDocument();
    // The hook is still called with "" (Rules of Hooks: unconditional
    // call before any return), but the hook's own `enabled` guard
    // (productId.length > 0) prevents a network request.
    expect(productsHooks.useProductQuery).toHaveBeenCalledWith("");
    // Sub-section panels must NOT have mounted because the empty-id
    // branch returns before they render.
    expect(productsHooks.useProductVariantsQuery).not.toHaveBeenCalled();
    expect(productsHooks.useProductComplianceAuditQuery).not.toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------- //
// Success — header + sub-sections
// --------------------------------------------------------------------- //

describe("ProductDetailPage — success render", () => {
  it("renders the header with name, brand, category and the four badges", () => {
    seedAllSuccess();

    renderAt(`/app/store/products/${PRODUCT_ID}`);

    expect(screen.getByTestId("product-detail-name")).toHaveTextContent(
      "Cosmic Gummies",
    );
    expect(screen.getByTestId("product-detail-brand")).toHaveTextContent(
      "Lunar Co.",
    );
    expect(screen.getByTestId("product-detail-category")).toHaveTextContent(
      "edibles",
    );
    // Compliance badge appears in BOTH the header AND the compliance
    // panel (same testid `product-compliance-allowed`), so we expect
    // exactly two instances.
    expect(
      screen.getAllByTestId("product-compliance-allowed"),
    ).toHaveLength(2);
    // Status badge: header instance + variant row instance (variant in
    // seedAllSuccess() is is_active=true).
    expect(screen.getAllByTestId("product-status-active")).toHaveLength(2);
    // Allowed-for-sale badge in the header is uniquely test-id'd.
    expect(
      screen.getByTestId("product-detail-allowed-yes"),
    ).toBeInTheDocument();
    // Sellable badge (success branch) — only one instance, in the header.
    expect(screen.getByTestId("product-sellable-yes")).toBeInTheDocument();
  });

  it("renders the compliance panel fields verbatim from the wire", () => {
    seedAllSuccess();
    vi.mocked(productsHooks.useProductQuery).mockReturnValue(
      asQueryResult<Product>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: makeProduct({
          hold_reason: "FDA recall pending",
          jurisdiction: "CA",
          last_compliance_check: "2026-03-15T10:00:00Z",
          allowed_for_sale: false,
        }),
        error: null,
      }),
    );

    renderAt(`/app/store/products/${PRODUCT_ID}`);

    expect(
      screen.getByTestId("product-compliance-hold-reason"),
    ).toHaveTextContent("FDA recall pending");
    expect(
      screen.getByTestId("product-compliance-jurisdiction"),
    ).toHaveTextContent("CA");
    expect(
      screen.getByTestId("product-compliance-last-check"),
    ).toHaveTextContent("2026-03-15T10:00:00Z");
    expect(
      screen.getByTestId("product-compliance-allowed-no"),
    ).toBeInTheDocument();
  });

  it("renders the variants table with sku, barcode, price and status", () => {
    seedAllSuccess();
    vi.mocked(productsHooks.useProductVariantsQuery).mockReturnValue(
      asQueryResult<ProductVariant[]>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: [
          makeVariant({
            id: "v1",
            sku: "GUM-MIX-10",
            barcode: "0123456789",
            price: "12.50",
            is_active: true,
          }),
          makeVariant({
            id: "v2",
            sku: "GUM-MIX-20",
            barcode: null,
            price: "24.99",
            is_active: false,
          }),
        ],
        error: null,
      }),
    );

    renderAt(`/app/store/products/${PRODUCT_ID}`);

    const rows = screen.getAllByTestId("product-variants-row");
    expect(rows).toHaveLength(2);

    // Row 1 — active variant with barcode + Decimal-as-string price.
    expect(within(rows[0]).getByText("GUM-MIX-10")).toBeInTheDocument();
    expect(within(rows[0]).getByText("0123456789")).toBeInTheDocument();
    expect(within(rows[0]).getByText("12.50")).toBeInTheDocument();
    expect(
      within(rows[0]).getByTestId("product-status-active"),
    ).toBeInTheDocument();

    // Row 2 — inactive, null barcode (em-dash fallback).
    expect(within(rows[1]).getByText("GUM-MIX-20")).toBeInTheDocument();
    expect(within(rows[1]).getByText("—")).toBeInTheDocument();
    expect(within(rows[1]).getByText("24.99")).toBeInTheDocument();
    expect(
      within(rows[1]).getByTestId("product-status-inactive"),
    ).toBeInTheDocument();
  });

  it("renders the audit panel with timestamp, status pair, reason and user", () => {
    seedAllSuccess();
    vi.mocked(productsHooks.useProductComplianceAuditQuery).mockReturnValue(
      asQueryResult<ProductComplianceAuditLog[]>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: [
          makeAuditEntry({
            id: "a1",
            previous_compliance_status: "allowed",
            new_compliance_status: "banned",
            reason: "Banned by FDA notice 2026-04-18",
            changed_by_user_id: null,
            created_at: "2026-04-18T12:00:00Z",
          }),
        ],
        error: null,
      }),
    );

    renderAt(`/app/store/products/${PRODUCT_ID}`);

    const row = screen.getByTestId("product-compliance-audit-row");
    expect(within(row).getByText("2026-04-18T12:00:00Z")).toBeInTheDocument();
    expect(within(row).getByText("allowed")).toBeInTheDocument();
    expect(within(row).getByText("banned")).toBeInTheDocument();
    expect(
      within(row).getByText("Banned by FDA notice 2026-04-18"),
    ).toBeInTheDocument();
    // Null user_id → em-dash via the panel's nullableText.
    expect(within(row).getByText("—")).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Section-level states (each panel handles loading/error/empty itself)
// --------------------------------------------------------------------- //

describe("ProductDetailPage — section-level independence", () => {
  it("renders the empty state for variants without affecting the audit panel", () => {
    seedAllSuccess();
    vi.mocked(productsHooks.useProductVariantsQuery).mockReturnValue(
      asQueryResult<ProductVariant[]>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: [],
        error: null,
      }),
    );

    renderAt(`/app/store/products/${PRODUCT_ID}`);

    // EmptyState renders the title as a <h2>; scope to the heading
    // role so we don't also match the "has no variants yet" copy in
    // the message body.
    expect(
      screen.getByRole("heading", { name: /no variants/i }),
    ).toBeInTheDocument();
    // Audit panel still rendered its row independently.
    expect(
      screen.getByTestId("product-compliance-audit-row"),
    ).toBeInTheDocument();
  });

  it("renders the audit panel error state without affecting variants", () => {
    seedAllSuccess();
    vi.mocked(productsHooks.useProductComplianceAuditQuery).mockReturnValue(
      asQueryResult<ProductComplianceAuditLog[]>({
        isLoading: false,
        isError: true,
        isSuccess: false,
        data: undefined,
        error: new ApiError({ status: 403, message: "Admin only" }),
        refetch: vi.fn() as never,
      }),
    );

    renderAt(`/app/store/products/${PRODUCT_ID}`);

    expect(screen.getByText(/audit log failed to load/i)).toBeInTheDocument();
    expect(screen.getByText(/admin only/i)).toBeInTheDocument();
    // Variants panel still rendered its row independently.
    expect(
      screen.getByTestId("product-variants-row"),
    ).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Sellable badge wired through the page
// --------------------------------------------------------------------- //

describe("ProductDetailPage — sellable badge", () => {
  it("renders 'Not sellable' on a 422 ApiError without combining with allowed_for_sale", () => {
    seedAllSuccess();
    // Override sellable to fail with 422 even though the product itself
    // is allowed_for_sale=true. The badge MUST reflect the backend's
    // answer, not the wire boolean.
    vi.mocked(productsHooks.useProductSellableQuery).mockReturnValue(
      asQueryResult<ProductSellableResponse>({
        isLoading: false,
        isError: true,
        isSuccess: false,
        data: undefined,
        error: new ApiError({
          status: 422,
          message: "Not sellable",
          details: { compliance_status: "banned" },
        }),
      }),
    );

    renderAt(`/app/store/products/${PRODUCT_ID}`);

    expect(screen.getByTestId("product-sellable-no")).toBeInTheDocument();
    // Sanity: the wire-boolean allowed badge is still 'yes' because
    // the page does NOT cross-reference the two — they answer
    // different questions.
    expect(
      screen.getByTestId("product-detail-allowed-yes"),
    ).toBeInTheDocument();
  });

  it("renders 'Unknown' on non-422 errors (e.g. 500)", () => {
    seedAllSuccess();
    vi.mocked(productsHooks.useProductSellableQuery).mockReturnValue(
      asQueryResult<ProductSellableResponse>({
        isLoading: false,
        isError: true,
        isSuccess: false,
        data: undefined,
        error: new ApiError({ status: 500, message: "boom" }),
      }),
    );

    renderAt(`/app/store/products/${PRODUCT_ID}`);

    expect(screen.getByTestId("product-sellable-unknown")).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Route param wiring
// --------------------------------------------------------------------- //

describe("ProductDetailPage — route param", () => {
  it("forwards the :productId route param to every hook call", () => {
    seedAllSuccess();

    renderAt(`/app/store/products/${PRODUCT_ID}`);

    expect(productsHooks.useProductQuery).toHaveBeenCalledWith(PRODUCT_ID);
    expect(productsHooks.useProductVariantsQuery).toHaveBeenCalledWith(
      PRODUCT_ID,
    );
    expect(productsHooks.useProductComplianceAuditQuery).toHaveBeenCalledWith(
      PRODUCT_ID,
    );
    expect(productsHooks.useProductSellableQuery).toHaveBeenCalledWith(
      PRODUCT_ID,
    );
  });

  it("renders a back-Link to the products list", () => {
    seedAllSuccess();

    renderAt(`/app/store/products/${PRODUCT_ID}`);

    const back = screen.getByTestId("product-detail-back");
    const anchor = back.tagName === "A" ? back : back.querySelector("a");
    expect(anchor).toHaveAttribute("href", "/app/store/products");
  });
});
