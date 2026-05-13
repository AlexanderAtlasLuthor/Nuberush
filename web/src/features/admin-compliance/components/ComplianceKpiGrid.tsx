// F2.20.6: KPI grid for the admin compliance overview.
//
// Pure presentational: receives the backend-computed
// `AdminComplianceSummary` and renders one card per KPI. Never
// derives blocker logic client-side; never infers compliance truth
// beyond displaying server values. The summary fields are 1:1 with
// the F2.20.2 backend response — adding a "computed" KPI here would
// be a contract drift.
//
// Read-only. No fetching, no auth/store context, no fake fallback
// values.

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import type { AdminComplianceSummary } from "../types";

export interface ComplianceKpiGridProps {
  summary: AdminComplianceSummary;
}

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

export function ComplianceKpiGrid({ summary }: ComplianceKpiGridProps) {
  const { products, queue, reviews } = summary;
  return (
    <div
      className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
      data-testid="compliance-kpi-grid"
    >
      <KpiCard
        label="Total products"
        value={products.total}
        testId="kpi-products-total"
      />
      <KpiCard
        label="Blocked products"
        value={products.blocked}
        emphasis="danger"
        testId="kpi-products-blocked"
      />
      <KpiCard
        label="Restricted"
        value={products.restricted}
        emphasis="warning"
        testId="kpi-products-restricted"
      />
      <KpiCard
        label="Banned"
        value={products.banned}
        emphasis="danger"
        testId="kpi-products-banned"
      />
      <KpiCard
        label="Not allowed for sale"
        value={products.not_allowed_for_sale}
        emphasis="warning"
        testId="kpi-products-not-allowed-for-sale"
      />
      <KpiCard
        label="Inactive products"
        value={products.inactive}
        testId="kpi-products-inactive"
      />
      <KpiCard
        label="Queue total"
        value={queue.total}
        emphasis="warning"
        testId="kpi-queue-total"
      />
      <KpiCard
        label="Recent reviews"
        value={reviews.recent_count}
        testId="kpi-reviews-recent-count"
      />
    </div>
  );
}
