// F2.19.6: presentational table for the admin operations alerts feed.
//
// Pure presentational. The parent supplies the rows; this component
// only renders. No fetching, no client-side alert generation, no
// permission logic.
//
// Read-only: NO acknowledge / dismiss / resolve / snooze / incident
// action buttons. Per F2.19.0 §2 (non-goals) the operations alerts
// surface is strictly observational. The drill-down link is the
// only navigation — it routes to the existing admin list/detail
// page where the operator can act on the underlying entity.
//
// Columns deliberately match the wire contract: the backend
// `AdminOperationsAlert` shape carries id, category, severity,
// store_id, entity_type, entity_id, summary, created_at. The table
// renders every wire field plus a derived Drill-down link; nothing
// is invented.

import { Link } from "react-router-dom";
import { ShieldAlert } from "lucide-react";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import type {
  AdminOperationsAlert,
  AdminOperationsAlertCategory,
} from "../types";
import { AlertCategoryBadge } from "./AlertCategoryBadge";
import { AlertSeverityBadge } from "./AlertSeverityBadge";

interface AdminOperationsAlertsTableProps {
  alerts: AdminOperationsAlert[];
  isLoading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyDescription?: string;
}

function readErrorMessage(error: unknown): string | undefined {
  if (error instanceof Error && error.message.length > 0) {
    return error.message;
  }
  return undefined;
}

function shortId(value: string): string {
  return value.length > 8 ? value.slice(0, 8) : value;
}

function formatTimestamp(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toISOString().replace("T", " ").replace(/:\d\d\.\d+Z$/, "Z");
}

/**
 * Drill-down route per category (F2.19.6 prompt §F). The link
 * targets the existing admin list/detail page where the operator
 * can investigate; no new routes are introduced.
 */
function drillDownHref(
  category: AdminOperationsAlertCategory,
  storeId: string | null,
): string {
  switch (category) {
    case "low_stock":
      return "/app/admin/inventory";
    case "aging_order":
      return "/app/admin/orders";
    case "compliance_blocker":
      return "/app/admin/audit";
    case "inactive_store":
    case "store_no_inventory":
      return storeId
        ? `/app/admin/stores/${encodeURIComponent(storeId)}`
        : "/app/admin/stores";
    default: {
      // Exhaustiveness guard: a new `AdminOperationsAlertCategory`
      // value would be a contract update that requires this switch
      // to grow. Falling back to the stores list keeps the UI
      // navigable in the meantime.
      const _exhaustive: never = category;
      void _exhaustive;
      return "/app/admin/stores";
    }
  }
}

export function AdminOperationsAlertsTable({
  alerts,
  isLoading = false,
  error,
  onRetry,
  emptyTitle = "No operational alerts",
  emptyDescription = "No alerts match the current filters across the platform.",
}: AdminOperationsAlertsTableProps) {
  if (isLoading) {
    return <LoadingState message="Loading alerts…" />;
  }

  if (error) {
    return (
      <ErrorState
        title="Could not load alerts"
        message={
          readErrorMessage(error) ??
          "An unexpected error occurred while loading alerts."
        }
        onRetry={onRetry}
      />
    );
  }

  if (alerts.length === 0) {
    return (
      <EmptyState
        icon={ShieldAlert}
        title={emptyTitle}
        message={emptyDescription}
      />
    );
  }

  return (
    <div
      className="rounded-md border border-border"
      data-testid="admin-operations-alerts-table"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Severity</TableHead>
            <TableHead>Category</TableHead>
            <TableHead>Summary</TableHead>
            <TableHead>Store ID</TableHead>
            <TableHead>Entity Type</TableHead>
            <TableHead>Entity ID</TableHead>
            <TableHead>Created At</TableHead>
            <TableHead className="text-right">Drill-down</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {alerts.map((alert) => (
            <TableRow
              key={alert.id}
              data-testid="admin-operations-alert-row"
              data-alert-id={alert.id}
            >
              <TableCell data-testid="admin-operations-row-severity">
                <AlertSeverityBadge severity={alert.severity} />
              </TableCell>
              <TableCell data-testid="admin-operations-row-category">
                <AlertCategoryBadge category={alert.category} />
              </TableCell>
              <TableCell
                className="max-w-md"
                data-testid="admin-operations-row-summary"
              >
                {alert.summary}
              </TableCell>
              <TableCell data-testid="admin-operations-row-store-id">
                {alert.store_id === null ? (
                  <span className="text-muted-foreground">Global</span>
                ) : (
                  <span
                    className="font-mono text-xs"
                    title={alert.store_id}
                  >
                    {shortId(alert.store_id)}
                  </span>
                )}
              </TableCell>
              <TableCell data-testid="admin-operations-row-entity-type">
                {alert.entity_type}
              </TableCell>
              <TableCell data-testid="admin-operations-row-entity-id">
                <span
                  className="font-mono text-xs"
                  title={alert.entity_id}
                >
                  {shortId(alert.entity_id)}
                </span>
              </TableCell>
              <TableCell data-testid="admin-operations-row-created-at">
                {formatTimestamp(alert.created_at)}
              </TableCell>
              <TableCell className="text-right">
                <Link
                  to={drillDownHref(alert.category, alert.store_id)}
                  className="text-sm underline-offset-2 hover:underline"
                  data-testid="admin-operations-row-drilldown"
                >
                  Investigate
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
