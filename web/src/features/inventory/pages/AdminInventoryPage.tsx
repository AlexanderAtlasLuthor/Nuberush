// F2.18.5: real Admin Inventory page over the F2.18.1A global feed.
//
// Mounted at /app/admin/inventory. Replaces the F2.17 placeholder
// with a real, contract-bound READ-ONLY list. Per F2.18 contract
// lock §9.3 the Admin Inventory UI must not render mutation
// controls — no receive / adjust / sell / reserve / damage / release
// / return / threshold / status actions are exposed here. Existing
// store-scoped mutation hooks remain untouched.
//
// Wiring:
//   useAdminInventoryQuery(filters)
//     -> AdminInventoryFilters (controlled, 6-field admin shape)
//     -> AdminInventoryTable (presentational, no row actions)
//
// Architecture rules in force here (mirroring features/audit
// AdminAuditPage and features/stores AdminStoresPage):
//   - No fetch, no axios, no Zustand, no business logic.
//   - No useAuth, no currentUser inspection, no role-based gating.
//   - No useStoreContext — the admin global feed is store-agnostic;
//     `store_id` lives inside the filters object as an optional
//     scope filter.
//   - No mutation hooks. No mutation buttons.
//   - No client-side merging, sorting, or aggregation. The backend
//     aggregator owns those rules.
//   - No fake rows.
//
// Pagination policy: `limit` is fixed at DEFAULT_LIMIT for this
// page; `offset` is owned in `filters` and reset to 0 by the filter
// component whenever a non-pagination field changes.

import { useState } from "react";

import { Button } from "@/components/ui/button";

import { AdminInventoryFilters } from "../components/AdminInventoryFilters";
import { AdminInventoryTable } from "../components/AdminInventoryTable";
import { useAdminInventoryQuery } from "../hooks";
import type { AdminInventoryFilters as AdminInventoryFiltersType } from "../types";

const DEFAULT_LIMIT = 100;

const DEFAULT_FILTERS: AdminInventoryFiltersType = {
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
      data-testid="admin-inventory-pagination"
    >
      <Button
        variant="outline"
        size="sm"
        onClick={onPrev}
        disabled={!canPrev}
        data-testid="admin-inventory-pagination-prev"
      >
        Previous
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={onNext}
        disabled={!canNext}
        data-testid="admin-inventory-pagination-next"
      >
        Next
      </Button>
    </div>
  );
}

function PageHeader() {
  return (
    <header>
      <h1 className="text-xl font-semibold">Inventory</h1>
      <p className="text-sm text-muted-foreground">
        Stock levels across every store in the NubeRush platform.
        Read-only — operate on inventory from a store context.
      </p>
    </header>
  );
}

export default function AdminInventoryPage() {
  const [filters, setFilters] =
    useState<AdminInventoryFiltersType>(DEFAULT_FILTERS);

  const query = useAdminInventoryQuery(filters);

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
      data-testid="admin-inventory-page"
    >
      <PageHeader />

      <AdminInventoryFilters
        filters={filters}
        onChange={setFilters}
        disabled={query.isLoading || query.isFetching}
      />

      <AdminInventoryTable
        items={items}
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
            data-testid="admin-inventory-total"
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
