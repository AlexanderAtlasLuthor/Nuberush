// F2.8.4: product detail header.
// F2.8.5: adds the Update compliance action — opens the compliance
// modal which owns the mutation. The modal is conditionally mounted so
// `useUpdateComplianceMutation` is only called once the operator opens
// the dialog (no idle hook subscription on every detail render).
//
// Pure projection of the wire `Product` shape plus the live sellable
// check (delegated entirely to `ProductSellableBadge`). No derivations,
// no rule composition, no permission gates — every visible string and
// every badge state comes from a wire field or the backend's sellable
// endpoint. The Update compliance button is unconditionally visible;
// the backend is the source of truth for whether the caller is
// authorised (a 403 surfaces via the modal's inline error).

import { useState } from "react";
import { ShieldCheck } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Product } from "../types";

import { ProductComplianceBadge } from "./ProductComplianceBadge";
import { ProductSellableBadge } from "./ProductSellableBadge";
import { ProductStatusBadge } from "./ProductStatusBadge";
import { UpdateProductComplianceModal } from "./UpdateProductComplianceModal";

const EM_DASH = "—";

interface ProductDetailHeaderProps {
  product: Product;
}

export function ProductDetailHeader({ product }: ProductDetailHeaderProps) {
  const [openCompliance, setOpenCompliance] = useState(false);

  return (
    <header className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1
            className="text-2xl font-semibold"
            data-testid="product-detail-name"
          >
            {product.name}
          </h1>
          <p className="text-sm text-muted-foreground">
            <span data-testid="product-detail-brand">
              {product.brand ?? EM_DASH}
            </span>
            <span className="mx-2 text-muted-foreground/60" aria-hidden="true">
              ·
            </span>
            <span data-testid="product-detail-category">
              {product.category}
            </span>
          </p>
        </div>

        <Button
          variant="outline"
          size="sm"
          onClick={() => setOpenCompliance(true)}
          data-testid="product-detail-update-compliance"
        >
          <ShieldCheck className="mr-2 h-4 w-4" aria-hidden="true" />
          Update compliance
        </Button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <ProductComplianceBadge status={product.compliance_status} />
        <ProductStatusBadge isActive={product.is_active} />
        <Badge
          variant="outline"
          className={cn(
            "uppercase tracking-wide",
            product.allowed_for_sale
              ? "border-transparent bg-emerald-100 text-emerald-900 hover:bg-emerald-100"
              : "border-transparent bg-neutral-200 text-neutral-700 hover:bg-neutral-200",
          )}
          data-testid={
            product.allowed_for_sale
              ? "product-detail-allowed-yes"
              : "product-detail-allowed-no"
          }
        >
          {product.allowed_for_sale ? "Allowed" : "Not allowed"}
        </Badge>
        <ProductSellableBadge productId={product.id} />
      </div>

      {openCompliance ? (
        <UpdateProductComplianceModal
          open={openCompliance}
          onOpenChange={setOpenCompliance}
          product={product}
        />
      ) : null}
    </header>
  );
}
