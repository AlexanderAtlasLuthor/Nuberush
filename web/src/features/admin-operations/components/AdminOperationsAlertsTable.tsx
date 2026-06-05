// F2.19.6 / Phase E: responsive presentational view for the admin
// operations alerts feed.
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
// Columns / card fields deliberately match the wire contract: the
// backend `AdminOperationsAlert` shape carries id, category,
// severity, store_id, entity_type, entity_id, summary, created_at.
// Every wire field is rendered; nothing is invented.
//
// Phase E — responsive layout:
//   - Desktop / tablet (>=md): the existing table is preserved with
//     polished spacing / typography. All pre-existing `data-testid`
//     hooks are kept intact (`admin-operations-alerts-table`,
//     `admin-operations-alert-row`, `admin-operations-row-*`).
//   - Mobile (<md): the same alerts render as a card stack. Each
//     card carries a distinct `admin-operations-alert-card` test-id
//     family so JSDOM-rendered desktop + mobile surfaces don't
//     collide for tests scoped to the desktop table.
//   - Loading / error / empty states render once for both surfaces.

import { ArrowRight, ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";

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
import { cn } from "@/lib/utils";

import type {
  AdminOperationsAlert,
  AdminOperationsAlertCategory,
  AdminOperationsAlertSeverity,
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

// Mobile-card severity tint. Mirrors the visual rhythm of the rest of
// the dashboard surface (see Phase C status pills). Used only inside
// this component's mobile cards so the standalone `AlertSeverityBadge`
// keeps its existing shadcn-variant look in the desktop table.
const MOBILE_SEVERITY_CLASS: Record<AdminOperationsAlertSeverity, string> = {
  low: "bg-secondary text-secondary-foreground",
  medium: "bg-primary/15 text-primary",
  high: "bg-destructive/15 text-destructive",
};

const MOBILE_SEVERITY_LABEL: Record<AdminOperationsAlertSeverity, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

// Locked label set for the five `AdminOperationsAlertCategory` values.
// Mirrors the `AlertCategoryBadge` LABEL exactly — duplicated here so
// the mobile cards can render the human-readable text inline without
// reaching for the standalone badge (which would also re-emit a
// `alert-category-{category}` test-id and collide with the desktop
// surface in JSDOM-rendered tests).
const MOBILE_CATEGORY_LABEL: Record<AdminOperationsAlertCategory, string> = {
  low_stock: "Low stock",
  aging_order: "Aging order",
  compliance_blocker: "Compliance blocker",
  inactive_store: "Inactive store",
  store_no_inventory: "Store has no inventory",
};

// Human-readable labels for the wire-shape entity type. The operator
// sees "Inventory item" rather than the raw `inventory_item` token;
// the underlying value sent to / received from the backend is never
// altered. Unknown values fall back to the raw token so a future
// backend addition renders verbatim rather than blank.
const ENTITY_TYPE_LABEL: Record<AdminOperationsAlert["entity_type"], string> = {
  store: "Store",
  inventory_item: "Inventory item",
  order: "Order",
  product: "Product",
};

function entityTypeLabel(value: AdminOperationsAlert["entity_type"]): string {
  return ENTITY_TYPE_LABEL[value] ?? value;
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

function DesktopAlertsTable({ alerts }: { alerts: AdminOperationsAlert[] }) {
  return (
    <div
      className="hidden md:block rounded-xl border border-border bg-card overflow-hidden"
      data-testid="admin-operations-alerts-table"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-[10px] font-semibold uppercase tracking-wider">
              Severity
            </TableHead>
            <TableHead className="text-[10px] font-semibold uppercase tracking-wider">
              Category
            </TableHead>
            <TableHead className="text-[10px] font-semibold uppercase tracking-wider">
              Summary
            </TableHead>
            <TableHead className="text-[10px] font-semibold uppercase tracking-wider">
              Store ID
            </TableHead>
            <TableHead className="text-[10px] font-semibold uppercase tracking-wider">
              Entity
            </TableHead>
            <TableHead className="text-[10px] font-semibold uppercase tracking-wider">
              Entity ID
            </TableHead>
            <TableHead className="text-[10px] font-semibold uppercase tracking-wider">
              Created At
            </TableHead>
            <TableHead className="text-right text-[10px] font-semibold uppercase tracking-wider">
              Drill-down
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {alerts.map((alert) => (
            <TableRow
              key={alert.id}
              data-testid="admin-operations-alert-row"
              data-alert-id={alert.id}
              className="transition-colors hover:bg-secondary/30"
            >
              <TableCell data-testid="admin-operations-row-severity">
                <AlertSeverityBadge severity={alert.severity} />
              </TableCell>
              <TableCell data-testid="admin-operations-row-category">
                <AlertCategoryBadge category={alert.category} />
              </TableCell>
              <TableCell
                className="max-w-md text-sm leading-snug"
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
              <TableCell
                className="text-sm"
                data-testid="admin-operations-row-entity-type"
              >
                {entityTypeLabel(alert.entity_type)}
              </TableCell>
              <TableCell data-testid="admin-operations-row-entity-id">
                <span
                  className="font-mono text-xs"
                  title={alert.entity_id}
                >
                  {shortId(alert.entity_id)}
                </span>
              </TableCell>
              <TableCell
                className="font-mono text-xs text-muted-foreground whitespace-nowrap"
                data-testid="admin-operations-row-created-at"
              >
                {formatTimestamp(alert.created_at)}
              </TableCell>
              <TableCell className="text-right">
                <Link
                  to={drillDownHref(alert.category, alert.store_id)}
                  className="inline-flex items-center gap-1 text-sm font-medium text-primary underline-offset-2 hover:underline"
                  data-testid="admin-operations-row-drilldown"
                >
                  Investigate
                  <ArrowRight className="h-3 w-3" aria-hidden="true" />
                </Link>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

function MobileAlertCardStack({
  alerts,
}: {
  alerts: AdminOperationsAlert[];
}) {
  return (
    <ul
      className="md:hidden space-y-3"
      data-testid="admin-operations-alerts-cards"
      aria-label="Operations alerts"
    >
      {alerts.map((alert) => {
        const severityLabel =
          MOBILE_SEVERITY_LABEL[alert.severity] ?? alert.severity;
        const severityClass =
          MOBILE_SEVERITY_CLASS[alert.severity] ??
          "bg-secondary text-secondary-foreground";
        const categoryLabel =
          MOBILE_CATEGORY_LABEL[alert.category] ?? alert.category;

        return (
          <li
            key={alert.id}
            className="rounded-xl border border-border bg-card p-4"
            data-testid="admin-operations-alert-card"
            data-alert-id={alert.id}
          >
            <div className="flex items-center gap-2 flex-wrap">
              <span
                className={cn(
                  "inline-flex items-center rounded-full px-2.5 py-0.5 text-[11px] font-semibold capitalize",
                  severityClass,
                )}
                data-testid="admin-operations-card-severity"
                aria-label={`Severity: ${severityLabel}`}
              >
                {severityLabel}
              </span>
              <span
                className="inline-flex items-center rounded-md border border-border px-2 py-0.5 text-[11px] font-medium text-foreground"
                data-testid="admin-operations-card-category"
              >
                {categoryLabel}
              </span>
              <span
                className="ml-auto text-[10px] font-mono text-muted-foreground"
                data-testid="admin-operations-card-created-at"
              >
                {formatTimestamp(alert.created_at)}
              </span>
            </div>
            <p
              className="mt-2.5 text-sm leading-snug"
              data-testid="admin-operations-card-summary"
            >
              {alert.summary}
            </p>
            <div className="mt-3 flex items-center justify-between gap-2 flex-wrap text-xs">
              <div className="text-muted-foreground inline-flex items-center gap-1.5 min-w-0">
                <span
                  className="font-mono"
                  data-testid="admin-operations-card-store-id"
                  title={alert.store_id ?? undefined}
                >
                  {alert.store_id === null ? "Global" : shortId(alert.store_id)}
                </span>
                <span aria-hidden="true">·</span>
                <span
                  className="truncate"
                  data-testid="admin-operations-card-entity-type"
                >
                  {entityTypeLabel(alert.entity_type)}
                </span>
                <span aria-hidden="true">·</span>
                <span
                  className="font-mono truncate"
                  data-testid="admin-operations-card-entity-id"
                  title={alert.entity_id}
                >
                  {shortId(alert.entity_id)}
                </span>
              </div>
              <Link
                to={drillDownHref(alert.category, alert.store_id)}
                className="inline-flex items-center gap-1 text-sm font-medium text-primary"
                data-testid="admin-operations-card-drilldown"
              >
                Investigate
                <ArrowRight className="h-3 w-3" aria-hidden="true" />
              </Link>
            </div>
          </li>
        );
      })}
    </ul>
  );
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
    <>
      <DesktopAlertsTable alerts={alerts} />
      <MobileAlertCardStack alerts={alerts} />
    </>
  );
}
