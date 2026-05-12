// F2.18.5: real Admin Orders page over the F2.18.1B global feed.
//
// Mounted at /app/admin/orders. Replaces the F2.17 placeholder with
// a real, contract-bound READ-ONLY list. Per F2.18 contract lock
// §9.3 the Admin Orders UI must not render mutation controls — no
// create / cancel / return / status-transition actions are exposed
// here. Existing store-scoped mutation hooks remain untouched.
//
// Wiring:
//   useAdminOrdersQuery(filters)
//     -> AdminOrdersFilters (controlled, 4-field admin shape)
//     -> AdminOrdersTable (presentational, no row actions)
//
// `q` is intentionally NOT exposed (F2.18.1B contract amendment —
// Order has no clean text-search target).
//
// Architecture rules in force here (mirroring features/inventory
// AdminInventoryPage):
//   - No fetch, no axios, no Zustand, no business logic.
//   - No useAuth, no currentUser inspection, no role-based gating.
//   - No useStoreContext — the admin global feed is store-agnostic.
//   - No mutation hooks. No mutation buttons.
//   - No client-side merging, sorting, or aggregation.
//   - No fake rows.

import { useState } from "react";

import { Button } from "@/components/ui/button";

import { AdminOrdersFilters } from "../components/AdminOrdersFilters";
import { AdminOrdersTable } from "../components/AdminOrdersTable";
import { useAdminOrdersQuery } from "../hooks";
import type { AdminOrdersFilters as AdminOrdersFiltersType } from "../types";

const DEFAULT_LIMIT = 50;

const DEFAULT_FILTERS: AdminOrdersFiltersType = {
  limit: DEFAULT_LIMIT,
  offset: 0,
};

interface PaginationBarProps {
  limit: number;
  offset: number;
  total: number;
  onPrev: () => void;
  onNext: () => void;
}

function PaginationBar({
  limit,
  offset,
  total,
  onPrev,
  onNext,
}: PaginationBarProps) {
  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  return (
    <div
      className="flex items-center justify-end gap-2"
      data-testid="admin-orders-pagination"
    >
      <Button
        variant="outline"
        size="sm"
        onClick={onPrev}
        disabled={!canPrev}
        data-testid="admin-orders-pagination-prev"
      >
        Previous
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={onNext}
        disabled={!canNext}
        data-testid="admin-orders-pagination-next"
      >
        Next
      </Button>
    </div>
  );
}

function PageHeader() {
  return (
    <header>
      <h1 className="text-xl font-semibold">Orders</h1>
      <p className="text-sm text-muted-foreground">
        Orders across every store in the NubeRush platform.
        Read-only — operate on orders from a store context.
      </p>
    </header>
  );
}

export default function AdminOrdersPage() {
  const [filters, setFilters] =
    useState<AdminOrdersFiltersType>(DEFAULT_FILTERS);

  const query = useAdminOrdersQuery(filters);

  const limit = filters.limit ?? DEFAULT_LIMIT;
  const offset = filters.offset ?? 0;
  const total = query.data?.total ?? 0;
  const items = query.data?.items ?? [];

  const handlePrev = () => {
    setFilters((prev) => ({
      ...prev,
      offset: Math.max(
        0,
        (prev.offset ?? 0) - (prev.limit ?? DEFAULT_LIMIT),
      ),
    }));
  };

  const handleNext = () => {
    setFilters((prev) => {
      const currentOffset = prev.offset ?? 0;
      const currentLimit = prev.limit ?? DEFAULT_LIMIT;
      const candidate = currentOffset + currentLimit;
      return candidate < total ? { ...prev, offset: candidate } : prev;
    });
  };

  return (
    <div
      className="p-6 md:p-8 space-y-6 max-w-7xl"
      data-testid="admin-orders-page"
    >
      <PageHeader />

      <AdminOrdersFilters
        filters={filters}
        onChange={setFilters}
        disabled={query.isLoading || query.isFetching}
      />

      <AdminOrdersTable
        orders={items}
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        onRetry={() => {
          void query.refetch();
        }}
      />

      {items.length > 0 ? (
        <div className="flex items-center justify-between">
          <p
            className="text-sm text-muted-foreground"
            data-testid="admin-orders-total"
          >
            Total: {total}
          </p>
          <PaginationBar
            limit={limit}
            offset={offset}
            total={total}
            onPrev={handlePrev}
            onNext={handleNext}
          />
        </div>
      ) : null}
    </div>
  );
}
