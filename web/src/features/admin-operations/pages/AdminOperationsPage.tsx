// F2.19.6: real Admin Operations Alerts page over the F2.19.2 backend.
//
// Mounted at /app/admin/operations. Replaces the F2.17 placeholder
// with a real, contract-bound READ-ONLY operations alerts surface.
// Per F2.19.0 §3.2 the page renders backend-computed alerts only —
// the frontend never generates an alert, never invents severity,
// never persists a state change.
//
// Wiring:
//   useAdminOperationsAlertsQuery(filters)
//     -> AdminOperationsFilters     (category/severity/store_id/aging_minutes)
//     -> AdminOperationsAlertsTable (rows + category drill-down)
//     -> PaginationBar              (offset/limit over response.total)
//
// Architecture rules in force here (mirroring AdminInventoryPage /
// AdminDashboardPage):
//   - No fetch, no apiRequest, no axios, no business logic.
//   - No useAuth, no currentUser inspection, no role-based gating.
//   - No useStoreContext — operations alerts are global / store-
//     agnostic; `store_id` lives inside the filters object.
//   - No useMutation, no useQueryClient, no setQueryData.
//   - No dashboard query — that's a separate feature.
//   - No acknowledge / dismiss / resolve / incident UI (F2.19.0 §2).
//   - No client-side alert generation, no merging, no sorting.
//   - No fake rows, no placeholder data.

import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";

import { useAdminOperationsAlertsQuery } from "../hooks";
import type { AdminOperationsAlertsFilters } from "../types";
import { AdminOperationsFilters } from "../components/AdminOperationsFilters";
import { AdminOperationsAlertsTable } from "../components/AdminOperationsAlertsTable";

const DEFAULT_LIMIT = 50;
const DEFAULT_AGING_MINUTES = 1440;

// Default snapshot used both at first mount and when the user
// clicks "Reset". Explicit `aging_minutes` here matches the backend
// default so the filter input is pre-populated and the cache key is
// stable across remounts.
const DEFAULT_FILTERS: AdminOperationsAlertsFilters = {
  limit: DEFAULT_LIMIT,
  offset: 0,
  aging_minutes: DEFAULT_AGING_MINUTES,
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
      data-testid="admin-operations-pagination"
    >
      <p
        className="text-sm text-muted-foreground"
        data-testid="admin-operations-pagination-range"
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
          data-testid="admin-operations-pagination-prev"
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onNext}
          disabled={!canNext}
          data-testid="admin-operations-pagination-next"
        >
          Next
        </Button>
      </div>
    </div>
  );
}

function PageHeader() {
  return (
    <header>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Admin · Operations
      </p>
      <h1 className="mt-1.5 text-2xl font-semibold tracking-tight md:text-[28px]">
        Operations alerts
      </h1>
      <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground leading-relaxed">
        Computed read-only operational signals: low stock, aging
        orders, compliance blockers, inactive stores, and stores
        with no inventory. Every alert is derived from existing data
        on each request — no persistence, no acknowledgement state.
      </p>
    </header>
  );
}

export default function AdminOperationsPage() {
  const [filters, setFilters] =
    useState<AdminOperationsAlertsFilters>(DEFAULT_FILTERS);

  const query = useAdminOperationsAlertsQuery(filters);

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
      data-testid="admin-operations-page"
    >
      <PageHeader />

      <AdminOperationsFilters
        filters={filters}
        onChange={setFilters}
        onReset={handleReset}
        disabled={query.isLoading || query.isFetching}
      />

      <AdminOperationsAlertsTable
        alerts={items}
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        onRetry={() => {
          void query.refetch();
        }}
      />

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
