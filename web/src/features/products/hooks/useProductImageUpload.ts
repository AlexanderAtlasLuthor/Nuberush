// F2.22.4.G: product image upload hook.
//
// Orchestrates the three-step admin flow:
//
//   1. POST /products/{id}/image-upload-url   (FastAPI)
//   2. supabase.storage.from(...).uploadToSignedUrl(...)
//   3. POST /products/{id}/images             (FastAPI metadata confirm)
//
// Step 3 runs ONLY when step 2 resolves. A failed Supabase upload
// short-circuits before any metadata write — keeping the
// public.product_images table consistent with what's actually in the
// bucket.
//
// Cache invalidation mirrors useApproveProductMutation / the other
// product-mutating hooks so any list/detail surface showing this
// product re-fetches the new `primary_image` value through FastAPI.

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { adminProductsQueryKeys } from "@/features/admin-products/hooks";

import {
  ALLOWED_IMAGE_CONTENT_TYPES,
  MAX_IMAGE_SIZE_BYTES,
  PRODUCT_IMAGES_BUCKET,
  ProductImageUploadError,
  confirmProductImageUpload,
  requestProductImageUploadUrl,
  uploadProductImageToSignedUrl,
} from "../storage";
import type { ProductImage } from "../types";
import { productsKeys } from "./queryKeys";

export interface UseProductImageUploadInput {
  file: File;
}

function assertAllowedFile(file: File): void {
  if (!file) {
    throw new ProductImageUploadError("No file selected.");
  }
  if (
    !ALLOWED_IMAGE_CONTENT_TYPES.includes(
      file.type as (typeof ALLOWED_IMAGE_CONTENT_TYPES)[number],
    )
  ) {
    throw new ProductImageUploadError(
      `Unsupported file type. Allowed: ${ALLOWED_IMAGE_CONTENT_TYPES.join(", ")}.`,
    );
  }
  if (file.size <= 0) {
    throw new ProductImageUploadError("File is empty.");
  }
  if (file.size > MAX_IMAGE_SIZE_BYTES) {
    throw new ProductImageUploadError(
      `File exceeds the ${MAX_IMAGE_SIZE_BYTES}-byte limit.`,
    );
  }
}

/**
 * Admin product image upload mutation.
 *
 * Client-side validation is convenience only. Backend (`require_admin`,
 * `app.services.storage`) remains authoritative — any payload the
 * frontend lets slip will still be rejected with a 400/422/403.
 */
export function useProductImageUpload(productId: string) {
  const queryClient = useQueryClient();

  return useMutation<ProductImage, Error, UseProductImageUploadInput>({
    mutationFn: async ({ file }) => {
      assertAllowedFile(file);

      const signed = await requestProductImageUploadUrl({
        productId,
        metadata: {
          filename: file.name,
          content_type: file.type,
          size_bytes: file.size,
        },
      });

      await uploadProductImageToSignedUrl({
        bucket: signed.bucket,
        objectKey: signed.object_key,
        signedUploadUrl: signed.signed_upload_url,
        file,
      });

      return confirmProductImageUpload({
        productId,
        body: {
          bucket: signed.bucket,
          object_key: signed.object_key,
        },
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: productsKeys.detail(productId),
      });
      queryClient.invalidateQueries({
        queryKey: productsKeys.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: adminProductsQueryKeys.lists(),
      });
    },
  });
}

// Re-export so call sites and tests can reuse the constants without
// reaching into the storage module directly.
export {
  ALLOWED_IMAGE_CONTENT_TYPES,
  MAX_IMAGE_SIZE_BYTES,
  PRODUCT_IMAGES_BUCKET,
};
