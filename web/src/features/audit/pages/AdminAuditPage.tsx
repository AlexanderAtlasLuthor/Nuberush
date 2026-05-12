// F2.18.4: real Admin Audit page over the F2.17.5 global audit feed.
//
// Mounted at /app/admin/audit. Replaces the F2.17 placeholder with a
// real, contract-bound feed. The backend (F2.17.5) is the source of
// truth for who may read the global audit feed via `require_admin`;
// this page surfaces 401/403/404/422 through the centralized
// ApiError path.
//
// Wiring:
//
//   useAdminAuditQuery(filters)
//     -> AdminAuditFilters (controlled, 7-field admin shape)
//     -> AuditFeed (reused presentational; admin title/description)
//
// Architecture rules (mirroring features/stores AdminStoresPage and
// features/audit AuditPage):
//   - No fetch, no axios, no Zustand, no business logic.
//   - No useAuth, no currentUser inspection, no role-based gating.
//   - No useStoreContext — the admin global feed is store-agnostic;
//     `store_id` lives inside the filters object as an optional
//     scope filter.
//   - No client-side merging, sorting, or aggregation. The backend
//     aggregator owns those rules; this page forwards
//     `query.data.items` to AuditFeed verbatim.
//   - No fake rows. The page either shows real data, the loading
//     state, the error state, or AuditFeed's real empty state.
//
// Pagination policy: same as features/inventory and features/stores.
// `limit` is fixed at DEFAULT_LIMIT for this page; `offset` is owned
// in `filters` and reset to 0 by the filter component whenever a
// non-pagination field changes.

import { useState } from "react";

import { Button } from "@/components/ui/button";

import { AdminAuditFilters } from "../components/AdminAuditFilters";
import { AuditFeed } from "../components/AuditFeed";
import { useAdminAuditQuery } from "../hooks";
import type { AdminAuditFilters as AdminAuditFiltersType } from "../types";

const DEFAULT_LIMIT = 50;

const DEFAULT_FILTERS: AdminAuditFiltersType = {
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
      data-testid="admin-audit-pagination"
    >
      <Button
        variant="outline"
        size="sm"
        onClick={onPrev}
        disabled={!canPrev}
        data-testid="admin-audit-pagination-prev"
      >
        Previous
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={onNext}
        disabled={!canNext}
        data-testid="admin-audit-pagination-next"
      >
        Next
      </Button>
    </div>
  );
}

function PageHeader() {
  return (
    <header>
      <h1 className="text-xl font-semibold">Audit</h1>
      <p className="text-sm text-muted-foreground">
        Review unified inventory, order, and compliance activity
        across the NubeRush platform.
      </p>
    </header>
  );
}

export default function AdminAuditPage() {
  const [filters, setFilters] =
    useState<AdminAuditFiltersType>(DEFAULT_FILTERS);

  const query = useAdminAuditQuery(filters);

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
      data-testid="admin-audit-page"
    >
      <PageHeader />

      <AdminAuditFilters
        filters={filters}
        onChange={setFilters}
        disabled={query.isLoading || query.isFetching}
      />

      <AuditFeed
        events={items}
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        onRetry={() => {
          void query.refetch();
        }}
        title="Platform activity"
        description="Inventory, order, and compliance events across every store."
        emptyTitle="No audit events"
        emptyDescription="No platform activity recorded for the selected filters."
      />

      {items.length > 0 ? (
        <div className="flex items-center justify-between">
          <p
            className="text-sm text-muted-foreground"
            data-testid="admin-audit-total"
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
