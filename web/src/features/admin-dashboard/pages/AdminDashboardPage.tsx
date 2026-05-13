// F2.19.5 / Phase C: real Admin Dashboard page over the F2.19.1 backend.
//
// Mounted at /app/admin. Renders a contract-bound READ-ONLY admin
// overview. Per F2.19.0 §3.1 the dashboard renders backend-computed
// KPIs only — the frontend never aggregates, never invents a value,
// never densifies the histogram (the backend already does that).
//
// Wiring:
//   useAdminDashboardQuery()
//     -> KpiGrid                (6 platform KPI cards, bento layout)
//     -> OrdersByStatusPanel    (orders.by_status, densified server-side)
//     -> RecentOrdersPanel      (orders.recent, bounded to 5)
//     -> RecentActivityPanel    (recent_audit, bounded to 5)
//     -> Operations CTA         (link to /app/admin/operations,
//                                 a separate phase's UI)
//
// Architecture rules in force here (mirroring AdminInventoryPage /
// AdminAuditPage / AdminStoresPage):
//   - No fetch, no apiRequest, no axios, no business logic.
//   - No useAuth, no currentUser inspection, no role-based gating.
//   - No useStoreContext — admin dashboard is global / store-agnostic.
//   - No useMutation, no useQueryClient, no setQueryData.
//   - No operations-alerts query — that's F2.19.6's surface.
//   - No client-side merging, sorting, or aggregation.
//   - No fake rows, no placeholder data.

import { AlertCircle, ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

import { KpiGrid } from "../components/KpiGrid";
import { OrdersByStatusPanel } from "../components/OrdersByStatusPanel";
import { RecentActivityPanel } from "../components/RecentActivityPanel";
import { RecentOrdersPanel } from "../components/RecentOrdersPanel";
import { useAdminDashboardQuery } from "../hooks";

function PageHeader() {
  return (
    <header>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Admin · Dashboard
      </p>
      <h1 className="mt-1.5 text-2xl font-semibold tracking-tight md:text-[28px]">
        Platform overview
      </h1>
      <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground leading-relaxed">
        Platform-wide operational overview. Read-only — every value is
        computed by the backend from existing data on each request.
      </p>
    </header>
  );
}

function OperationsCta() {
  return (
    <section
      className="rounded-xl border border-border bg-card p-5 md:p-6"
      data-testid="admin-dashboard-operations-cta"
      aria-label="Operations alerts"
    >
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">Operations alerts</h2>
          <p className="mt-1 text-sm text-muted-foreground max-w-2xl">
            Low stock, aging orders, compliance blockers, inactive stores,
            and stores with no inventory live on the dedicated operations
            surface.
          </p>
        </div>
        <Button asChild className="shrink-0">
          <Link
            to="/app/admin/operations"
            data-testid="admin-dashboard-operations-link"
            className="inline-flex items-center gap-2"
          >
            Open operations
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </Button>
      </div>
    </section>
  );
}

function LoadingState() {
  return (
    <p
      className="text-sm text-muted-foreground"
      data-testid="admin-dashboard-loading"
    >
      Loading dashboard…
    </p>
  );
}

interface ErrorStateProps {
  error: unknown;
  onRetry: () => void;
}

function ErrorState({ error, onRetry }: ErrorStateProps) {
  const message =
    error instanceof Error && error.message
      ? error.message
      : "Unable to load dashboard.";
  return (
    <Alert
      variant="destructive"
      data-testid="admin-dashboard-error"
    >
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Could not load admin dashboard</AlertTitle>
      <AlertDescription className="flex flex-col gap-2">
        <span>{message}</span>
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          className="self-start"
          data-testid="admin-dashboard-retry"
        >
          Retry
        </Button>
      </AlertDescription>
    </Alert>
  );
}

export default function AdminDashboardPage() {
  const query = useAdminDashboardQuery();

  return (
    <div
      className="px-4 py-5 md:px-8 md:py-7 max-w-[1320px] mx-auto w-full space-y-5 md:space-y-6"
      data-testid="admin-dashboard-page"
    >
      <PageHeader />

      {query.isPending ? <LoadingState /> : null}

      {query.isError ? (
        <ErrorState
          error={query.error}
          onRetry={() => {
            void query.refetch();
          }}
        />
      ) : null}

      {query.isSuccess && query.data ? (
        <>
          <KpiGrid summary={query.data} />
          <OrdersByStatusPanel byStatus={query.data.orders.by_status} />
          <div className="grid gap-4 lg:grid-cols-2 md:gap-5">
            <RecentOrdersPanel orders={query.data.orders.recent} />
            <RecentActivityPanel events={query.data.recent_audit} />
          </div>
          <OperationsCta />
        </>
      ) : null}
    </div>
  );
}
