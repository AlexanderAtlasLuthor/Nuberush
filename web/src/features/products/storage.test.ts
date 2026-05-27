// F2.22.4.G: tests for the product image storage API module.
//
// Covers the three thin functions: requestProductImageUploadUrl,
// uploadProductImageToSignedUrl, confirmProductImageUpload.
//
// `@/api` and `@/lib/supabase` are mocked so the tests run offline.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  PRODUCT_IMAGES_BUCKET,
  ProductImageUploadError,
  confirmProductImageUpload,
  requestProductImageUploadUrl,
  uploadProductImageToSignedUrl,
} from "./storage";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const uploadToSignedUrlMock = vi.fn();

vi.mock("@/lib/supabase", () => ({
  supabase: {
    storage: {
      from: vi.fn(() => ({
        uploadToSignedUrl: uploadToSignedUrlMock,
      })),
    },
  },
}));

import { apiRequest } from "@/api";
import { supabase } from "@/lib/supabase";

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  uploadToSignedUrlMock.mockReset();
  vi.mocked(supabase.storage.from).mockClear();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// requestProductImageUploadUrl
// --------------------------------------------------------------------- //

describe("requestProductImageUploadUrl", () => {
  it("POSTs to /products/{id}/image-upload-url with the metadata body", async () => {
    vi.mocked(apiRequest).mockResolvedValue({
      bucket: PRODUCT_IMAGES_BUCKET,
      object_key: `products/${PRODUCT_ID}/abc.jpg`,
      signed_upload_url: "https://example.supabase.co/x?token=t",
      expires_in_seconds: 600,
    });

    const result = await requestProductImageUploadUrl({
      productId: PRODUCT_ID,
      metadata: {
        filename: "hero.jpg",
        content_type: "image/jpeg",
        size_bytes: 12345,
      },
    });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/products/${PRODUCT_ID}/image-upload-url`);
    expect(options).toMatchObject({
      method: "POST",
      body: {
        filename: "hero.jpg",
        content_type: "image/jpeg",
        size_bytes: 12345,
      },
    });
    expect(result.bucket).toBe(PRODUCT_IMAGES_BUCKET);
  });
});

// --------------------------------------------------------------------- //
// uploadProductImageToSignedUrl
// --------------------------------------------------------------------- //

describe("uploadProductImageToSignedUrl", () => {
  function makeFile(): File {
    return new File([new Uint8Array([1, 2, 3])], "hero.jpg", {
      type: "image/jpeg",
    });
  }

  it("calls supabase.storage.from(bucket).uploadToSignedUrl with the extracted token", async () => {
    uploadToSignedUrlMock.mockResolvedValue({
      data: { path: `products/${PRODUCT_ID}/abc.jpg` },
      error: null,
    });

    await uploadProductImageToSignedUrl({
      bucket: PRODUCT_IMAGES_BUCKET,
      objectKey: `products/${PRODUCT_ID}/abc.jpg`,
      signedUploadUrl:
        "https://example.supabase.co/storage/v1/object/upload/sign/" +
        `${PRODUCT_IMAGES_BUCKET}/products/${PRODUCT_ID}/abc.jpg?token=SIGNED-TOKEN`,
      file: makeFile(),
    });

    expect(supabase.storage.from).toHaveBeenCalledWith(
      PRODUCT_IMAGES_BUCKET,
    );
    expect(uploadToSignedUrlMock).toHaveBeenCalledTimes(1);
    const [path, token, file, options] = uploadToSignedUrlMock.mock.calls[0];
    expect(path).toBe(`products/${PRODUCT_ID}/abc.jpg`);
    expect(token).toBe("SIGNED-TOKEN");
    expect(file).toBeInstanceOf(File);
    expect(options).toMatchObject({ contentType: "image/jpeg" });
  });

  it("throws ProductImageUploadError when the URL has no token", async () => {
    await expect(
      uploadProductImageToSignedUrl({
        bucket: PRODUCT_IMAGES_BUCKET,
        objectKey: "products/x/y.jpg",
        signedUploadUrl: "https://example.supabase.co/x",
        file: makeFile(),
      }),
    ).rejects.toBeInstanceOf(ProductImageUploadError);
    expect(uploadToSignedUrlMock).not.toHaveBeenCalled();
  });

  it("throws ProductImageUploadError when supabase returns an error", async () => {
    uploadToSignedUrlMock.mockResolvedValue({
      data: null,
      error: { message: "boom" },
    });

    await expect(
      uploadProductImageToSignedUrl({
        bucket: PRODUCT_IMAGES_BUCKET,
        objectKey: "products/x/y.jpg",
        signedUploadUrl: "https://example.supabase.co/x?token=t",
        file: makeFile(),
      }),
    ).rejects.toBeInstanceOf(ProductImageUploadError);
  });
});

// --------------------------------------------------------------------- //
// confirmProductImageUpload
// --------------------------------------------------------------------- //

describe("confirmProductImageUpload", () => {
  it("POSTs to /products/{id}/images with the bucket and object_key", async () => {
    vi.mocked(apiRequest).mockResolvedValue({
      id: "img-1",
      product_id: PRODUCT_ID,
      object_key: `products/${PRODUCT_ID}/abc.jpg`,
      public_url: null,
      uploaded_by_user_id: "admin-1",
      created_at: "2026-05-27T00:00:00Z",
      updated_at: "2026-05-27T00:00:00Z",
    });

    const result = await confirmProductImageUpload({
      productId: PRODUCT_ID,
      body: {
        bucket: PRODUCT_IMAGES_BUCKET,
        object_key: `products/${PRODUCT_ID}/abc.jpg`,
      },
    });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/products/${PRODUCT_ID}/images`);
    expect(options).toMatchObject({
      method: "POST",
      body: {
        bucket: PRODUCT_IMAGES_BUCKET,
        object_key: `products/${PRODUCT_ID}/abc.jpg`,
      },
    });
    expect(result.object_key).toBe(
      `products/${PRODUCT_ID}/abc.jpg`,
    );
  });
});
