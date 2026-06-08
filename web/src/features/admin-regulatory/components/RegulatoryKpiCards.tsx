// F2.27.5: KPI cards for the regulatory alerts surface.
//
// All four cards are now GLOBAL, backend-computed counts from the
// `/admin/regulatory/aggregate` endpoint (dense-by-enum, computed before
// pagination) — NOT derived from the current page of rows. The component is
// purely presentational: it receives the aggregate (plus loading/error flags)
// and renders it. It never calls `.filter()` over page items and never labels
// a count "(this page)".
//
// The aggregate respects the SAME filters as the alert list, so "Total
// matching filters" and the three breakdowns always describe the same set the
// table is paging through — just globally rather than per page.

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import type { ComplianceAlertAggregate } from "../types";

interface KpiCardProps {
  label: string;
  /** Display value: a formatted number when known, or a placeholder. */
  display: string;
  testId: string;
  emphasis?: "default" | "danger" | "warning";
}

function KpiCard({ label, display, testId, emphasis = "default" }: KpiCardProps) {
  const tone =
    emphasis === "danger"
      ? "text-destructive"
      : emphasis === "warning"
        ? "text-amber-600 dark:text-amber-500"
        : "text-foreground";
  return (
    <Card data-testid={testId}>
      <CardHeader className="space-y-1 p-4">
        <CardTitle className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
          {label}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4 pt-0">
        <p
          className={`text-2xl font-semibold ${tone}`}
          data-testid={`${testId}-value`}
        >
          {display}
        </p>
      </CardContent>
    </Card>
  );
}

export interface RegulatoryKpiCardsProps {
  /** Backend aggregate for the active filters. Undefined while loading/error. */
  aggregate: ComplianceAlertAggregate | undefined;
  /** True while the aggregate query is in flight. */
  isLoading?: boolean;
  /** True when the aggregate query failed. */
  isError?: boolean;
}

// Neutral placeholder shown when the global counts are not available
// (loading or error) — never a fabricated zero, which would read as a real
// "no alerts" count.
const PLACEHOLDER = "—";

export function RegulatoryKpiCards({
  aggregate,
  isLoading = false,
  isError = false,
}: RegulatoryKpiCardsProps) {
  const fmt = (value: number): string => value.toLocaleString();

  const show = (value: number | undefined): string => {
    if (aggregate === undefined || value === undefined) return PLACEHOLDER;
    return fmt(value);
  };

  const total = show(aggregate?.total);
  const open = show(aggregate?.by_status.open);
  const highOrCritical =
    aggregate === undefined
      ? PLACEHOLDER
      : fmt(aggregate.by_severity.high + aggregate.by_severity.critical);
  const holdOrBan =
    aggregate === undefined
      ? PLACEHOLDER
      : fmt(
          aggregate.by_recommended_action.hold +
            aggregate.by_recommended_action.ban,
        );

  return (
    <div
      className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
      data-testid="regulatory-kpi-grid"
      data-loading={isLoading ? "true" : undefined}
      data-error={isError ? "true" : undefined}
    >
      <KpiCard
        label="Total matching filters"
        display={total}
        testId="regulatory-kpi-total"
      />
      <KpiCard
        label="Open alerts"
        display={open}
        testId="regulatory-kpi-open"
      />
      <KpiCard
        label="High / critical"
        display={highOrCritical}
        emphasis="danger"
        testId="regulatory-kpi-high-critical"
      />
      <KpiCard
        label="Hold / ban recommended"
        display={holdOrBan}
        emphasis="warning"
        testId="regulatory-kpi-hold-ban"
      />
    </div>
  );
}
