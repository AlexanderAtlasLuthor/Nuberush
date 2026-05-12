// F2.18.3: Admin Store detail page.
//
// Mounted at /app/admin/stores/:storeId. Replaces the F2.17 detail
// placeholder with a real, contract-bound summary + lifecycle action.
// Scope is deliberately tight per F2.18.3 brief:
//   - Show the wire-shape `StoreProfile` (name, code, timezone,
//     is_active, created_at, updated_at).
//   - Surface a single lifecycle action (deactivate when active,
//     reactivate when inactive).
//   - Back link to /app/admin/stores.
//
// Out of scope: store users, store inventory, store orders, store
// audit, store compliance, store metrics. Those become real surfaces
// later — or behind /app/store/* — and are not invented here.
//
// Architecture rules in force here:
//   - No fetch, no api calls. Hooks do the talking.
//   - `useAdminStoreQuery(storeId)` accepts null/undefined/"" — when
//     the URL has no `:storeId`, the hook short-circuits via its
//     `enabled` flag.
//   - No useAuth, no role checks. Backend RBAC is authoritative.

import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { getApiErrorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";

import { StoreLifecycleDialog } from "../components/StoreLifecycleDialog";
import { StoreStatusBadge } from "../components/StoreStatusBadge";
import { useAdminStoreQuery } from "../hooks";
import type { StoreProfile } from "../types";

interface DetailRowProps {
  label: string;
  children: React.ReactNode;
  testId?: string;
}

function DetailRow({ label, children, testId }: DetailRowProps) {
  return (
    <div className="flex items-baseline gap-3">
      <span className="text-sm text-muted-foreground w-28">{label}</span>
      <span className="text-sm" data-testid={testId}>
        {children}
      </span>
    </div>
  );
}

function StoreSummary({ store }: { store: StoreProfile }) {
  return (
    <div
      className="rounded-md border border-border p-6 space-y-3"
      data-testid="admin-store-summary"
    >
      <DetailRow label="Name" testId="admin-store-summary-name">
        <span className="font-medium">{store.name}</span>
      </DetailRow>
      <DetailRow label="Code" testId="admin-store-summary-code">
        <span className="font-mono text-xs">{store.code}</span>
      </DetailRow>
      <DetailRow label="Timezone" testId="admin-store-summary-timezone">
        <span className="font-mono text-xs">{store.timezone}</span>
      </DetailRow>
      <DetailRow label="Status">
        <StoreStatusBadge isActive={store.is_active} />
      </DetailRow>
      <DetailRow label="Created" testId="admin-store-summary-created">
        <span className="font-mono text-xs text-muted-foreground">
          {store.created_at}
        </span>
      </DetailRow>
      <DetailRow label="Updated" testId="admin-store-summary-updated">
        <span className="font-mono text-xs text-muted-foreground">
          {store.updated_at}
        </span>
      </DetailRow>
    </div>
  );
}

export default function AdminStoreDetailPage() {
  const { storeId } = useParams<{ storeId: string }>();
  const [lifecycleOpen, setLifecycleOpen] = useState(false);

  // useAdminStoreQuery handles null/undefined/"" safely via its
  // `enabled` flag — no manual guard needed before calling it.
  const query = useAdminStoreQuery(storeId);

  const renderBody = () => {
    if (!storeId || storeId.length === 0) {
      return (
        <EmptyState
          title="Missing store id"
          message="This page requires a store id in the URL."
        />
      );
    }
    if (query.isLoading) {
      return <LoadingState message="Loading store…" />;
    }
    if (query.isError) {
      return (
        <ErrorState
          title="Could not load store"
          message={getApiErrorMessage(query.error)}
          onRetry={() => query.refetch()}
        />
      );
    }
    if (!query.data) {
      return (
        <EmptyState
          title="No store data"
          message="The backend returned no store for this id."
        />
      );
    }

    const store = query.data;
    return (
      <>
        <StoreSummary store={store} />
        <div className="flex justify-end">
          <Button
            type="button"
            variant={store.is_active ? "destructive" : "default"}
            onClick={() => setLifecycleOpen(true)}
            data-testid="admin-store-detail-lifecycle-button"
          >
            {store.is_active ? "Deactivate store" : "Reactivate store"}
          </Button>
        </div>
        <StoreLifecycleDialog
          store={store}
          open={lifecycleOpen}
          onOpenChange={setLifecycleOpen}
        />
      </>
    );
  };

  return (
    <div
      className="p-6 md:p-8 space-y-6 max-w-3xl"
      data-testid="admin-store-detail-page"
    >
      <div>
        <Link
          to="/app/admin/stores"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
          data-testid="admin-store-detail-back-link"
        >
          <ArrowLeft className="h-4 w-4" aria-hidden="true" />
          Back to stores
        </Link>
      </div>

      <header>
        <h1 className="text-xl font-semibold">Store detail</h1>
        <p className="text-sm text-muted-foreground">
          Platform-level view of a single store.
        </p>
      </header>

      {renderBody()}
    </div>
  );
}
