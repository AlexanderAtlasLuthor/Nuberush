// F2.26.6.C: read-only Admin Regulatory alerts surface over the
// GET /admin/regulatory/alerts backend (F2.26.5) via the F2.26.6.B hooks.
//
// READ-ONLY by design for this subphase:
//   - useAdminRegulatoryAlerts(filters) only — no detail query, no mutations.
//   - No alert selection, no detail panel, no decision-trail panel.
//   - The "Review" affordance is a static disabled button (see the table /
//     mobile-card components); it opens nothing and mutates nothing.
//
// Architecture rules in force (mirroring AdminOperationsPage):
//   - No fetch, no apiRequest, no axios, no business logic.
//   - No useAuth / currentUser inspection, no role-based gating.
//   - No useStoreContext — regulatory alerts are global; product_id / notice_id
//     live inside the filters object.
//   - No useMutation, no useQueryClient, no setQueryData.
//   - No acknowledge / dismiss / resolve UI.
//   - No route registration, no nav item, no dashboard tile here.

import { useCallback, useState } from "react";
import { ShieldCheck } from "lucide-react";

import { getApiErrorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";

import { useAdminRegulatoryAlerts } from "../hooks";
import type { ComplianceAlertFilters } from "../types";
import { RegulatoryAlertsFilters } from "../components/RegulatoryAlertsFilters";
import { RegulatoryAlertsMobileCards } from "../components/RegulatoryAlertsMobileCards";
import { RegulatoryAlertsTable } from "../components/RegulatoryAlertsTable";
import { RegulatoryKpiCards } from "../components/RegulatoryKpiCards";

const DEFAULT_LIMIT = 25;

// Default snapshot used at first mount and on "Reset". Explicit limit/offset
// keep the cache key stable across remounts and let `withOffsetReset` work.
const DEFAULT_FILTERS: ComplianceAlertFilters = {
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
      data-testid="regulatory-pagination"
    >
      <p
        className="text-sm text-muted-foreground"
        data-testid="regulatory-pagination-range"
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
          data-testid="regulatory-pagination-prev"
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onNext}
          disabled={!canNext}
          data-testid="regulatory-pagination-next"
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
        Admin · Regulatory
      </p>
      <h1 className="mt-1.5 text-2xl font-semibold tracking-tight md:text-[28px]">
        Regulatory alerts
      </h1>
      <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground leading-relaxed">
        Review regulatory signals, product matches, and compliance
        recommendations before taking action. Recommendations are advisory —
        no change is applied here.
      </p>
    </header>
  );
}

export default function AdminRegulatoryPage() {
  const [filters, setFilters] =
    useState<ComplianceAlertFilters>(DEFAULT_FILTERS);

  const query = useAdminRegulatoryAlerts(filters);

  const limit = filters.limit ?? DEFAULT_LIMIT;
  const offset = filters.offset ?? 0;
  const total = query.data?.total ?? 0;
  const items = query.data?.items ?? [];

  const handlePrev = useCallback(() => {
    setFilters((prev) => ({
      ...prev,
      offset: Math.max(0, (prev.offset ?? 0) - (prev.limit ?? DEFAULT_LIMIT)),
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
      data-testid="admin-regulatory-page"
    >
      <PageHeader />

      <RegulatoryAlertsFilters
        filters={filters}
        onChange={setFilters}
        onReset={handleReset}
        disabled={query.isLoading || query.isFetching}
      />

      {query.isSuccess ? (
        <RegulatoryKpiCards total={total} pageItems={items} />
      ) : null}

      {query.isLoading ? (
        <LoadingState message="Loading regulatory alerts…" />
      ) : query.isError ? (
        <ErrorState
          title="Could not load regulatory alerts"
          message={getApiErrorMessage(query.error)}
          onRetry={() => {
            void query.refetch();
          }}
        />
      ) : items.length === 0 ? (
        <EmptyState
          icon={ShieldCheck}
          title="No regulatory alerts"
          message="No regulatory alerts match the current filters."
        />
      ) : (
        <>
          <RegulatoryAlertsTable alerts={items} />
          <RegulatoryAlertsMobileCards alerts={items} />
        </>
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
