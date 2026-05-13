// F2.20.5: real Admin Products oversight page over the F2.20.1 backend.
//
// Mounted at /app/admin/products. Replaces the F2.17/F2.18 placeholder
// with a real, contract-bound READ-ONLY admin products surface. Per
// F2.20.0 §6 the page renders backend-served products only — the
// frontend never derives compliance state, never invents rows.
//
// Wiring:
//   useAdminProductsQuery(filters)
//     -> AdminProductsFilters  (q/category/compliance/allowed_for_sale/is_active)
//     -> AdminProductsTable    (rows + drill-down to /app/admin/products/:id)
//     -> PaginationBar         (offset/limit over response.total)
//
// Architecture rules in force here (mirroring AdminOperationsPage /
// AdminDashboardPage):
//   - No fetch, no apiRequest, no axios, no business logic.
//   - No useAuth, no currentUser inspection, no role-based gating.
//     Backend is the security authority; non-admin callers get an
//     ApiError(403) which surfaces in the error state.
//   - No useStoreContext — Product is global per F2.20.0 §4; store-
//     specific availability lives on InventoryItem.
//   - No useMutation here — mutations live on the detail page via
//     the existing canonical components.
//   - No client-side compliance / queue generation.
//   - No fake rows, no placeholder data.
//   - No product media, reporting/export, or admin settings work.

import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";

import { useAdminProductsQuery } from "../hooks";
import type { AdminProductsFilters as AdminProductsFiltersValue } from "../types";
import { AdminProductsFilters } from "../components/AdminProductsFilters";
import { AdminProductsTable } from "../components/AdminProductsTable";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import { getApiErrorMessage } from "@/api";
import { ShoppingBag } from "lucide-react";

const DEFAULT_LIMIT = 50;

const DEFAULT_FILTERS: AdminProductsFiltersValue = {
  limit: DEFAULT_LIMIT,
  offset: 0,
};

interface PaginationBarProps {
  limit: number;
  offset: number;
  total: number;
  itemsLength: number;
  onPrev: () => void;
  onNext: () => void;
}

function PaginationBar({
  limit,
  offset,
  total,
  itemsLength,
  onPrev,
  onNext,
}: PaginationBarProps) {
  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  const rangeStart = total === 0 ? 0 : offset + 1;
  const rangeEnd = total === 0 ? 0 : Math.min(offset + itemsLength, total);

  return (
    <div
      className="flex items-center justify-between gap-2"
      data-testid="admin-products-pagination"
    >
      <p
        className="text-sm text-muted-foreground"
        data-testid="admin-products-pagination-range"
      >
        {total === 0
          ? "0 of 0"
          : `Showing ${rangeStart}–${rangeEnd} of ${total}`}
      </p>
      <div className="flex items-center gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={onPrev}
          disabled={!canPrev}
          data-testid="admin-products-pagination-prev"
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onNext}
          disabled={!canNext}
          data-testid="admin-products-pagination-next"
        >
          Next
        </Button>
      </div>
    </div>
  );
}

function PageHeader({ total }: { total: number | null }) {
  return (
    <header>
      <h1 className="text-xl font-semibold">Admin Products</h1>
      <p className="text-sm text-muted-foreground">
        Global product oversight. Read-only platform view of every
        product across the catalog, regardless of store. Compliance
        review and product edits happen on the per-product page;
        store-specific availability lives in inventory, not here.
      </p>
      {total !== null ? (
        <p
          className="text-sm text-muted-foreground mt-2"
          data-testid="admin-products-total"
        >
          {total === 1 ? "1 product" : `${total} products`}
        </p>
      ) : null}
    </header>
  );
}

export default function AdminProductsPage() {
  const [filters, setFilters] =
    useState<AdminProductsFiltersValue>(DEFAULT_FILTERS);

  const query = useAdminProductsQuery(filters);

  const limit = filters.limit ?? DEFAULT_LIMIT;
  const offset = filters.offset ?? 0;
  const total = query.data?.total ?? 0;
  const items = query.data?.items ?? [];

  const handlePrev = useCallback(() => {
    setFilters((prev) => ({
      ...prev,
      offset: Math.max(
        0,
        (prev.offset ?? 0) - (prev.limit ?? DEFAULT_LIMIT),
      ),
    }));
  }, []);

  const handleNext = useCallback(() => {
    setFilters((prev) => {
      const currentOffset = prev.offset ?? 0;
      const currentLimit = prev.limit ?? DEFAULT_LIMIT;
      const candidate = currentOffset + currentLimit;
      return candidate < (query.data?.total ?? 0)
        ? { ...prev, offset: candidate }
        : prev;
    });
  }, [query.data?.total]);

  const handleReset = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
  }, []);

  return (
    <div
      className="p-6 md:p-8 space-y-6 max-w-7xl"
      data-testid="admin-products-page"
    >
      <PageHeader total={query.isSuccess ? total : null} />

      <AdminProductsFilters
        filters={filters}
        onChange={setFilters}
        onReset={handleReset}
        disabled={query.isLoading || query.isFetching}
      />

      {query.isLoading ? (
        <LoadingState message="Loading products…" />
      ) : query.isError ? (
        <ErrorState
          title="Could not load admin products"
          message={getApiErrorMessage(query.error)}
          onRetry={() => {
            void query.refetch();
          }}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={ShoppingBag}
          title="No products"
          message="No products match the current filters across the platform."
        />
      ) : (
        <AdminProductsTable products={items} />
      )}

      {query.isSuccess ? (
        <PaginationBar
          limit={limit}
          offset={offset}
          total={total}
          itemsLength={items.length}
          onPrev={handlePrev}
          onNext={handleNext}
        />
      ) : null}
    </div>
  );
}
