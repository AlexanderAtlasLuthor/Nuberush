// F2.20.4: admin-compliance wire types.
//
// 1:1 mirror of the FastAPI admin-compliance contract introduced in
// F2.20.2 — see backend/app/schemas/admin_compliance.py
// (AdminComplianceSummary, AdminComplianceProductsListResponse) and
// backend/app/api/routes/admin_compliance.py (GET /admin/compliance,
// GET /admin/compliance/products).
//
// Hard rules baked in:
//   - Product, ProductComplianceStatus and ProductComplianceAuditLog
//     are reused from the canonical products feature. Duplicating
//     those types here would create a drift risk between the admin
//     compliance oversight surface and the regular product contract;
//     the two MUST stay aligned.
//   - No store_id field anywhere. F2.20.0 §4 locks Product as a
//     global resource; store-specific availability lives on
//     InventoryItem, not on the compliance queue.
//   - No workflow / incident / task types. F2.20.0 §12 forbids
//     persisted compliance workflow state; the frontend MUST NOT
//     define types that imply that state exists.
//   - No business logic, no derived flags, no UI permission state.
//     This module exists purely to type the wire.

import type {
  Product,
  ProductComplianceAuditLog,
  ProductComplianceStatus,
} from "@/features/products/types";

// Re-export canonical product types so admin-compliance consumers
// don't have to reach into the products feature directly.
export type {
  Product,
  ProductComplianceAuditLog,
  ProductComplianceStatus,
};

// --------------------------------------------------------------------- //
// GET /admin/compliance — summary shape
// --------------------------------------------------------------------- //

/**
 * Product population counts by compliance / sale state.
 *
 * Counts can overlap conceptually (a banned product is also
 * `not_allowed_for_sale` and is included in `blocked`). Each field is
 * an independent category count produced server-side from a single
 * aggregate query.
 */
export interface AdminComplianceProductCounts {
  total: number;
  allowed: number;
  restricted: number;
  banned: number;
  /**
   * Shared blocker predicate (F2.20.0 §8):
   * `allowed_for_sale == false OR compliance_status IN (restricted, banned)`.
   */
  blocked: number;
  allowed_for_sale: number;
  not_allowed_for_sale: number;
  inactive: number;
}

/**
 * Bounded recent tail of compliance review activity.
 *
 * `recent_count` is the size of the `recent` list returned by this
 * call (NOT a lifetime audit count). The backend bounds the list at
 * a service-owned cap and orders deterministically by
 * `created_at DESC, id DESC`.
 */
export interface AdminComplianceReviewSummary {
  recent_count: number;
  recent: ProductComplianceAuditLog[];
}

/**
 * Compliance queue cardinalities.
 *
 * - `total` is the blocker-predicate union (matches `products.blocked`).
 * - `banned`, `restricted`, and `not_allowed_for_sale` are independent
 *   category counts and may overlap.
 */
export interface AdminComplianceQueueCounts {
  total: number;
  banned: number;
  restricted: number;
  not_allowed_for_sale: number;
}

/**
 * Top-level response for `GET /admin/compliance`.
 *
 * Bundles product counts, the bounded recent-reviews tail, and queue
 * cardinalities. Backend-computed at request time — there is no
 * persisted compliance state.
 */
export interface AdminComplianceSummary {
  products: AdminComplianceProductCounts;
  reviews: AdminComplianceReviewSummary;
  queue: AdminComplianceQueueCounts;
}

// --------------------------------------------------------------------- //
// GET /admin/compliance/products — filters + envelope
// --------------------------------------------------------------------- //

/**
 * Filters accepted by `GET /admin/compliance/products` (F2.20.2).
 *
 * Every field is optional. Default queue rule (F2.20.0 §7): when
 * neither `compliance_status` nor `allowed_for_sale` is provided, the
 * backend restricts the result to products matching the shared
 * blocker predicate. Either explicit filter disables the default so
 * callers can intentionally inspect allowed / allowed_for_sale rows.
 *
 * There is intentionally NO `store_id` field — Product is global.
 * There is also no `category` filter on this endpoint (the backend
 * route deliberately omits it; if a caller needs to filter by
 * category, they should use `GET /admin/products` instead).
 */
export interface AdminComplianceProductsFilters {
  limit?: number;
  offset?: number;
  q?: string;
  compliance_status?: ProductComplianceStatus;
  allowed_for_sale?: boolean;
  is_active?: boolean;
}

/**
 * Paginated response envelope for `GET /admin/compliance/products`.
 *
 * `total` is the count of products matching the (default queue OR
 * explicit) filter BEFORE pagination is applied.
 */
export interface AdminComplianceProductsListResponse {
  items: Product[];
  total: number;
  limit: number;
  offset: number;
}
