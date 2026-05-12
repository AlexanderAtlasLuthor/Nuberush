// F2.18.3: Admin Stores list page.
//
// Mounted at /app/admin/stores. Replaces the F2.17 placeholder with a
// real, contract-bound list/create/lifecycle surface. The backend
// (F2.17 + F2.18.1 admin auth) is the single source of truth for who
// may list / create / deactivate / reactivate; this page surfaces the
// 401/403/422 results through the centralized ApiError path.
//
// Architecture rules in force here (mirroring features/users
// UsersPage.tsx and features/inventory InventoryPage.tsx):
//   - No fetch, no api calls. Hooks do the talking.
//   - useState only for filter state, pagination offset, and modal
//     selection.
//   - No useAuth / role inspection. Backend matrices are the single
//     source of truth.
//   - No fake stores, no client-side authorization.
//
// Pagination policy: same as features/inventory. `limit` is fixed at
// DEFAULT_LIMIT for this page; `offset` is owned in state and reset
// to 0 whenever filters change.

import { useState } from "react";
import { Plus } from "lucide-react";

import { Button } from "@/components/ui/button";

import { AdminStoresFilters } from "../components/AdminStoresFilters";
import { AdminStoresTable } from "../components/AdminStoresTable";
import { CreateStoreDialog } from "../components/CreateStoreDialog";
import { StoreLifecycleDialog } from "../components/StoreLifecycleDialog";
import { useAdminStoresQuery } from "../hooks";
import type { StoreListFilters, StoreProfile } from "../types";

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
      data-testid="admin-stores-pagination"
    >
      <Button
        variant="outline"
        size="sm"
        onClick={onPrev}
        disabled={!canPrev}
        data-testid="admin-stores-pagination-prev"
      >
        Previous
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={onNext}
        disabled={!canNext}
        data-testid="admin-stores-pagination-next"
      >
        Next
      </Button>
    </div>
  );
}

export default function AdminStoresPage() {
  const [filters, setFilters] = useState<StoreListFilters>({
    limit: DEFAULT_LIMIT,
    offset: 0,
  });
  const [openCreate, setOpenCreate] = useState(false);
  const [lifecycleTarget, setLifecycleTarget] =
    useState<StoreProfile | null>(null);

  const query = useAdminStoresQuery(filters);

  const limit = filters.limit ?? DEFAULT_LIMIT;
  const offset = filters.offset ?? 0;
  const total = query.data?.total ?? 0;

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
      data-testid="admin-stores-page"
    >
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Stores</h1>
          <p className="text-sm text-muted-foreground">
            Manage stores across the NubeRush platform.
          </p>
        </div>
        <Button
          size="sm"
          onClick={() => setOpenCreate(true)}
          data-testid="admin-stores-create-button"
        >
          <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
          Create store
        </Button>
      </header>

      <AdminStoresFilters
        filters={filters}
        onChange={setFilters}
        disabled={query.isLoading}
      />

      <AdminStoresTable
        stores={query.data?.items ?? []}
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        onRetry={() => query.refetch()}
        actions={(store) => (
          <Button
            type="button"
            variant={store.is_active ? "outline" : "default"}
            size="sm"
            onClick={() => setLifecycleTarget(store)}
            data-testid="admin-stores-row-lifecycle-button"
          >
            {store.is_active ? "Deactivate" : "Reactivate"}
          </Button>
        )}
      />

      {query.data && query.data.items.length > 0 ? (
        <div className="flex items-center justify-between">
          <p
            className="text-sm text-muted-foreground"
            data-testid="admin-stores-total"
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

      <CreateStoreDialog
        open={openCreate}
        onOpenChange={setOpenCreate}
      />

      <StoreLifecycleDialog
        store={lifecycleTarget}
        open={lifecycleTarget !== null}
        onOpenChange={(open) => {
          if (!open) setLifecycleTarget(null);
        }}
      />
    </div>
  );
}
