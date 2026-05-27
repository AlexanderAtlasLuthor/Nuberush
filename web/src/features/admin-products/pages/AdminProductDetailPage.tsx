// F2.20.5: real Admin Product detail page over the existing
// product endpoints.
//
// Mounted at /app/admin/products/:productId. This is a NEW admin
// drill-down route that did not exist as a placeholder pre-F2.20.0;
// see contract §9.
//
// Reuses the canonical product detail components verbatim — there
// is no separate admin-only product detail backend endpoint, and
// inventing one would duplicate the existing /products/{id} surface.
// The only admin-specific difference is the back-link target
// (/app/admin/products) and the page-level "global admin" framing.
//
// Reused canonical pieces (F2.8.x):
//   - useProductQuery
//   - ProductDetailHeader     (name, brand, category, badges)
//   - ProductActionsBar       (Edit / Add variant / Deactivate)
//   - ProductCompliancePanel  (compliance state display)
//   - ProductVariantsTable    (variants list; owns its own fetch)
//   - ProductComplianceAuditPanel (audit log; owns its own fetch)
//
// Compliance review continues to flow through the existing canonical
// mutation `PATCH /products/{product_id}/compliance` that lives
// inside ProductDetailHeader / UpdateProductComplianceModal. F2.20.0
// §3 forbids a duplicate compliance review endpoint, and this page
// honors that by never adding one.
//
// Hard rules in force:
//   - No fetch, no apiRequest, no axios, no new backend endpoint.
//   - No useStoreContext — Product is global per F2.20.0 §4.
//   - No useAuth, no client-side role gating. Backend is the
//     security authority; non-admin callers see ApiError(403) which
//     surfaces as the error state.
//   - No client-side compliance derivation.

import { ArrowLeft, ShoppingBag } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { getApiErrorMessage } from "@/api";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import { Button } from "@/components/ui/button";

import { ProductActionsBar } from "@/features/products/components/ProductActionsBar";
import { ProductCompliancePanel } from "@/features/products/components/ProductCompliancePanel";
import { ProductComplianceAuditPanel } from "@/features/products/components/ProductComplianceAuditPanel";
import { ProductDetailHeader } from "@/features/products/components/ProductDetailHeader";
import { ProductVariantsTable } from "@/features/products/components/ProductVariantsTable";
import { useProductQuery } from "@/features/products/hooks";

import { AdminProductApprovalPanel } from "../components/AdminProductApprovalPanel";
import { ProductImagePanel } from "../components/ProductImagePanel";

const EM_DASH = "—";

function PageHeader({ productId }: { productId: string }) {
  return (
    <header className="flex flex-col gap-3">
      <Button variant="ghost" size="sm" asChild className="self-start">
        <Link
          to="/app/admin/products"
          data-testid="admin-product-detail-back"
        >
          <ArrowLeft className="mr-2 h-4 w-4" aria-hidden="true" />
          Back to Admin Products
        </Link>
      </Button>
      <p
        className="font-mono text-xs text-muted-foreground break-all"
        data-testid="admin-product-detail-id"
      >
        {productId}
      </p>
    </header>
  );
}

export default function AdminProductDetailPage() {
  const params = useParams<{ productId: string }>();
  const productId = params.productId ?? "";

  // Always called: the hook short-circuits via `enabled: id.length > 0`.
  // Variants / audit queries live inside their own panels so each
  // panel owns its own loading / error state independently.
  const productQuery = useProductQuery(productId);

  if (productId.length === 0) {
    return (
      <div
        className="p-6 md:p-8 space-y-6 max-w-7xl"
        data-testid="admin-product-detail-page"
      >
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
      <div
        className="p-6 md:p-8 space-y-6 max-w-7xl"
        data-testid="admin-product-detail-page"
      >
        <PageHeader productId={productId} />
        <LoadingState message="Loading product…" />
      </div>
    );
  }

  if (productQuery.isError) {
    return (
      <div
        className="p-6 md:p-8 space-y-6 max-w-7xl"
        data-testid="admin-product-detail-page"
      >
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
      <div
        className="p-6 md:p-8 space-y-6 max-w-7xl"
        data-testid="admin-product-detail-page"
      >
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
    <div
      className="p-6 md:p-8 space-y-6 max-w-7xl"
      data-testid="admin-product-detail-page"
    >
      <PageHeader productId={productId} />
      <ProductDetailHeader product={product} />
      <AdminProductApprovalPanel product={product} />
      <ProductImagePanel product={product} />
      <ProductActionsBar product={product} />
      <ProductCompliancePanel product={product} />
      <ProductVariantsTable productId={product.id} />
      <ProductComplianceAuditPanel productId={product.id} />
    </div>
  );
}
