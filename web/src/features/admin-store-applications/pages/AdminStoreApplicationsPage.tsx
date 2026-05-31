// F2.24.C7: Admin store-applications queue page.
//
// Mounted at /app/admin/applications under the existing AdminShell, so
// the admin route guard (ProtectedRoute) and admin sidebar apply with no
// extra gating here. The backend `GET /admin/store-applications` is
// admin-only and authoritative for access; this page surfaces the
// 401/403 path through the centralized ApiError handling in the table.
//
// Architecture rules (mirroring features/stores AdminStoresPage):
//   - No fetch, no Supabase. Hooks do the talking.
//   - useState only for filter + pagination state.
//   - No useAuth / role inspection. Backend is the source of truth.

import { useState } from "react";

import { Button } from "@/components/ui/button";

import { StoreApplicationsFilters } from "../components/StoreApplicationsFilters";
import { StoreApplicationsTable } from "../components/StoreApplicationsTable";
import { useAdminStoreApplicationsQuery } from "../hooks";
import type { StoreApplicationListFilters } from "../types";

const DEFAULT_LIMIT = 25;

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
      data-testid="store-applications-pagination"
    >
      <Button
        variant="outline"
        size="sm"
        onClick={onPrev}
        disabled={!canPrev}
        data-testid="store-applications-pagination-prev"
      >
        Previous
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={onNext}
        disabled={!canNext}
        data-testid="store-applications-pagination-next"
      >
        Next
      </Button>
    </div>
  );
}

export default function AdminStoreApplicationsPage() {
  const [filters, setFilters] = useState<StoreApplicationListFilters>({
    limit: DEFAULT_LIMIT,
    offset: 0,
  });

  const query = useAdminStoreApplicationsQuery(filters);

  const limit = filters.limit ?? DEFAULT_LIMIT;
  const offset = filters.offset ?? 0;
  const total = query.data?.total ?? 0;

  const handleFiltersChange = (next: StoreApplicationListFilters) => {
    // Any filter change resets pagination to the first page.
    setFilters({ ...next, offset: 0 });
  };

  const handlePrev = () => {
    setFilters((prev) => ({
      ...prev,
      offset: Math.max(0, (prev.offset ?? 0) - (prev.limit ?? DEFAULT_LIMIT)),
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
      data-testid="admin-store-applications-page"
    >
      <header>
        <h1 className="text-xl font-semibold">Store applications</h1>
        <p className="text-sm text-muted-foreground">
          Review merchant onboarding applications submitted through the public
          apply form. Approve to provision a store and owner, or reject with a
          reason.
        </p>
      </header>

      <StoreApplicationsFilters
        filters={filters}
        onChange={handleFiltersChange}
        disabled={query.isLoading}
      />

      <StoreApplicationsTable
        applications={query.data?.items ?? []}
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        onRetry={() => query.refetch()}
      />

      {query.data && query.data.items.length > 0 ? (
        <div className="flex items-center justify-between">
          <p
            className="text-sm text-muted-foreground"
            data-testid="store-applications-total"
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
