// F2.22.4.G: admin product image upload panel.
// F2.26.3.C: adds local preview-before-save and a remove/clear action.
//
// Renders the current primary image (if any) and the admin-only image
// controls. Three flows, all admin-only and all backend-authoritative:
//
//   * Upload / change — the existing F2.22.4.F three-step pipeline:
//       1. FastAPI mints a signed upload URL.
//       2. supabase-js posts the binary via uploadToSignedUrl.
//       3. FastAPI upserts the public.product_images metadata row.
//   * Preview-before-save — when a file is picked, a local object-URL
//     preview is shown and NO backend call happens until the admin
//     clicks Upload. The object URL is revoked on file change / unmount.
//   * Remove — the F2.26.3.A `DELETE /products/{id}/images` endpoint,
//     which clears the metadata row + storage object and returns the
//     product with `primary_image === null`.
//
// The panel never reads from supabase.from(...). It never receives the
// service-role key. It never derives a public URL client-side — the URL
// it renders for the *current* image is `primary_image.public_url`
// straight from FastAPI. The *local preview* URL is an object URL for
// the not-yet-uploaded File and is always revoked.
//
// Cache invalidation lives in the hooks; this component is presentation.

import { useEffect, useRef, useState } from "react";

import { getApiErrorMessage } from "@/api";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import {
  ALLOWED_IMAGE_CONTENT_TYPES,
  MAX_IMAGE_SIZE_BYTES,
  useDeleteProductImage,
  useProductImageUpload,
} from "@/features/products/hooks";
import type { Product } from "@/features/products/types";

const ACCEPT_ATTR = ALLOWED_IMAGE_CONTENT_TYPES.join(",");

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} KB`;
  return `${(kb / 1024).toFixed(1)} MB`;
}

interface ProductImagePanelProps {
  product: Product;
}

export function ProductImagePanel({ product }: ProductImagePanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const uploadMutation = useProductImageUpload(product.id);
  const removeMutation = useDeleteProductImage(product.id);
  const primaryImage = product.primary_image ?? null;
  const currentImageUrl = primaryImage?.public_url ?? null;

  // Local preview-before-save. Creating an object URL for the picked
  // File lets the admin see exactly what they're about to upload with
  // NO backend call. The URL is revoked whenever the file changes (the
  // cleanup runs before the next effect) and on unmount, so we never
  // leak object URLs.
  useEffect(() => {
    if (selectedFile === null) {
      setPreviewUrl(null);
      return;
    }
    const url = URL.createObjectURL(selectedFile);
    setPreviewUrl(url);
    return () => {
      URL.revokeObjectURL(url);
    };
  }, [selectedFile]);

  function handleFileSelected(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    uploadMutation.reset();
    removeMutation.reset();
  }

  function clearSelection() {
    setSelectedFile(null);
    if (fileInputRef.current !== null) {
      fileInputRef.current.value = "";
    }
  }

  function handleUpload() {
    if (selectedFile === null) return;
    uploadMutation.mutate(
      { file: selectedFile },
      {
        // Drop the selection on success — the effect revokes the
        // object URL and the panel falls back to rendering the freshly
        // uploaded `primary_image` once the product query refetches.
        onSuccess: clearSelection,
      },
    );
  }

  function handleRemove() {
    removeMutation.mutate(undefined, {
      onSuccess: clearSelection,
    });
  }

  const isUploading = uploadMutation.isPending;
  const isRemoving = removeMutation.isPending;
  const isBusy = isUploading || isRemoving;

  const uploadError = uploadMutation.isError
    ? getApiErrorMessage(uploadMutation.error)
    : null;
  const removeError = removeMutation.isError
    ? getApiErrorMessage(removeMutation.error)
    : null;

  const hasCurrentImage = currentImageUrl !== null;
  const uploadLabel = hasCurrentImage ? "Replace image" : "Upload";

  return (
    <Card data-testid="admin-product-image-panel">
      <CardHeader>
        <CardTitle>Product image</CardTitle>
        <CardDescription>
          Primary image shown to the storefront. JPEG, PNG or WebP up to{" "}
          {Math.floor(MAX_IMAGE_SIZE_BYTES / (1024 * 1024))}&nbsp;MB.
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {previewUrl !== null ? (
          <div className="space-y-2">
            <img
              src={previewUrl}
              alt={`${product.name} selected image preview`}
              className="h-40 w-40 rounded-md border object-cover"
              data-testid="admin-product-image-local-preview"
            />
            <p
              className="text-xs text-muted-foreground"
              data-testid="admin-product-image-selected-meta"
            >
              {selectedFile !== null
                ? `${selectedFile.name} · ${formatBytes(selectedFile.size)} · not uploaded yet`
                : null}
            </p>
          </div>
        ) : currentImageUrl !== null ? (
          <img
            src={currentImageUrl}
            alt={`${product.name} primary image`}
            className="h-40 w-40 rounded-md border object-cover"
            data-testid="admin-product-image-preview"
          />
        ) : (
          <div
            className="flex h-40 w-40 items-center justify-center rounded-md border border-dashed text-sm text-muted-foreground"
            data-testid="admin-product-image-empty"
          >
            No image yet
          </div>
        )}

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPT_ATTR}
            onChange={handleFileSelected}
            disabled={isBusy}
            aria-label="Select product image"
            data-testid="admin-product-image-file-input"
            className="block text-sm file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-2 file:text-sm file:font-medium hover:file:bg-secondary/80"
          />
          <Button
            type="button"
            onClick={handleUpload}
            disabled={selectedFile === null || isBusy}
            data-testid="admin-product-image-upload-button"
          >
            {isUploading ? "Uploading…" : uploadLabel}
          </Button>
          {selectedFile !== null ? (
            <Button
              type="button"
              variant="ghost"
              onClick={clearSelection}
              disabled={isBusy}
              data-testid="admin-product-image-cancel-button"
            >
              Cancel
            </Button>
          ) : null}
          {hasCurrentImage && selectedFile === null ? (
            <Button
              type="button"
              variant="outline"
              onClick={handleRemove}
              disabled={isBusy}
              data-testid="admin-product-image-remove-button"
            >
              {isRemoving ? "Removing…" : "Remove image"}
            </Button>
          ) : null}
        </div>

        {uploadError !== null && (
          <Alert
            variant="destructive"
            role="alert"
            data-testid="admin-product-image-error"
          >
            <AlertDescription>{uploadError}</AlertDescription>
          </Alert>
        )}

        {removeError !== null && (
          <Alert
            variant="destructive"
            role="alert"
            data-testid="admin-product-image-remove-error"
          >
            <AlertDescription>{removeError}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
