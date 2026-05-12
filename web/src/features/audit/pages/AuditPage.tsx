// F2.16.6: real Store Audit page over the unified F2.16 feed.
//
// Replaces the F2.10 "inventory logs hub" with a true unified feed
// page. The backend now exposes
// `GET /stores/{store_id}/audit` (F2.16.3), the frontend has the
// matching API/hook (F2.16.4), and the presentational components
// (F2.16.5) render filters and the merged event list. This page is
// the integration site:
//
//   useStoreContext()
//     -> currentStoreId
//   useStoreAuditQuery(currentStoreId, filters)
//     -> AuditFilters (controlled) + AuditFeed (presentational)
//
// Architecture rules (carried over from F2.10):
//   - No fetch, no axios, no Zustand, no business logic.
//   - No useAuth, no currentUser inspection, no role-based gating.
//     The backend authorises every read via
//     `require_staff_or_above` + `require_store_member`; the API
//     surfaces 401/403/404/400 through the centralized ApiError
//     path, and `AuditFeed` renders the failure honestly.
//   - useStoreContext IS used here at the page boundary (only) so
//     `AuditFilters` and `AuditFeed` stay store-agnostic and
//     reusable from a future admin store-picker. The components
//     themselves never read session state.
//   - No client-side merging, sorting, or aggregation. The backend
//     aggregator owns those rules; this page only forwards
//     `query.data.items` to `AuditFeed`.
//   - No fake rows, no "backend required" primary copy. The page
//     either shows real data, a clear no-store state, the loading
//     state, the error state, or a real empty state from
//     `AuditFeed`.

import { useState } from "react";
import { Store as StoreIcon } from "lucide-react";

import { EmptyState } from "@/components/common/empty-state";
import { useStoreContext } from "@/auth";

import { AuditFeed } from "../components/AuditFeed";
import { AuditFilters } from "../components/AuditFilters";
import { useStoreAuditQuery } from "../hooks";
import type { StoreAuditFilters } from "../types";

const DEFAULT_FILTERS: StoreAuditFilters = { limit: 50, offset: 0 };

function PageHeader() {
  return (
    <header>
      <h1 className="text-xl font-semibold">Audit</h1>
      <p className="text-sm text-muted-foreground">
        Review unified inventory, order, and compliance activity for
        this store.
      </p>
    </header>
  );
}

export default function AuditPage() {
  const { currentStoreId } = useStoreContext();
  const [filters, setFilters] = useState<StoreAuditFilters>(
    DEFAULT_FILTERS,
  );

  // The hook is always invoked so React hooks ordering stays
  // stable. Its internal `enabled` guard keeps the network idle
  // when `currentStoreId` is null/undefined/empty/whitespace, so
  // the no-store branch below just controls the UX.
  const query = useStoreAuditQuery(currentStoreId, filters);

  const hasStore =
    typeof currentStoreId === "string" &&
    currentStoreId.trim().length > 0;

  if (!hasStore) {
    return (
      <div
        className="p-6 md:p-8 space-y-6 max-w-7xl"
        data-testid="audit-page"
      >
        <PageHeader />
        <EmptyState
          icon={StoreIcon}
          title="Select a store"
          message="Choose a store to view its audit activity."
        />
      </div>
    );
  }

  return (
    <div
      className="p-6 md:p-8 space-y-6 max-w-7xl"
      data-testid="audit-page"
    >
      <PageHeader />
      <AuditFilters
        filters={filters}
        onChange={setFilters}
        disabled={query.isLoading || query.isFetching}
      />
      <AuditFeed
        events={query.data?.items ?? []}
        isLoading={query.isLoading}
        error={query.isError ? query.error : undefined}
        onRetry={() => {
          void query.refetch();
        }}
      />
    </div>
  );
}
