// F2.26.3.B: store ProductsTable image display tests.
//
// Pure presentational component test — the table receives rows and
// renders them. Wrapped in MemoryRouter because each row renders a
// <Link>. Covers: a row with a primary image renders the thumbnail; a
// row without one renders the placeholder; and the store list surface
// exposes no image-management (upload/change/delete) controls.

import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ProductsTable } from "../ProductsTable";
import type { Product, ProductImage } from "../../types";

function makeImage(overrides: Partial<ProductImage> = {}): ProductImage {
  return {
    id: "img-1",
    product_id: "prod-1",
    object_key: "products/prod-1/hero.jpg",
    public_url:
      "https://example.supabase.co/storage/v1/object/public/product-images/products/prod-1/hero.jpg",
    uploaded_by_user_id: "user-1",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    name: "Mango Ice",
    brand: "NubeBrand",
    category: "vape",
    description: null,
    compliance_status: "allowed",
    allowed_for_sale: true,
    is_active: true,
    hold_reason: null,
    jurisdiction: "FL",
    last_compliance_check: null,
    approval_status: "approved",
    proposed_by_store_id: null,
    proposed_by_user_id: null,
    reviewed_by_user_id: null,
    reviewed_at: null,
    rejection_reason: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function renderTable(products: Product[]) {
  return render(
    <MemoryRouter>
      <ProductsTable products={products} />
    </MemoryRouter>,
  );
}

describe("ProductsTable — image display", () => {
  it("renders a thumbnail when the product has a primary image", () => {
    renderTable([makeProduct({ primary_image: makeImage() })]);
    const cell = screen.getByTestId("products-row-thumbnail");
    expect(
      within(cell).getByTestId("product-thumbnail-image"),
    ).toBeInTheDocument();
  });

  it("renders a placeholder when the product has no image", () => {
    renderTable([makeProduct({ primary_image: null })]);
    const cell = screen.getByTestId("products-row-thumbnail");
    expect(
      within(cell).getByTestId("product-thumbnail-placeholder"),
    ).toBeInTheDocument();
  });

  it("does not render image upload/change/delete controls", () => {
    renderTable([makeProduct({ primary_image: makeImage() })]);
    // Store list is read-only for images: no file input, no
    // upload/change/remove buttons anywhere on the surface.
    expect(
      document.querySelector("input[type=file]"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /upload/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /(change|replace) image/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /(remove|delete) image/i }),
    ).not.toBeInTheDocument();
  });
});
