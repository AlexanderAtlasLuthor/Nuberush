// F2.26.6.C: KPI cards for the regulatory alerts read surface.
//
// One genuinely-global card (Total matching filters = response.total, computed
// server-side before pagination) plus three page-derived counts. The
// page-derived cards are explicitly labelled "(this page)" so they are never
// mistaken for global aggregates — the backend list response does not carry
// per-status / per-severity totals, so we do NOT fabricate them.
//
// Read-only and presentational: no query, no mutation, no selection.

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import type { ComplianceAlert } from "../types";

interface KpiCardProps {
  label: string;
  value: number;
  testId: string;
  emphasis?: "default" | "danger" | "warning";
}

function KpiCard({ label, value, testId, emphasis = "default" }: KpiCardProps) {
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
          {value.toLocaleString()}
        </p>
      </CardContent>
    </Card>
  );
}

export interface RegulatoryKpiCardsProps {
  /** Total alerts matching the active filters (server-side, all pages). */
  total: number;
  /** The alerts on the current page only. */
  pageItems: ComplianceAlert[];
}

export function RegulatoryKpiCards({
  total,
  pageItems,
}: RegulatoryKpiCardsProps) {
  const openOnPage = pageItems.filter(
    (alert) => alert.status === "open",
  ).length;
  const highOrCriticalOnPage = pageItems.filter(
    (alert) => alert.severity === "high" || alert.severity === "critical",
  ).length;
  const holdOrBanOnPage = pageItems.filter(
    (alert) =>
      alert.recommended_action === "hold" ||
      alert.recommended_action === "ban",
  ).length;

  return (
    <div
      className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
      data-testid="regulatory-kpi-grid"
    >
      <KpiCard
        label="Total matching filters"
        value={total}
        testId="regulatory-kpi-total"
      />
      <KpiCard
        label="Open (this page)"
        value={openOnPage}
        testId="regulatory-kpi-open-page"
      />
      <KpiCard
        label="High / Critical (this page)"
        value={highOrCriticalOnPage}
        emphasis="danger"
        testId="regulatory-kpi-high-critical-page"
      />
      <KpiCard
        label="Hold / Ban recommended (this page)"
        value={holdOrBanOnPage}
        emphasis="warning"
        testId="regulatory-kpi-hold-ban-page"
      />
    </div>
  );
}
