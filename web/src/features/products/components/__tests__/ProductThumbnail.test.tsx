// F2.26.3.B: ProductThumbnail component tests.
//
// Pure presentational component — no hooks, no API, no router needed.
// Covers: renders the image when a public_url exists, renders the
// placeholder when there is no image, and swaps to a safe "Image
// unavailable" fallback when the image fails to load (onError).

import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { ProductThumbnail } from "../ProductThumbnail";
import type { ProductImage } from "../../types";

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

describe("ProductThumbnail", () => {
  it("renders the image when primary_image.public_url exists", () => {
    render(
      <ProductThumbnail
        primaryImage={makeImage()}
        productName="Mango Ice"
      />,
    );
    const img = screen.getByTestId("product-thumbnail-image");
    expect(img).toBeInTheDocument();
    expect(img).toHaveAttribute("src", makeImage().public_url as string);
    // Accessible alt text derived from the product name.
    expect(img).toHaveAttribute("alt", "Mango Ice product image");
    expect(
      screen.queryByTestId("product-thumbnail-placeholder"),
    ).not.toBeInTheDocument();
  });

  it("renders the placeholder when there is no image (null)", () => {
    render(
      <ProductThumbnail primaryImage={null} productName="Mango Ice" />,
    );
    const placeholder = screen.getByTestId("product-thumbnail-placeholder");
    expect(placeholder).toBeInTheDocument();
    expect(placeholder).toHaveAttribute("aria-label", "Mango Ice: No image yet");
    expect(placeholder).toHaveAttribute("data-broken", "false");
    expect(
      screen.queryByTestId("product-thumbnail-image"),
    ).not.toBeInTheDocument();
  });

  it("renders the placeholder when primary_image is undefined", () => {
    render(<ProductThumbnail productName="Mango Ice" />);
    expect(
      screen.getByTestId("product-thumbnail-placeholder"),
    ).toBeInTheDocument();
  });

  it("renders the placeholder when public_url is null", () => {
    render(
      <ProductThumbnail
        primaryImage={makeImage({ public_url: null })}
        productName="Mango Ice"
      />,
    );
    expect(
      screen.getByTestId("product-thumbnail-placeholder"),
    ).toBeInTheDocument();
  });

  it("swaps to a safe fallback when the image fails to load (onError)", () => {
    render(
      <ProductThumbnail
        primaryImage={makeImage()}
        productName="Mango Ice"
      />,
    );
    const img = screen.getByTestId("product-thumbnail-image");
    fireEvent.error(img);

    // Image is gone; the placeholder fallback is shown with the
    // "Image unavailable" affordance.
    expect(
      screen.queryByTestId("product-thumbnail-image"),
    ).not.toBeInTheDocument();
    const placeholder = screen.getByTestId("product-thumbnail-placeholder");
    expect(placeholder).toHaveAttribute("data-broken", "true");
    expect(placeholder).toHaveAttribute(
      "aria-label",
      "Mango Ice: Image unavailable",
    );
  });

  it("shows the label text at the lg size", () => {
    render(
      <ProductThumbnail
        primaryImage={null}
        productName="Mango Ice"
        size="lg"
      />,
    );
    expect(screen.getByText("No image yet")).toBeInTheDocument();
  });
});
