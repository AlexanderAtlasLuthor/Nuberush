// F2.8.4: product detail page.
//
// Read-only in this subphase. Admin create/edit, compliance edits and
// variant create/edit/delete intentionally remain out of scope; the
// mutation hooks already exist (F2.8.2) and will plug in via dedicated
// modals in a later subphase.
//
// Rendering structure:
//   - PageHeader with back-link to /app/store/products
//   - ProductDetailHeader (name, brand, category, badges incl. sellable)
//   - ProductCompliancePanel (compliance fields from the product)
//   - ProductVariantsTable (owns its own data fetch — slow variants
//     do not block the header / compliance render)
//   - ProductComplianceAuditPanel (owns its own data fetch — admin-only
//     on the backend; non-admin callers see an ErrorState in-place)
//
// Hard rules in force:
//   - No fetch, no Zustand, no mutations, no compliance / sellable
//     derivations, no permission gates.
//   - useProductQuery is called unconditionally before any return
//     (Rules of Hooks intact); `enabled: productId.length > 0` inside
//     the hook keeps the network silent when the route param is
//     missing. The variants / audit / sellable queries live inside
//     their own panels so each panel handles its own loading / error /
//     empty state independently.
//   - No business logic: nullable fields render as em-dashes, no
//     calculations, no client-side formatting beyond raw display.

import { ArrowLeft, ShoppingBag } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { getApiErrorMessage } from "@/api";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import { Button } from "@/components/ui/button";

import { ProductActionsBar } from "../components/ProductActionsBar";
import { ProductCompliancePanel } from "../components/ProductCompliancePanel";
import { ProductComplianceAuditPanel } from "../components/ProductComplianceAuditPanel";
import { ProductDetailHeader } from "../components/ProductDetailHeader";
import { ProductVariantsTable } from "../components/ProductVariantsTable";
import { useProductQuery } from "../hooks";

const EM_DASH = "—";

function PageHeader({ productId }: { productId: string }) {
  return (
    <header className="flex flex-col gap-3">
      <Button variant="ghost" size="sm" asChild className="self-start">
        <Link to="/app/store/products" data-testid="product-detail-back">
          <ArrowLeft className="mr-2 h-4 w-4" aria-hidden="true" />
          Back to products
        </Link>
      </Button>
      <p
        className="font-mono text-xs text-muted-foreground break-all"
        data-testid="product-detail-id"
      >
        {productId}
      </p>
    </header>
  );
}

export default function ProductDetailPage() {
  // useParams is typed permissively; the param is `string | undefined`
  // because React Router cannot prove the URL matched a parent route
  // that defines `:productId`. We narrow defensively.
  const params = useParams<{ productId: string }>();
  const productId = params.productId ?? "";

  // Always called: the hook short-circuits via `enabled: productId.length > 0`.
  // The variants / audit / sellable queries live inside their own panels
  // so they only fire when this page actually mounts the panels (which
  // only happens after the product itself loads successfully).
  const productQuery = useProductQuery(productId);

  // ------------------------- render branches ------------------------- //

  if (productId.length === 0) {
    return (
      <div className="p-6 md:p-8 space-y-6 max-w-7xl">
        <PageHeader productId={EM_DASH} />
        <ErrorState
          title="Missing product id"
          message="The route did not provide a valid product id."
        />
      </div>
    );
  }

  if (productQuery.isLoading) {
    return (
      <div className="p-6 md:p-8 space-y-6 max-w-7xl">
        <PageHeader productId={productId} />
        <LoadingState message="Loading product…" />
      </div>
    );
  }

  if (productQuery.isError) {
    return (
      <div className="p-6 md:p-8 space-y-6 max-w-7xl">
        <PageHeader productId={productId} />
        <ErrorState
          title="Product failed to load"
          message={getApiErrorMessage(productQuery.error)}
          onRetry={() => productQuery.refetch()}
        />
      </div>
    );
  }

  if (!productQuery.data) {
    return (
      <div className="p-6 md:p-8 space-y-6 max-w-7xl">
        <PageHeader productId={productId} />
        <EmptyState
          icon={ShoppingBag}
          title="Product not found"
          message="No data was returned for this product."
        />
      </div>
    );
  }

  const product = productQuery.data;

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl">
      <PageHeader productId={productId} />
      <ProductDetailHeader product={product} />
      <ProductActionsBar product={product} />
      <ProductCompliancePanel product={product} />
      <ProductVariantsTable productId={product.id} />
      <ProductComplianceAuditPanel productId={product.id} />
    </div>
  );
}
