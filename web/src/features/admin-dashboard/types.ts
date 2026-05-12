// F2.19.3: admin dashboard wire types.
//
// 1:1 mirror of the FastAPI admin dashboard contract. Field names and
// casing match the JSON over the wire exactly (snake_case). The
// schemas are owned by the backend feature module
// `backend/app/schemas/admin_dashboard.py` — do NOT camelCase here.
//
// Sources of truth (keep in lockstep):
//   - backend/app/schemas/admin_dashboard.py
//       AdminDashboardSummary, AdminDashboardStoresSummary,
//       AdminDashboardUsersSummary, AdminDashboardInventorySummary,
//       AdminDashboardOrdersSummary, AdminDashboardComplianceSummary
//   - backend/app/services/admin_dashboard.py
//       get_admin_dashboard_summary
//   - backend/app/api/routes/admin_dashboard.py
//       GET /admin/dashboard
//   - docs/f2.19-contract-lock.md §3.1
//
// Reuse decisions (do not duplicate canonical types):
//   - `OrderRead` and `OrderStatus` come from `@/features/orders/types`
//     unchanged. The dashboard `orders.recent` array carries the same
//     wire shape the orders module already serializes.
//   - `AuditEvent` comes from `@/features/audit/types` unchanged. The
//     dashboard `recent_audit` array carries the unified audit-feed
//     shape produced by the backend `list_admin_audit` service.
//   - `OrderStatus` doubles as the key type for `orders.by_status`;
//     `Record<OrderStatus, number>` matches the densified histogram
//     the backend service produces (every status present, zero-filled).

import type { AuditEvent } from "@/features/audit/types";
import type { OrderRead, OrderStatus } from "@/features/orders/types";

/**
 * Store population counts. Sourced server-side from `Store.is_active`.
 *
 * `total = active + inactive` is an invariant the backend enforces by
 * computing the three counts in one query; the wire shape mirrors that.
 */
export interface AdminDashboardStoresSummary {
  total: number;
  active: number;
  inactive: number;
}

/**
 * User population counts. Sourced server-side from `User.is_active`.
 *
 * `total >= active` because inactive users remain in the user table.
 */
export interface AdminDashboardUsersSummary {
  total: number;
  active: number;
}

/**
 * Inventory KPI. Sourced from the canonical low-stock predicate
 * `quantity_on_hand - quantity_reserved <= reorder_threshold`. The
 * frontend never recomputes this; it consumes the count verbatim.
 */
export interface AdminDashboardInventorySummary {
  low_stock_count: number;
}

/**
 * Order KPIs.
 *
 * - `open_count`: orders in the locked open set
 *   `{pending, accepted, preparing, ready, out_for_delivery}`. Sum is
 *   derived server-side from the same histogram below — the wire
 *   contract guarantees the two values agree.
 * - `by_status`: every `OrderStatus` member with its count; the
 *   backend densifies missing statuses to `0` so consumers don't have
 *   to handle a missing key.
 * - `recent`: bounded to 5 by the backend, ordered by
 *   `created_at DESC, id ASC`. The shape is `OrderRead` (reused).
 */
export interface AdminDashboardOrdersSummary {
  open_count: number;
  by_status: Record<OrderStatus, number>;
  recent: OrderRead[];
}

/**
 * Compliance KPI. Count of products blocked from sale, where blocked
 * means `allowed_for_sale = false` OR `compliance_status` is in the
 * blocking set (`banned`, `restricted`). Derived server-side; the
 * frontend never reproduces the predicate.
 */
export interface AdminDashboardComplianceSummary {
  blocked_count: number;
}

/**
 * Top-level response shape for `GET /admin/dashboard`.
 *
 * Bundles every KPI section plus the bounded recent audit tail.
 * Read-only and computed-on-request — no persistence sits behind this
 * shape; the backend derives every value on every call.
 *
 * `recent_audit` is the audit-feed projection (`AuditEvent`, reused
 * from the audit module). Bounded to 5 by the backend, ordered per
 * the existing global audit feed convention.
 */
export interface AdminDashboardSummary {
  stores: AdminDashboardStoresSummary;
  users: AdminDashboardUsersSummary;
  inventory: AdminDashboardInventorySummary;
  orders: AdminDashboardOrdersSummary;
  compliance: AdminDashboardComplianceSummary;
  recent_audit: AuditEvent[];
}
