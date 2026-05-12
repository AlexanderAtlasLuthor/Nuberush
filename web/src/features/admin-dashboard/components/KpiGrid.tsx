// F2.19.5: KPI grid for the admin dashboard.
//
// Renders the six locked KPIs over backend-provided values from
// `AdminDashboardSummary`. NO aggregation — every cell pulls a
// value from a path inside `summary`. Zero values render as `0`,
// not as "—" or blank.
//
// Drill-down targets (F2.19.5 prompt §A):
//   - Total stores  / Active stores → /app/admin/stores
//   - Total users                    → /app/admin/users
//   - Low-stock items                → /app/admin/inventory
//   - Open orders                    → /app/admin/orders
//   - Compliance blockers            → /app/admin/audit
//                                       (the global audit feed is
//                                        where product compliance
//                                        events surface today)
//
// "Operations CTA" is rendered separately in AdminDashboardPage,
// not here, so this component stays a pure 6-cell grid.

import type { AdminDashboardSummary } from "../types";
import { KpiCard } from "./KpiCard";

export interface KpiGridProps {
  summary: AdminDashboardSummary;
}

export function KpiGrid({ summary }: KpiGridProps) {
  return (
    <div
      className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3"
      data-testid="admin-dashboard-kpi-grid"
    >
      <KpiCard
        title="Total stores"
        value={summary.stores.total}
        description={`${summary.stores.inactive} inactive`}
        to="/app/admin/stores"
        data-testid="kpi-stores-total"
      />
      <KpiCard
        title="Active stores"
        value={summary.stores.active}
        to="/app/admin/stores"
        data-testid="kpi-stores-active"
      />
      <KpiCard
        title="Total users"
        value={summary.users.total}
        description={`${summary.users.active} active`}
        to="/app/admin/users"
        data-testid="kpi-users-total"
      />
      <KpiCard
        title="Low-stock items"
        value={summary.inventory.low_stock_count}
        description="Items at or below reorder threshold"
        to="/app/admin/inventory"
        data-testid="kpi-inventory-low-stock"
      />
      <KpiCard
        title="Open orders"
        value={summary.orders.open_count}
        description="Pending through out-for-delivery"
        to="/app/admin/orders"
        data-testid="kpi-orders-open"
      />
      <KpiCard
        title="Compliance blockers"
        value={summary.compliance.blocked_count}
        description="Products blocked from sale"
        to="/app/admin/audit"
        data-testid="kpi-compliance-blocked"
      />
    </div>
  );
}
