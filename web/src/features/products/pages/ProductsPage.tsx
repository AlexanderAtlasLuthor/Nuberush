// F2.8.3: real products list page.
//
// Store App products list mounted under /app/store/products. Read-only in
// this subphase: detail page, admin create/edit, compliance, and variant
// flows ship in later F2.8.x subphases.
//
// Architecture rules in force here (see brief):
//   - No fetch, no mutations, no Zustand, no business logic.
//   - useState only for local filter UX state.
//   - Data shape stays the wire shape — no client-side derivations,
//     no formatting beyond what shadcn primitives apply.
//   - Products are GLOBAL (not store-scoped); no useStoreContext lookup.
//   - All compliance / sellable / permission rules live server-side.

import { useState } from "react";
import { Plus, ShoppingBag } from "lucide-react";

import { getApiErrorMessage } from "@/api";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import { Button } from "@/components/ui/button";

import { useProductsQuery } from "../hooks";
import type { ProductComplianceStatus } from "../types";
import { ProductFilters } from "../components/ProductFilters";
import { ProductFormModal } from "../components/ProductFormModal";
import { ProductsTable } from "../components/ProductsTable";

interface PageHeaderProps {
  onCreate: () => void;
}

function PageHeader({ onCreate }: PageHeaderProps) {
  return (
    <header className="flex items-start justify-between gap-4">
      <div>
        <h1 className="text-xl font-semibold">Products</h1>
        <p className="text-sm text-muted-foreground">
          Catalog browser. Edit / deactivate / variant actions live on each
          product detail page.
        </p>
      </div>
      <Button
        size="sm"
        onClick={onCreate}
        data-testid="products-create-button"
      >
        <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
        Create product
      </Button>
    </header>
  );
}

export default function ProductsPage() {
  const [complianceStatus, setComplianceStatus] = useState<
    ProductComplianceStatus | undefined
  >(undefined);
  const [onlyActive, setOnlyActive] = useState(false);
  const [openCreate, setOpenCreate] = useState(false);

  const query = useProductsQuery({
    compliance_status: complianceStatus,
    only_active: onlyActive,
  });

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl">
      <PageHeader onCreate={() => setOpenCreate(true)} />

      <ProductFilters
        complianceStatus={complianceStatus}
        onlyActive={onlyActive}
        disabled={query.isLoading}
        onComplianceStatusChange={setComplianceStatus}
        onOnlyActiveChange={setOnlyActive}
      />

      {query.isLoading ? (
        <LoadingState message="Loading products…" />
      ) : query.isError ? (
        <ErrorState
          title="Products failed to load"
          message={getApiErrorMessage(query.error)}
          onRetry={() => query.refetch()}
        />
      ) : query.data && query.data.length === 0 ? (
        <EmptyState
          icon={ShoppingBag}
          title={
            complianceStatus !== undefined || onlyActive
              ? "No matching products"
              : "No products yet"
          }
          message={
            complianceStatus !== undefined || onlyActive
              ? "No products match the current filters."
              : "The catalog is empty. Use Create product above to add the first one."
          }
        />
      ) : query.data ? (
        <>
          <p
            className="text-sm text-muted-foreground"
            data-testid="products-total"
          >
            Showing {query.data.length}{" "}
            {query.data.length === 1 ? "product" : "products"}
          </p>
          <ProductsTable products={query.data} />
        </>
      ) : null}

      {openCreate ? (
        <ProductFormModal
          mode="create"
          open={openCreate}
          onOpenChange={setOpenCreate}
        />
      ) : null}
    </div>
  );
}
