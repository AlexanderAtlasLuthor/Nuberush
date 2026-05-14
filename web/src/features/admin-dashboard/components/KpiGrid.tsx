// F2.19.5 / Phase C: KPI bento grid for the admin dashboard.
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
// Phase C — bento layout:
//   "Open orders" is promoted to the hero tile (col-span-2 on lg)
//   because it is the most operational of the six metrics — every
//   other KPI is a population count, this one is work in flight.
//   The hero card uses the same `summary.orders.open_count` value
//   the satellite previously used; no new data is introduced.
//
// "Operations CTA" is rendered separately in AdminDashboardPage,
// not here, so this component stays a pure 6-cell grid.

import {
  Boxes,
  ClipboardCheck,
  ClipboardList,
  FileWarning,
  Store,
  Users,
} from "lucide-react";

import type { AdminDashboardSummary } from "../types";
import { KpiCard } from "./KpiCard";

export interface KpiGridProps {
  summary: AdminDashboardSummary;
}

export function KpiGrid({ summary }: KpiGridProps) {
  return (
    <div
      className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4"
      data-testid="admin-dashboard-kpi-grid"
    >
      <div className="sm:col-span-2 lg:col-span-2 lg:row-span-2">
        <KpiCard
          variant="hero"
          accent="primary"
          title="Open orders"
          value={summary.orders.open_count}
          description="Pending through out-for-delivery — orders currently in flight across every store."
          icon={ClipboardList}
          to="/app/admin/orders"
          data-testid="kpi-orders-open"
        />
      </div>
      <KpiCard
        title="Total stores"
        value={summary.stores.total}
        description={`${summary.stores.inactive} inactive`}
        icon={Store}
        to="/app/admin/stores"
        data-testid="kpi-stores-total"
      />
      <KpiCard
        accent="success"
        title="Active stores"
        value={summary.stores.active}
        icon={Store}
        to="/app/admin/stores"
        data-testid="kpi-stores-active"
      />
      <KpiCard
        title="Total users"
        value={summary.users.total}
        description={`${summary.users.active} active`}
        icon={Users}
        to="/app/admin/users"
        data-testid="kpi-users-total"
      />
      <KpiCard
        accent="warning"
        title="Low-stock items"
        value={summary.inventory.low_stock_count}
        description="At or below reorder threshold"
        icon={Boxes}
        to="/app/admin/inventory"
        data-testid="kpi-inventory-low-stock"
      />
      <KpiCard
        accent="destructive"
        title="Compliance blockers"
        value={summary.compliance.blocked_count}
        description="Products blocked from sale"
        icon={FileWarning}
        to="/app/admin/audit"
        data-testid="kpi-compliance-blocked"
      />
      {/* Pending approvals fills the rest of the bento row. On lg+ the
          tile spans 3 of the 4 grid columns so the row that started with
          "Compliance blockers" finishes flush against the hero — no
          dead space on the right edge. On sm the tile spans both
          columns so it doesn't look orphaned on the narrower layout. */}
      <div className="sm:col-span-2 lg:col-span-3">
        <KpiCard
          accent="primary"
          title="Pending approvals"
          value={summary.products.pending_approvals_count}
          description="Store-proposed products awaiting review"
          icon={ClipboardCheck}
          to="/app/admin/products?approval_status=pending"
          data-testid="kpi-products-pending-approvals"
        />
      </div>
    </div>
  );
}
