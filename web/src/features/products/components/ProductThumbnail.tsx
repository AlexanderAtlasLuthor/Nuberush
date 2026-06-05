// F2.26.3.B: reusable, read-only product image display.
//
// Renders `Product.primary_image.public_url` verbatim (the URL is
// computed server-side from the locked `product-images` bucket — the
// frontend never derives it from `object_key`), or a clean placeholder
// when there is no image. If the image URL is set but fails to load,
// an `onError` handler swaps to an "Image unavailable" fallback so a
// dead URL never shows a broken-image glyph.
//
// Pure presentation: no fetching, no mutations, no business logic, no
// permission gating, no upload/delete controls. This component is
// display-only and is safe on both admin and store (read-only)
// surfaces.

import { useEffect, useState } from "react";
import { ImageIcon, ImageOff } from "lucide-react";

import { cn } from "@/lib/utils";
import type { ProductImage } from "../types";

export type ProductThumbnailSize = "sm" | "md" | "lg";

interface ProductThumbnailProps {
  /**
   * The product's primary image metadata, straight from the wire.
   * `null`/`undefined` (no image) renders the placeholder.
   */
  primaryImage?: ProductImage | null;
  /** Product name, used to compose accessible alt / aria-label text. */
  productName: string;
  /** Visual size. `sm` suits table rows; `lg` suits detail surfaces. */
  size?: ProductThumbnailSize;
  className?: string;
}

const FRAME_CLASSES: Record<ProductThumbnailSize, string> = {
  sm: "h-10 w-10",
  md: "h-16 w-16",
  lg: "h-40 w-40",
};

const ICON_CLASSES: Record<ProductThumbnailSize, string> = {
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-10 w-10",
};

const NO_IMAGE_LABEL = "No image yet";
const BROKEN_IMAGE_LABEL = "Image unavailable";

export function ProductThumbnail({
  primaryImage,
  productName,
  size = "sm",
  className,
}: ProductThumbnailProps) {
  const publicUrl = primaryImage?.public_url ?? null;
  const [broken, setBroken] = useState(false);

  // A fresh URL (e.g. after an image replace) deserves a fresh load
  // attempt — clear any prior broken state when the URL changes.
  useEffect(() => {
    setBroken(false);
  }, [publicUrl]);

  const showImage = publicUrl !== null && publicUrl !== "" && !broken;
  const frame = FRAME_CLASSES[size];

  if (showImage) {
    return (
      <img
        src={publicUrl}
        alt={`${productName} product image`}
        onError={() => setBroken(true)}
        className={cn(
          "shrink-0 rounded-md border border-border object-cover",
          frame,
          className,
        )}
        data-testid="product-thumbnail-image"
      />
    );
  }

  const label = broken ? BROKEN_IMAGE_LABEL : NO_IMAGE_LABEL;
  const showText = size === "lg";

  return (
    <div
      role="img"
      aria-label={`${productName}: ${label}`}
      className={cn(
        "flex shrink-0 flex-col items-center justify-center gap-1 rounded-md border border-dashed border-border bg-muted/30 text-center text-muted-foreground",
        frame,
        className,
      )}
      data-testid="product-thumbnail-placeholder"
      data-broken={broken ? "true" : "false"}
    >
      {broken ? (
        <ImageOff className={ICON_CLASSES[size]} aria-hidden="true" />
      ) : (
        <ImageIcon className={ICON_CLASSES[size]} aria-hidden="true" />
      )}
      {showText ? <span className="text-xs">{label}</span> : null}
    </div>
  );
}
