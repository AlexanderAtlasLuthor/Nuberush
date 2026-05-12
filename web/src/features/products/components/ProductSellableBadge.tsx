// F2.8.3: read-only sellable badge.
//
// Renders the result of `useProductSellableQuery` for a single product.
// CRITICAL: this component does NOT compute sellability. The backend
// owns the rule via `assert_product_sellable` and exposes the answer at
// `GET /products/{id}/sellable`:
//
//   - 200 with `{ product_id, sellable: true }`  → "Sellable"
//   - 422 (ApiError, status === 422)             → "Not sellable"
//   - 4xx/5xx other than 422, network error, etc → "Unknown" (we cannot
//                                                   honestly answer)
//
// We never branch on `is_active` / `allowed_for_sale` / `compliance_status`
// here — that would fork the contract.

import { ShieldAlert, ShieldCheck, ShieldQuestion } from "lucide-react";

import { ApiError } from "@/api";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useProductSellableQuery } from "../hooks";

interface ProductSellableBadgeProps {
  productId: string;
  className?: string;
}

export function ProductSellableBadge({
  productId,
  className,
}: ProductSellableBadgeProps) {
  const query = useProductSellableQuery(productId);

  if (query.isLoading) {
    return (
      <Badge
        variant="outline"
        className={cn(
          "border-transparent bg-neutral-100 text-neutral-700 hover:bg-neutral-100",
          "uppercase tracking-wide",
          className,
        )}
        data-testid="product-sellable-loading"
      >
        Checking…
      </Badge>
    );
  }

  if (query.isSuccess && query.data.sellable === true) {
    return (
      <Badge
        variant="outline"
        className={cn(
          "border-transparent bg-emerald-100 text-emerald-900 hover:bg-emerald-100",
          "uppercase tracking-wide inline-flex items-center gap-1",
          className,
        )}
        data-testid="product-sellable-yes"
      >
        <ShieldCheck className="h-3 w-3" aria-hidden="true" />
        Sellable
      </Badge>
    );
  }

  // 422 is the documented "not sellable" path — surfaced as ApiError
  // by the api-client wrapper. Anything else (404 missing product,
  // 5xx, network) we render as "Unknown" rather than guessing the
  // sellability bit ourselves.
  if (query.isError && query.error instanceof ApiError && query.error.status === 422) {
    return (
      <Badge
        variant="outline"
        className={cn(
          "border-transparent bg-red-100 text-red-900 hover:bg-red-100",
          "uppercase tracking-wide inline-flex items-center gap-1",
          className,
        )}
        data-testid="product-sellable-no"
      >
        <ShieldAlert className="h-3 w-3" aria-hidden="true" />
        Not sellable
      </Badge>
    );
  }

  return (
    <Badge
      variant="outline"
      className={cn(
        "border-transparent bg-neutral-200 text-neutral-700 hover:bg-neutral-200",
        "uppercase tracking-wide inline-flex items-center gap-1",
        className,
      )}
      data-testid="product-sellable-unknown"
    >
      <ShieldQuestion className="h-3 w-3" aria-hidden="true" />
      Unknown
    </Badge>
  );
}
