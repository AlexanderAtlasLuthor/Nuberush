// F2.6.0: inventory wire types.
//
// 1:1 mirror of the FastAPI inventory contract. Field names and casing
// match the JSON over the wire exactly (snake_case). Do NOT camelCase
// here — that mapping, if ever needed, belongs in the UI layer.
//
// Sources of truth (do not diverge without updating both sides):
//   - backend/app/schemas/inventory.py
//       InventoryItemRead, InventoryProductSummary,
//       InventoryVariantSummary, InventoryLogRead,
//       AdjustStockRequest, ReceiveStockRequest,
//       InventoryItemListResponse
//   - backend/app/db/models.py
//       ComplianceStatus, InventoryStatus, InventoryMovementType
//
// Only read types and the two request shapes the F2.6.0 brief asks for
// are declared here. The remaining movement requests (damage, sale,
// reserve, release, return) ship in later subphases when the
// corresponding mutations are wired.

import type { PaginatedResponse } from "@/api/types";
import type { ProductSummary } from "@/features/products/types";

// --------------------------------------------------------------------- //
// Enums (string literal unions — exact wire values)
// --------------------------------------------------------------------- //

/** Source: app.db.models.ComplianceStatus. */
export type ComplianceStatus = "allowed" | "restricted" | "banned";

/** Source: app.db.models.InventoryStatus. */
export type InventoryStatus =
  | "available"
  | "reserved"
  | "sold"
  | "flagged"
  | "quarantined";

/**
 * Source: app.db.models.InventoryMovementType. Note `"return"` (no
 * trailing underscore) — Python uses `return_` because `return` is a
 * keyword, but the serialised wire value is the bare word.
 */
export type InventoryMovementType =
  | "receipt"
  | "adjustment"
  | "reservation"
  | "sale"
  | "cancellation"
  | "return"
  | "damage"
  | "compliance_hold";

// --------------------------------------------------------------------- //
// Enriched read shapes
// --------------------------------------------------------------------- //

/**
 * Curated product subset surfaced inside an inventory response.
 *
 * Re-exported from the products feature module so the wire shape has
 * a single canonical declaration (F2.8.7). The backend payload still
 * mirrors `InventoryProductSummary` from
 * `backend/app/schemas/inventory.py`; that schema is structurally
 * identical to the products `ProductSummary`, so consumers — including
 * `VariantSummary.product` below — share one TypeScript interface.
 */
export type { ProductSummary };

/**
 * Curated variant subset surfaced inside an inventory response, with
 * its parent product nested.
 *
 * Mirrors backend `InventoryVariantSummary`. There is intentionally
 * no `name` field on the wire: a variant is identified by its SKU
 * plus optional `flavor` / `size_label` modifiers — the UI composes
 * its own display label.
 */
export interface VariantSummary {
  id: string;
  sku: string;
  flavor: string | null;
  size_label: string | null;
  is_active: boolean;
  product: ProductSummary;
}

/**
 * Response shape for any endpoint returning a single inventory item.
 *
 * Mirrors backend `InventoryItemRead`. Quantities are NEVER mutated
 * through generic update calls; they only change via the dedicated
 * movement endpoints (receive, adjust, sale, etc.).
 *
 * Field naming follows the wire exactly:
 *   - quantity_on_hand   (NOT "stock")
 *   - quantity_reserved  (NOT "reserved_stock")
 *   - reorder_threshold  (NOT "threshold")
 */
export interface InventoryItem {
  id: string;
  store_id: string;
  variant_id: string;
  quantity_on_hand: number;
  quantity_reserved: number;
  reorder_threshold: number;
  status: InventoryStatus;
  last_counted_at: string | null;
  created_at: string;
  updated_at: string;
  variant: VariantSummary;
}

/**
 * Response shape for an inventory log entry. Append-only by
 * convention; there is no Create/Update counterpart.
 *
 * Mirrors backend `InventoryLogRead`. Field naming follows the wire
 * exactly:
 *   - performed_by_user_id  (NOT "user_id")
 *   - movement_type         (NOT "action_type")
 *   - quantity_delta        (signed; NOT "quantity")
 *   - quantity_after        (post-mutation balance; NOT "new_stock")
 * The wire does NOT carry a "previous_stock" field — callers compute
 * it as `quantity_after - quantity_delta` if needed.
 */
export interface InventoryLogEntry {
  id: string;
  inventory_item_id: string;
  store_id: string;
  variant_id: string;
  performed_by_user_id: string | null;
  movement_type: InventoryMovementType;
  quantity_delta: number;
  quantity_after: number;
  reason: string | null;
  reference_type: string | null;
  reference_id: string | null;
  created_at: string;
}

// --------------------------------------------------------------------- //
// Movement request bodies
// --------------------------------------------------------------------- //

/**
 * POST /inventory/{item_id}/receive — add stock from a supplier or
 * inbound transfer.
 *
 * Backend constraint: `quantity` must be > 0; `reason` is optional but
 * is rejected if provided as whitespace. `reference_type` and
 * `reference_id` must come paired or both null (DB CHECK on
 * inventory_logs).
 */
export interface ReceiveStockRequest {
  quantity: number;
  reason?: string | null;
  reference_type?: string | null;
  reference_id?: string | null;
}

/**
 * POST /inventory/{item_id}/adjust — signed adjustment.
 *
 * Backend constraints: `delta` must be a non-zero integer (positive
 * adds, negative removes; zero is rejected because adjustments must
 * change something). `reason` is mandatory and non-empty for
 * adjustments — the audit trail must explain why someone overrode
 * the count. Reference pair rule applies as in ReceiveStockRequest.
 */
export interface AdjustStockRequest {
  delta: number;
  reason: string;
  reference_type?: string | null;
  reference_id?: string | null;
}

/**
 * POST /inventory/{item_id}/damage — record lost / damaged / stolen
 * units. The backend service layer applies the negative sign when it
 * reduces stock; the wire body carries the unsigned magnitude.
 *
 * Backend constraints (DamageStockRequest in
 * backend/app/schemas/inventory.py): `quantity` must be a positive
 * integer (> 0); `reason` is mandatory and non-empty (whitespace-only
 * is rejected). The frontend mirrors these as UX guards only — the
 * authoritative validation lives server-side.
 */
export interface DamageStockRequest {
  quantity: number;
  reason: string;
}

/**
 * PATCH /inventory/{item_id}/threshold — update the reorder / low-stock
 * threshold of an inventory item.
 *
 * Backend contract: the route binds an embedded body field
 * `reorder_threshold: int (ge=0)` (see
 * `backend/app/api/routes/inventory.py::patch_inventory_threshold`).
 * The wire field name is `reorder_threshold` exactly — kept snake_case
 * here to mirror the JSON over the wire and stay grep-friendly against
 * the backend.
 *
 * Frontend mirrors the `>= 0` constraint as a UX guard only; the
 * server is the authoritative validator and will reject anything else.
 */
export interface UpdateInventoryThresholdRequest {
  reorder_threshold: number;
}

/**
 * PATCH /inventory/{item_id}/status — update the operational status of
 * an inventory item.
 *
 * Backend contract: the route binds an embedded body field
 * `status: InventoryStatus` (see
 * `backend/app/api/routes/inventory.py::patch_inventory_status`). The
 * service layer additionally restricts MVP-settable values to
 * `available | flagged | quarantined` (`_MVP_OPERATIONAL_STATUSES`);
 * any other enum value is rejected with 422.
 *
 * `reason` is captured by the frontend for audit / UX context. The
 * current MVP wire route does not bind it server-side, but the field
 * is sent verbatim so the backend can adopt it without a frontend
 * change. The frontend treats `reason` as a required UX guard.
 */
export interface UpdateInventoryStatusRequest {
  status: InventoryStatus;
  reason: string;
}

// --------------------------------------------------------------------- //
// Aggregate response
// --------------------------------------------------------------------- //

/**
 * Paginated response for GET /stores/{store_id}/inventory.
 *
 * Reuses the cross-cutting `PaginatedResponse<T>` envelope from
 * `src/api/types.ts` so feature hooks share the same shape with
 * every other paginated endpoint.
 */
export type InventoryListResponse = PaginatedResponse<InventoryItem>;

// --------------------------------------------------------------------- //
// F2.18.2C — admin global inventory feed (GET /admin/inventory)
// --------------------------------------------------------------------- //

/**
 * Optional filters for `getAdminInventory`.
 *
 * Mirrors the shipped backend surface from F2.18.1A
 * (`backend/app/api/routes/inventory.py::list_admin_inventory_endpoint`).
 * Every field is optional — an empty filter object requests the
 * unfiltered first page (server applies defaults: limit=100, offset=0).
 *
 * Snake_case keys mirror the backend query params 1:1 so the API
 * layer can serialize them verbatim.
 *
 * Notes (mirror F2.18.0 contract §8.2):
 *   - `store_id` is a QUERY filter (admin endpoint has no path id).
 *     When omitted, returns inventory across every store.
 *   - `low_stock` (NOT `low_stock_only`) — the admin endpoint renamed
 *     the flag in F2.18.1A so the admin namespace can grow
 *     consistently. The store-scoped endpoint still uses
 *     `low_stock_only`; that is intentional and untouched.
 *   - `q` runs ILIKE on `variant.sku` + `product.name` server-side;
 *     whitespace-only collapses to no filter.
 *   - `status` accepts the full `InventoryStatus` union (the admin
 *     filter is not restricted to the MVP-settable subset).
 *
 * Empty/whitespace strings are dropped by the API layer for every
 * string field (including `store_id`, `q`, `product_id`,
 * `variant_id`) so a "no filter" UI state doesn't send `?q=` (which
 * Pydantic would treat as the literal empty string).
 */
export interface AdminInventoryFilters {
  /**
   * Page size, 1..500. Sent verbatim when defined; backend default
   * applies otherwise.
   */
  limit?: number;
  /**
   * Pagination offset, >=0. Explicit `0` is preserved on the wire.
   */
  offset?: number;
  /**
   * Scope to one store. Optional — when omitted, the feed returns
   * inventory across every store the admin can see.
   * Empty/whitespace strings are dropped.
   */
  store_id?: string;
  /**
   * Low-stock filter:
   *   `(quantity_on_hand - quantity_reserved) <= reorder_threshold`.
   * Sent verbatim when defined (including explicit `false`); omitted
   * when undefined so the backend default (`False`) applies.
   */
  low_stock?: boolean;
  /**
   * Free-text search over `variant.sku` and `product.name`.
   * Empty/whitespace strings are dropped.
   */
  q?: string;
  /** Product UUID. Empty/whitespace strings are dropped. */
  product_id?: string;
  /** Variant UUID. Empty/whitespace strings are dropped. */
  variant_id?: string;
  /** Inventory status filter. */
  status?: InventoryStatus;
}
