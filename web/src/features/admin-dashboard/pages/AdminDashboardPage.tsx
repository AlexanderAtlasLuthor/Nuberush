// F2.19.5: real Admin Dashboard page over the F2.19.1 backend.
//
// Mounted at /app/admin. Replaces the F2.17 placeholder with a real,
// contract-bound READ-ONLY admin overview. Per F2.19.0 §3.1 the
// dashboard renders backend-computed KPIs only — the frontend never
// aggregates, never invents a value, never densifies the histogram
// (the backend already does that).
//
// Wiring:
//   useAdminDashboardQuery()
//     -> KpiGrid                (6 platform KPI cards)
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

import { Link } from "react-router-dom";
import { AlertCircle } from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import { useAdminDashboardQuery } from "../hooks";
import { KpiGrid } from "../components/KpiGrid";
import { OrdersByStatusPanel } from "../components/OrdersByStatusPanel";
import { RecentOrdersPanel } from "../components/RecentOrdersPanel";
import { RecentActivityPanel } from "../components/RecentActivityPanel";

function PageHeader() {
  return (
    <header>
      <h1 className="text-xl font-semibold">Admin dashboard</h1>
      <p className="text-sm text-muted-foreground">
        Platform-wide operational overview. Read-only — every value is
        computed by the backend from existing data on each request.
      </p>
    </header>
  );
}

function OperationsCta() {
  return (
    <Card data-testid="admin-dashboard-operations-cta">
      <CardHeader>
        <CardTitle className="text-base font-semibold">
          Operations alerts
        </CardTitle>
        <CardDescription>
          Low stock, aging orders, compliance blockers, inactive stores,
          and stores with no inventory live on the dedicated operations
          surface.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <Button asChild>
          <Link
            to="/app/admin/operations"
            data-testid="admin-dashboard-operations-link"
          >
            Open operations
          </Link>
        </Button>
      </CardContent>
    </Card>
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
      className="p-6 md:p-8 space-y-6 max-w-7xl"
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
          <div className="grid gap-6 lg:grid-cols-2">
            <RecentOrdersPanel orders={query.data.orders.recent} />
            <RecentActivityPanel events={query.data.recent_audit} />
          </div>
          <OperationsCta />
        </>
      ) : null}
    </div>
  );
}
