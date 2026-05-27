// F2.22.4.G: admin product image upload panel.
//
// Renders the current primary image (if any) and an admin-only upload
// control. The upload runs through the F2.22.4.F three-step flow:
//
//   1. FastAPI mints a signed upload URL.
//   2. supabase-js posts the binary via uploadToSignedUrl.
//   3. FastAPI upserts the public.product_images metadata row.
//
// The panel never reads from supabase.from(...). It never receives
// the service-role key. It never derives a public URL client-side —
// the URL it renders is `Product.primary_image.public_url` straight
// from FastAPI.
//
// Cache invalidation lives in the hook; this component is presentation.

import { useRef, useState } from "react";

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
  useProductImageUpload,
} from "@/features/products/hooks";
import type { Product } from "@/features/products/types";

const ACCEPT_ATTR = ALLOWED_IMAGE_CONTENT_TYPES.join(",");

interface ProductImagePanelProps {
  product: Product;
}

export function ProductImagePanel({ product }: ProductImagePanelProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);

  const mutation = useProductImageUpload(product.id);
  const primaryImage = product.primary_image ?? null;

  function handleFileSelected(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    mutation.reset();
  }

  function handleUpload() {
    if (selectedFile === null) return;
    mutation.mutate(
      { file: selectedFile },
      {
        onSuccess: () => {
          setSelectedFile(null);
          if (fileInputRef.current !== null) {
            fileInputRef.current.value = "";
          }
        },
      },
    );
  }

  const isUploading = mutation.isPending;
  const errorMessage = mutation.isError
    ? getApiErrorMessage(mutation.error)
    : null;

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
        {primaryImage !== null && primaryImage.public_url !== null ? (
          <img
            src={primaryImage.public_url}
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
            disabled={isUploading}
            aria-label="Select product image"
            data-testid="admin-product-image-file-input"
            className="block text-sm file:mr-3 file:rounded-md file:border-0 file:bg-secondary file:px-3 file:py-2 file:text-sm file:font-medium hover:file:bg-secondary/80"
          />
          <Button
            type="button"
            onClick={handleUpload}
            disabled={selectedFile === null || isUploading}
            data-testid="admin-product-image-upload-button"
          >
            {isUploading ? "Uploading…" : "Upload"}
          </Button>
        </div>

        {errorMessage !== null && (
          <Alert
            variant="destructive"
            role="alert"
            data-testid="admin-product-image-error"
          >
            <AlertDescription>{errorMessage}</AlertDescription>
          </Alert>
        )}
      </CardContent>
    </Card>
  );
}
