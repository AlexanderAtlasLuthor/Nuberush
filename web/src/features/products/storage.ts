// F2.22.4.G: product image upload — frontend storage API.
//
// Three thin async functions for the admin product image upload flow.
// FastAPI mints the signed upload URL, validates metadata, and writes
// the `public.product_images` row. The frontend uploads the binary to
// Supabase Storage with `uploadToSignedUrl` and never writes business
// metadata directly.
//
// Hard rules baked in (docs/f2.22-contract-lock.md §8.1):
//
//   - No `supabase.from(...)` — frontend never reads or writes
//     business tables through `supabase-js`. Every product / image
//     metadata read/write goes through `apiRequest` → FastAPI.
//   - No `supabase.storage.list()` / `supabase.storage.download()` as
//     a business source of truth. The only storage call permitted is
//     `supabase.storage.from(bucket).uploadToSignedUrl(...)`.
//   - The service-role key never appears in the frontend bundle.
//   - The bucket and object_key the FastAPI sign endpoint returned
//     are echoed verbatim back to FastAPI on confirm — the backend
//     re-validates them.
//
// URL alignment with backend/app/api/routes/products.py (F2.22.4.F):
//
//   POST /products/{product_id}/image-upload-url
//   POST /products/{product_id}/images

import { apiRequest } from "@/api";
import { supabase } from "@/lib/supabase";

import type {
  Product,
  ProductImage,
  ProductImageConfirmRequest,
  ProductImageUploadUrlRequest,
  ProductImageUploadUrlResponse,
} from "./types";

/** Locked bucket for F2.22.4 product images. Mirrors the backend. */
export const PRODUCT_IMAGES_BUCKET = "product-images" as const;

/** Allowed content types — mirrors `app.services.storage.ALLOWED_CONTENT_TYPES`. */
export const ALLOWED_IMAGE_CONTENT_TYPES = [
  "image/jpeg",
  "image/png",
  "image/webp",
] as const;

/** Max client-side size — mirrors `app.services.storage.MAX_IMAGE_SIZE_BYTES`. */
export const MAX_IMAGE_SIZE_BYTES = 5 * 1024 * 1024;

/**
 * Raised when the Supabase Storage `uploadToSignedUrl` call fails.
 *
 * Wraps the supabase-js error so the hook can surface a single
 * exception type to the UI without leaking the raw client error. The
 * message is the supabase-js error message, which is safe to display
 * (no service-role key, no project URL).
 */
export class ProductImageUploadError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ProductImageUploadError";
  }
}

// --------------------------------------------------------------------- //
// 1. Ask FastAPI for a signed upload URL.
// --------------------------------------------------------------------- //

export interface RequestProductImageUploadUrlParams {
  productId: string;
  metadata: ProductImageUploadUrlRequest;
}

/**
 * `POST /products/{product_id}/image-upload-url`.
 *
 * Admin-only on the backend. The signed URL Supabase mints is short
 * lived (10 min in F2.22.4) — call this immediately before uploading.
 */
export function requestProductImageUploadUrl(
  params: RequestProductImageUploadUrlParams,
  signal?: AbortSignal,
): Promise<ProductImageUploadUrlResponse> {
  const path = `/products/${encodeURIComponent(params.productId)}/image-upload-url`;
  return apiRequest<ProductImageUploadUrlResponse>(path, {
    method: "POST",
    body: params.metadata,
    signal,
  });
}

// --------------------------------------------------------------------- //
// 2. Upload the file to Supabase Storage using the signed URL.
// --------------------------------------------------------------------- //

export interface UploadProductImageToSignedUrlParams {
  bucket: string;
  objectKey: string;
  signedUploadUrl: string;
  file: File;
}

function extractSignedUploadToken(signedUploadUrl: string): string {
  // Supabase signed-upload URLs carry the JWT in the `token=` query
  // string. supabase-js's `uploadToSignedUrl(path, token, file)`
  // wants the token by itself, not the full URL.
  try {
    const url = new URL(signedUploadUrl);
    const token = url.searchParams.get("token");
    if (token === null || token.length === 0) {
      throw new Error("missing token");
    }
    return token;
  } catch {
    throw new ProductImageUploadError(
      "Signed upload URL is malformed.",
    );
  }
}

/**
 * Uploads `file` to the `product-images` bucket using a backend-issued
 * signed upload URL. Returns nothing — success is the absence of
 * `ProductImageUploadError`.
 */
export async function uploadProductImageToSignedUrl(
  params: UploadProductImageToSignedUrlParams,
): Promise<void> {
  const token = extractSignedUploadToken(params.signedUploadUrl);
  const { error } = await supabase.storage
    .from(params.bucket)
    .uploadToSignedUrl(params.objectKey, token, params.file, {
      contentType: params.file.type,
      upsert: false,
    });
  if (error !== null) {
    throw new ProductImageUploadError(
      error.message || "Supabase Storage upload failed.",
    );
  }
}

// --------------------------------------------------------------------- //
// 3. Confirm metadata with FastAPI.
// --------------------------------------------------------------------- //

export interface ConfirmProductImageUploadParams {
  productId: string;
  body: ProductImageConfirmRequest;
}

/**
 * `POST /products/{product_id}/images`.
 *
 * Admin-only on the backend. Upserts the metadata row — re-confirming
 * for the same product replaces the existing row rather than creating
 * a duplicate (DB-enforced via `unique(product_id)`).
 */
export function confirmProductImageUpload(
  params: ConfirmProductImageUploadParams,
  signal?: AbortSignal,
): Promise<ProductImage> {
  const path = `/products/${encodeURIComponent(params.productId)}/images`;
  return apiRequest<ProductImage>(path, {
    method: "POST",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// 4. Clear the primary image (F2.26.3.A backend lifecycle).
// --------------------------------------------------------------------- //

export interface DeleteProductImageParams {
  productId: string;
}

/**
 * `DELETE /products/{product_id}/images`.
 *
 * Admin-only on the backend. Clears the product's primary image — both
 * the `public.product_images` metadata row and the storage object — and
 * returns the updated `Product` with `primary_image === null`.
 *
 * Idempotent backend-side: clearing a product that has no image is a
 * success (200 with `primary_image: null`), not a 404. There is no
 * request body; the backend re-derives everything from the product id.
 */
export function deleteProductImage(
  params: DeleteProductImageParams,
  signal?: AbortSignal,
): Promise<Product> {
  const path = `/products/${encodeURIComponent(params.productId)}/images`;
  return apiRequest<Product>(path, { method: "DELETE", signal });
}
