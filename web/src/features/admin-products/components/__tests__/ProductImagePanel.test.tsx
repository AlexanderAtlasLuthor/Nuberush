// F2.22.4.G + F2.26.3.C: ProductImagePanel UI tests.
//
// The panel is presentation around `useProductImageUpload` (upload) and
// `useDeleteProductImage` (clear). Both hooks are mocked here so we can
// drive every state (idle / pending / error / success) deterministically
// and assert the panel's visual + interaction contract — preview-before-
// save, upload/change, and remove — without TanStack Query, the api
// layer, Supabase, or real file I/O.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import type { Product, ProductImage } from "@/features/products/types";
import { ProductImagePanel } from "../ProductImagePanel";

const mockUploadMutate = vi.fn();
const mockUploadReset = vi.fn();
const mockRemoveMutate = vi.fn();
const mockRemoveReset = vi.fn();

let uploadState: { isPending: boolean; isError: boolean; error: Error | null };
let removeState: { isPending: boolean; isError: boolean; error: Error | null };

vi.mock("@/features/products/hooks", () => ({
  // Constants mirror the real module synchronously so the import-time
  // `.join(",")` in the panel resolves before the async test body runs.
  ALLOWED_IMAGE_CONTENT_TYPES: ["image/jpeg", "image/png", "image/webp"] as const,
  MAX_IMAGE_SIZE_BYTES: 5 * 1024 * 1024,
  PRODUCT_IMAGES_BUCKET: "product-images",
  useProductImageUpload: () => ({
    mutate: mockUploadMutate,
    reset: mockUploadReset,
    isPending: uploadState.isPending,
    isError: uploadState.isError,
    error: uploadState.error,
  }),
  useDeleteProductImage: () => ({
    mutate: mockRemoveMutate,
    reset: mockRemoveReset,
    isPending: removeState.isPending,
    isError: removeState.isError,
    error: removeState.error,
  }),
}));

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";

function makeImage(overrides: Partial<ProductImage> = {}): ProductImage {
  return {
    id: "img-1",
    product_id: PRODUCT_ID,
    object_key: `products/${PRODUCT_ID}/hero.jpg`,
    public_url:
      "https://example.supabase.co/storage/v1/object/public/product-images/products/x/hero.jpg",
    uploaded_by_user_id: "admin-1",
    created_at: "2026-05-27T00:00:00Z",
    updated_at: "2026-05-27T00:00:00Z",
    ...overrides,
  };
}

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

function makeFile(name = "hero.jpg"): File {
  return new File([new Uint8Array([1, 2, 3])], name, { type: "image/jpeg" });
}

let createObjectURLMock: ReturnType<typeof vi.fn>;
let revokeObjectURLMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  mockUploadMutate.mockReset();
  mockUploadReset.mockReset();
  mockRemoveMutate.mockReset();
  mockRemoveReset.mockReset();
  uploadState = { isPending: false, isError: false, error: null };
  removeState = { isPending: false, isError: false, error: null };

  // jsdom does not implement object-URL APIs — stub them so the
  // preview-before-save effect can run and so we can assert revocation.
  createObjectURLMock = vi.fn(() => "blob:preview-123");
  revokeObjectURLMock = vi.fn();
  URL.createObjectURL =
    createObjectURLMock as unknown as typeof URL.createObjectURL;
  URL.revokeObjectURL =
    revokeObjectURLMock as unknown as typeof URL.revokeObjectURL;

  // Default mutate stubs fire onSuccess so success-path side effects
  // (clearing the selection) are observable. Tests that need a pending
  // or error state set the hook state instead.
  mockUploadMutate.mockImplementation(
    (_vars: unknown, opts?: { onSuccess?: () => void }) => {
      opts?.onSuccess?.();
    },
  );
  mockRemoveMutate.mockImplementation(
    (_vars: unknown, opts?: { onSuccess?: () => void }) => {
      opts?.onSuccess?.();
    },
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// A / B — current image vs. placeholder
// --------------------------------------------------------------------- //

describe("ProductImagePanel — current image / placeholder", () => {
  it("A: shows the current image when primary_image.public_url is set", () => {
    render(
      <ProductImagePanel
        product={makeProduct({ primary_image: makeImage() })}
      />,
    );
    const img = screen.getByTestId("admin-product-image-preview");
    expect(img).toBeInTheDocument();
    expect(img.getAttribute("src")).toContain(
      "/storage/v1/object/public/product-images/",
    );
    expect(
      screen.queryByTestId("admin-product-image-empty"),
    ).not.toBeInTheDocument();
  });

  it("B: shows the placeholder when primary_image is null", () => {
    render(<ProductImagePanel product={makeProduct()} />);
    expect(
      screen.getByTestId("admin-product-image-empty"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("admin-product-image-preview"),
    ).not.toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// C / D — preview-before-save + object-URL revocation
// --------------------------------------------------------------------- //

describe("ProductImagePanel — preview before save", () => {
  it("C: selecting a file shows a local preview and makes NO upload call", () => {
    render(<ProductImagePanel product={makeProduct()} />);
    const input = screen.getByTestId(
      "admin-product-image-file-input",
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { files: [makeFile()] } });

    const preview = screen.getByTestId("admin-product-image-local-preview");
    expect(preview).toBeInTheDocument();
    expect(preview.getAttribute("src")).toBe("blob:preview-123");
    expect(createObjectURLMock).toHaveBeenCalledTimes(1);
    // Filename + "not uploaded yet" hint, and no backend call yet.
    expect(
      screen.getByTestId("admin-product-image-selected-meta"),
    ).toHaveTextContent(/hero\.jpg/);
    expect(
      screen.getByTestId("admin-product-image-selected-meta"),
    ).toHaveTextContent(/not uploaded yet/i);
    expect(mockUploadMutate).not.toHaveBeenCalled();
  });

  it("D: revokes the object URL when the component unmounts", () => {
    const { unmount } = render(<ProductImagePanel product={makeProduct()} />);
    fireEvent.change(
      screen.getByTestId("admin-product-image-file-input"),
      { target: { files: [makeFile()] } },
    );
    expect(createObjectURLMock).toHaveBeenCalledTimes(1);

    unmount();
    expect(revokeObjectURLMock).toHaveBeenCalledWith("blob:preview-123");
  });

  it("D: revokes the previous object URL when the file changes", () => {
    render(<ProductImagePanel product={makeProduct()} />);
    const input = screen.getByTestId("admin-product-image-file-input");
    fireEvent.change(input, { target: { files: [makeFile("first.jpg")] } });
    fireEvent.change(input, { target: { files: [makeFile("second.jpg")] } });
    // First URL revoked when the second selection replaced it.
    expect(revokeObjectURLMock).toHaveBeenCalledWith("blob:preview-123");
  });
});

// --------------------------------------------------------------------- //
// E / F — upload / change flow
// --------------------------------------------------------------------- //

describe("ProductImagePanel — upload / change", () => {
  it("disables the upload button until a file is selected", () => {
    render(<ProductImagePanel product={makeProduct()} />);
    expect(
      (
        screen.getByTestId(
          "admin-product-image-upload-button",
        ) as HTMLButtonElement
      ).disabled,
    ).toBe(true);
  });

  it("E: clicking Upload calls the existing upload mutation with the file", () => {
    render(<ProductImagePanel product={makeProduct()} />);
    fireEvent.change(
      screen.getByTestId("admin-product-image-file-input"),
      { target: { files: [makeFile()] } },
    );
    const button = screen.getByTestId(
      "admin-product-image-upload-button",
    ) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
    fireEvent.click(button);

    expect(mockUploadMutate).toHaveBeenCalledTimes(1);
    expect(mockUploadMutate.mock.calls[0][0].file).toBeInstanceOf(File);
    // onSuccess (fired by the mock) cleared the selection → local
    // preview is gone and the object URL was revoked.
    expect(
      screen.queryByTestId("admin-product-image-local-preview"),
    ).not.toBeInTheDocument();
    expect(revokeObjectURLMock).toHaveBeenCalled();
  });

  it("shows the loading label while the upload mutation is pending", () => {
    uploadState = { isPending: true, isError: false, error: null };
    render(<ProductImagePanel product={makeProduct()} />);
    const button = screen.getByTestId("admin-product-image-upload-button");
    expect(button).toHaveTextContent(/uploading/i);
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it("F: upload failure shows an error and keeps the current image visible", () => {
    uploadState = {
      isPending: false,
      isError: true,
      error: new Error("Upload failed because reasons."),
    };
    render(
      <ProductImagePanel
        product={makeProduct({ primary_image: makeImage() })}
      />,
    );
    expect(
      screen.getByTestId("admin-product-image-error"),
    ).toHaveTextContent(/upload failed because reasons/i);
    // The existing image was NOT removed by a failed upload.
    expect(
      screen.getByTestId("admin-product-image-preview"),
    ).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// G / H / I — remove / clear flow
// --------------------------------------------------------------------- //

describe("ProductImagePanel — remove image", () => {
  it("G: shows the Remove button only when a current image exists", () => {
    const { rerender } = render(<ProductImagePanel product={makeProduct()} />);
    // No image → no remove button.
    expect(
      screen.queryByTestId("admin-product-image-remove-button"),
    ).not.toBeInTheDocument();

    rerender(
      <ProductImagePanel
        product={makeProduct({ primary_image: makeImage() })}
      />,
    );
    expect(
      screen.getByTestId("admin-product-image-remove-button"),
    ).toBeInTheDocument();
  });

  it("H: clicking Remove calls the delete mutation", () => {
    render(
      <ProductImagePanel
        product={makeProduct({ primary_image: makeImage() })}
      />,
    );
    fireEvent.click(screen.getByTestId("admin-product-image-remove-button"));
    expect(mockRemoveMutate).toHaveBeenCalledTimes(1);
  });

  it("shows the removing label while the delete mutation is pending", () => {
    removeState = { isPending: true, isError: false, error: null };
    render(
      <ProductImagePanel
        product={makeProduct({ primary_image: makeImage() })}
      />,
    );
    const button = screen.getByTestId("admin-product-image-remove-button");
    expect(button).toHaveTextContent(/removing/i);
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it("I: remove failure shows an error and keeps the current image visible", () => {
    removeState = {
      isPending: false,
      isError: true,
      error: new Error("Remove failed upstream."),
    };
    render(
      <ProductImagePanel
        product={makeProduct({ primary_image: makeImage() })}
      />,
    );
    expect(
      screen.getByTestId("admin-product-image-remove-error"),
    ).toHaveTextContent(/remove failed upstream/i);
    // Failed remove must not blank out the still-present image.
    expect(
      screen.getByTestId("admin-product-image-preview"),
    ).toBeInTheDocument();
  });
});
