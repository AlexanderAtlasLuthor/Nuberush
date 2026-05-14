// F2.20.3: admin-products wire types.
//
// 1:1 mirror of the FastAPI admin-products contract introduced in
// F2.20.1 — see backend/app/schemas/admin_products.py
// (AdminProductsListResponse) and backend/app/api/routes/admin_products.py
// (GET /admin/products).
//
// Hard rules baked in:
//   - Product, ProductVariant, ProductComplianceStatus and
//     ProductComplianceAuditLog are reused from the canonical products
//     feature. Duplicating those types here would create a drift risk
//     between the admin oversight surface and the regular product
//     contract; the two MUST stay aligned.
//   - No store_id field. F2.20.0 §4 locks Product as a global resource;
//     store-specific availability lives on InventoryItem.
//   - No business logic, no derived flags, no UI permission state. This
//     module exists purely to type the wire.

import type {
  Product,
  ProductApprovalStatus,
  ProductComplianceAuditLog,
  ProductComplianceStatus,
  ProductVariant,
} from "@/features/products/types";

// Re-export canonical product types so admin-products consumers don't
// have to reach into the products feature directly.
export type {
  Product,
  ProductApprovalStatus,
  ProductComplianceAuditLog,
  ProductComplianceStatus,
  ProductVariant,
};

/**
 * Filters accepted by `GET /admin/products` (F2.20.1).
 *
 * Every field is optional. Backend defaults are applied when a field
 * is omitted:
 *
 *   - limit  → 50  (ge=1, le=200)
 *   - offset → 0   (ge=0)
 *
 * `q` and `category` are trimmed on the client (and ignored when empty
 * after trimming) so a stray whitespace input does not become a wildcard
 * `%%` match on the server.
 *
 * There is intentionally NO `store_id` field — see module docstring.
 */
export interface AdminProductsFilters {
  limit?: number;
  offset?: number;
  /** Free-text search across name / brand / category / description. */
  q?: string;
  compliance_status?: ProductComplianceStatus;
  /** Optional approval-workflow filter. Admin can isolate the pending queue. */
  approval_status?: ProductApprovalStatus;
  allowed_for_sale?: boolean;
  is_active?: boolean;
  /** Optional category filter. Backend match is case-insensitive. */
  category?: string;
}

/**
 * Response envelope for `GET /admin/products`.
 *
 * Mirrors backend `AdminProductsListResponse`. `total` is the count of
 * products matching the filters BEFORE pagination is applied; `limit`
 * and `offset` echo the request so callers can render pagination
 * controls without re-deriving them.
 */
export interface AdminProductsListResponse {
  items: Product[];
  total: number;
  limit: number;
  offset: number;
}
