// F2.20.6: real Admin Compliance oversight page over the F2.20.2
// backend.
//
// Mounted at /app/admin/compliance. Replaces the F2.17/F2.18
// placeholder with a real, contract-bound READ-ONLY admin
// compliance surface. Per F2.20.0 §7 the page renders backend-
// computed values only — the frontend never derives queue
// membership, never invents KPI numbers, never invents review rows.
//
// Wiring:
//   useAdminComplianceSummaryQuery()
//     -> ComplianceKpiGrid          (8 KPIs from products/queue/reviews)
//     -> RecentComplianceReviews    (bounded recent audit tail)
//   useAdminComplianceProductsQuery(filters)
//     -> ComplianceFilters          (q/compliance_status/allowed_for_sale/is_active)
//     -> ComplianceQueueTable       (rows + drill-down to /app/admin/products/:id)
//     -> PaginationBar              (offset/limit over response.total)
//
// Architecture rules in force here (mirroring AdminOperationsPage /
// AdminProductsPage):
//   - No fetch, no apiRequest, no axios, no business logic.
//   - No useAuth, no currentUser inspection, no role-based gating.
//     Backend is the security authority; non-admin callers get an
//     ApiError(403) which surfaces in the error state.
//   - No useStoreContext — Product is global per F2.20.0 §4.
//   - No useMutation here — compliance updates flow through the
//     existing canonical `PATCH /products/{product_id}/compliance`
//     via the canonical UpdateProductComplianceModal on the
//     /app/admin/products/:productId detail page (F2.20.5).
//   - No client-side compliance / queue generation.
//   - No fake rows, no placeholder data.
//   - No category filter — the backend route does not accept it.
//   - No store_id filter, no workflow / incident / task UI.

import { useCallback, useState } from "react";

import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import { getApiErrorMessage } from "@/api";
import { ShieldCheck } from "lucide-react";

import {
  useAdminComplianceProductsQuery,
  useAdminComplianceSummaryQuery,
} from "../hooks";
import type { AdminComplianceProductsFilters } from "../types";
import { ComplianceFilters } from "../components/ComplianceFilters";
import { ComplianceKpiGrid } from "../components/ComplianceKpiGrid";
import { ComplianceQueueTable } from "../components/ComplianceQueueTable";
import { RecentComplianceReviews } from "../components/RecentComplianceReviews";

const DEFAULT_LIMIT = 50;

const DEFAULT_FILTERS: AdminComplianceProductsFilters = {
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
      data-testid="compliance-pagination"
    >
      <p
        className="text-sm text-muted-foreground"
        data-testid="compliance-pagination-range"
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
          data-testid="compliance-pagination-prev"
        >
          Previous
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={onNext}
          disabled={!canNext}
          data-testid="compliance-pagination-next"
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
      <h1 className="text-xl font-semibold">Admin Compliance</h1>
      <p className="text-sm text-muted-foreground">
        Global compliance oversight. KPI snapshot, recent reviews,
        and the queue of products currently blocked from sale —
        every value computed by the backend on each request.
        Compliance review and state changes happen on the
        per-product page through the existing audited mutation.
      </p>
    </header>
  );
}

export default function AdminCompliancePage() {
  const [filters, setFilters] =
    useState<AdminComplianceProductsFilters>(DEFAULT_FILTERS);

  const summaryQuery = useAdminComplianceSummaryQuery();
  const queueQuery = useAdminComplianceProductsQuery(filters);

  const limit = filters.limit ?? DEFAULT_LIMIT;
  const offset = filters.offset ?? 0;
  const total = queueQuery.data?.total ?? 0;
  const items = queueQuery.data?.items ?? [];

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
      return candidate < (queueQuery.data?.total ?? 0)
        ? { ...prev, offset: candidate }
        : prev;
    });
  }, [queueQuery.data?.total]);

  const handleReset = useCallback(() => {
    setFilters(DEFAULT_FILTERS);
  }, []);

  return (
    <div
      className="p-6 md:p-8 space-y-6 max-w-7xl"
      data-testid="admin-compliance-page"
    >
      <PageHeader />

      {summaryQuery.isLoading ? (
        <LoadingState message="Loading compliance summary…" />
      ) : summaryQuery.isError ? (
        <ErrorState
          title="Could not load compliance summary"
          message={getApiErrorMessage(summaryQuery.error)}
          onRetry={() => {
            void summaryQuery.refetch();
          }}
        />
      ) : summaryQuery.isSuccess && summaryQuery.data ? (
        <ComplianceKpiGrid summary={summaryQuery.data} />
      ) : null}

      <section className="space-y-3" aria-labelledby="compliance-queue-heading">
        <h2
          id="compliance-queue-heading"
          className="text-base font-semibold"
        >
          Compliance queue
        </h2>

        <ComplianceFilters
          filters={filters}
          onChange={setFilters}
          onReset={handleReset}
          disabled={queueQuery.isLoading || queueQuery.isFetching}
        />

        {queueQuery.isLoading ? (
          <LoadingState message="Loading compliance queue…" />
        ) : queueQuery.isError ? (
          <ErrorState
            title="Could not load compliance queue"
            message={getApiErrorMessage(queueQuery.error)}
            onRetry={() => {
              void queueQuery.refetch();
            }}
          />
        ) : items.length === 0 ? (
          <EmptyState
            icon={ShieldCheck}
            title="Queue is empty"
            message="No products match the current compliance filters across the platform."
          />
        ) : (
          <ComplianceQueueTable products={items} />
        )}

        {queueQuery.isSuccess ? (
          <PaginationBar
            limit={limit}
            offset={offset}
            total={total}
            itemsLength={items.length}
            onPrev={handlePrev}
            onNext={handleNext}
          />
        ) : null}
      </section>

      {summaryQuery.isSuccess && summaryQuery.data ? (
        <RecentComplianceReviews
          reviews={summaryQuery.data.reviews.recent}
          recentCount={summaryQuery.data.reviews.recent_count}
        />
      ) : null}
    </div>
  );
}
