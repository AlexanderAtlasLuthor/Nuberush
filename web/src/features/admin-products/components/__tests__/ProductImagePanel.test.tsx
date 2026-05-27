// F2.22.4.G: ProductImagePanel UI tests.
//
// The panel is presentation around `useProductImageUpload`. The hook
// is mocked here so we can drive every state (idle / pending / error /
// success) deterministically and assert the panel's visual contract.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import type { Product } from "@/features/products/types";
import { ProductImagePanel } from "../ProductImagePanel";

const mockMutate = vi.fn();
const mockReset = vi.fn();
let hookState: {
  isPending: boolean;
  isError: boolean;
  error: Error | null;
};

vi.mock("@/features/products/hooks", () => ({
  // Only the surface the panel touches. Constants mirror the real
  // module synchronously so the import-time `.join(",")` in the panel
  // resolves before the async test body runs.
  ALLOWED_IMAGE_CONTENT_TYPES: [
    "image/jpeg",
    "image/png",
    "image/webp",
  ] as const,
  MAX_IMAGE_SIZE_BYTES: 5 * 1024 * 1024,
  PRODUCT_IMAGES_BUCKET: "product-images",
  useProductImageUpload: () => ({
    mutate: mockMutate,
    reset: mockReset,
    isPending: hookState.isPending,
    isError: hookState.isError,
    error: hookState.error,
  }),
}));

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: PRODUCT_ID,
    name: "Mango Ice",
    brand: null,
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
    created_at: "2026-05-27T00:00:00Z",
    updated_at: "2026-05-27T00:00:00Z",
    primary_image: null,
    ...overrides,
  };
}

function makeFile(): File {
  return new File([new Uint8Array([1, 2, 3])], "hero.jpg", {
    type: "image/jpeg",
  });
}

beforeEach(() => {
  mockMutate.mockReset();
  mockReset.mockReset();
  hookState = { isPending: false, isError: false, error: null };
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("ProductImagePanel", () => {
  it("renders the empty state when primary_image is null", () => {
    render(<ProductImagePanel product={makeProduct()} />);
    expect(
      screen.getByTestId("admin-product-image-empty"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("admin-product-image-preview"),
    ).not.toBeInTheDocument();
  });

  it("renders the current image when primary_image.public_url is set", () => {
    render(
      <ProductImagePanel
        product={makeProduct({
          primary_image: {
            id: "img-1",
            product_id: PRODUCT_ID,
            object_key: `products/${PRODUCT_ID}/hero.jpg`,
            public_url:
              "https://example.supabase.co/storage/v1/object/public/product-images/products/x/hero.jpg",
            uploaded_by_user_id: "admin-1",
            created_at: "2026-05-27T00:00:00Z",
            updated_at: "2026-05-27T00:00:00Z",
          },
        })}
      />,
    );
    const img = screen.getByTestId("admin-product-image-preview");
    expect(img).toBeInTheDocument();
    expect(img.getAttribute("src")).toContain(
      "/storage/v1/object/public/product-images/",
    );
  });

  it("disables the upload button until a file is selected", () => {
    render(<ProductImagePanel product={makeProduct()} />);
    const button = screen.getByTestId(
      "admin-product-image-upload-button",
    ) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
  });

  it("enables the upload button after selecting a file and calls mutate on click", () => {
    render(<ProductImagePanel product={makeProduct()} />);
    const input = screen.getByTestId(
      "admin-product-image-file-input",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile()] } });

    const button = screen.getByTestId(
      "admin-product-image-upload-button",
    ) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
    fireEvent.click(button);
    expect(mockMutate).toHaveBeenCalledTimes(1);
    const callArg = mockMutate.mock.calls[0][0];
    expect(callArg.file).toBeInstanceOf(File);
  });

  it("shows the loading label while the mutation is pending", () => {
    hookState = { isPending: true, isError: false, error: null };
    render(<ProductImagePanel product={makeProduct()} />);
    const button = screen.getByTestId(
      "admin-product-image-upload-button",
    );
    expect(button).toHaveTextContent(/uploading/i);
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it("renders an accessible error message when the mutation errors", () => {
    hookState = {
      isPending: false,
      isError: true,
      error: new Error("Upload failed because reasons."),
    };
    render(<ProductImagePanel product={makeProduct()} />);
    const alert = screen.getByRole("alert");
    expect(alert).toHaveTextContent(/upload failed because reasons/i);
  });
});
