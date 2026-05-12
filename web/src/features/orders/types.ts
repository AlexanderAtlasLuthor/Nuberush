// F2.7.1: orders wire types.
//
// 1:1 mirror of the FastAPI orders contract. Field names and casing
// match the JSON over the wire exactly (snake_case). Do NOT camelCase
// here; that mapping, if ever needed, belongs in the UI layer.
//
// Sources of truth:
//   - backend/app/schemas/orders.py
//       OrderCreate, OrderItemCreate, OrderRead, OrderItemRead,
//       OrderStatusUpdate, OrderCancelRequest, OrderReturnRequest,
//       OrderAuditLogRead, OrderListResponse
//   - backend/app/schemas/inventory.py
//       InventoryVariantSummary, InventoryProductSummary
//   - backend/app/db/models.py
//       OrderStatus
//
// Type-design decisions:
//   - Money fields are strings because the backend serializes Decimal
//     values as JSON strings.
//   - Datetime fields are strings from the backend wire.
//   - UUIDs are strings.
//   - Request bodies omit every server-managed or trust-boundary field.

import type { PaginatedResponse } from "@/api/types";
import type {
  VariantSummary as InventoryVariantSummary,
} from "@/features/inventory/types";

// --------------------------------------------------------------------- //
// Enum
// --------------------------------------------------------------------- //

export type OrderStatus =
  | "pending"
  | "accepted"
  | "preparing"
  | "ready"
  | "out_for_delivery"
  | "delivered"
  | "canceled"
  | "returned";

// --------------------------------------------------------------------- //
// Read shapes
// --------------------------------------------------------------------- //

/**
 * Response shape for an order line item.
 *
 * Mirrors backend `OrderItemRead`. `variant` is the backend enrichment
 * needed by Orders UI and uses the same summary shape as Inventory:
 * variant plus nested product summary.
 */
export interface OrderItemRead {
  id: string;
  order_id: string;
  variant_id: string;
  inventory_item_id: string;
  quantity: number;
  /** Decimal-as-string to preserve precision. */
  unit_price: string;
  /** Decimal-as-string. Server-enforced line total snapshot. */
  line_total: string;
  created_at: string;
  updated_at: string;
  variant: InventoryVariantSummary;
}

/**
 * Response shape for any endpoint returning an order.
 */
export interface OrderRead {
  id: string;
  store_id: string;
  customer_user_id: string | null;
  idempotency_key: string;
  status: OrderStatus;
  /** Decimal-as-string. Server-computed from line items. */
  subtotal_amount: string;
  /** Decimal-as-string. */
  tax_amount: string;
  /** Decimal-as-string. */
  total_amount: string;
  age_verified_at: string | null;
  age_verified_by_user_id: string | null;
  accepted_at: string | null;
  canceled_at: string | null;
  delivered_at: string | null;
  returned_at: string | null;
  cancel_reason: string | null;
  notes: string | null;
  created_at: string;
  updated_at: string;
  items: OrderItemRead[];
}

/**
 * Response shape for an order audit log entry.
 */
export interface OrderAuditLogRead {
  id: string;
  order_id: string;
  store_id: string;
  performed_by_user_id: string | null;
  previous_status: OrderStatus | null;
  new_status: OrderStatus;
  action: string;
  reason: string | null;
  created_at: string;
}

// --------------------------------------------------------------------- //
// Request bodies
// --------------------------------------------------------------------- //

/**
 * Body element of `OrderCreateRequest.items`.
 */
export interface OrderItemCreate {
  variant_id: string;
  /** Backend constraint: > 0. */
  quantity: number;
}

/**
 * Body for `POST /stores/{store_id}/orders`.
 *
 * Deliberately omits server-managed fields, money snapshots,
 * `inventory_item_id`, status and timestamps.
 */
export interface OrderCreateRequest {
  /** Required. Trimmed, 1..128 chars. UUID4 recommended. */
  idempotency_key: string;
  /** Required. Length >= 1. No duplicate variant_id across items. */
  items: OrderItemCreate[];
  /** Optional. Backend rejects whitespace-only when provided. */
  notes?: string | null;
}

/**
 * Body for `PATCH /orders/{order_id}/status`.
 */
export interface OrderStatusUpdateRequest {
  new_status: OrderStatus;
  /** Optional. Backend rejects whitespace-only when provided. */
  reason?: string | null;
}

/**
 * Body for `POST /orders/{order_id}/cancel`.
 */
export interface OrderCancelRequest {
  /** Required. Length >= 1 after trim. */
  reason: string;
}

/**
 * Body for `POST /orders/{order_id}/return`.
 */
export interface OrderReturnRequest {
  /** Required. Length >= 1 after trim. */
  reason: string;
}

// --------------------------------------------------------------------- //
// Aggregate response
// --------------------------------------------------------------------- //

/**
 * Paginated response for `GET /stores/{store_id}/orders`.
 *
 * Matches BO_PAG: `{ items, total, limit, offset }`.
 */
export type OrdersListResponse = PaginatedResponse<OrderRead>;

// --------------------------------------------------------------------- //
// F2.18.2C — admin global orders feed (GET /admin/orders)
// --------------------------------------------------------------------- //

/**
 * Optional filters for `getAdminOrders`.
 *
 * Mirrors the shipped backend surface from F2.18.1B
 * (`backend/app/api/routes/orders.py::list_admin_orders_endpoint`).
 * Every field is optional — an empty filter object requests the
 * unfiltered first page (server applies defaults: limit=50, offset=0).
 *
 * Snake_case keys mirror the backend query params 1:1 so the API
 * layer can serialize them verbatim.
 *
 * Notes (mirror F2.18.0/F2.18.1B contract §8.2):
 *   - `store_id` is a QUERY filter (admin endpoint has no path id).
 *     When omitted, returns orders across every store.
 *   - `date_from` / `date_to` are INCLUSIVE bounds on
 *     `Order.created_at` (`>=` and `<=`), matching the existing
 *     store-scoped semantics.
 *
 * `q` is intentionally **not** declared. F2.18.1B explicitly did not
 * ship a `q` filter for `/admin/orders` (the `Order` model has no
 * clean text-search target). Adding `q` here would create silent
 * contract divergence — the backend would 422 on the `q` query
 * param, and the wire would never carry it anyway. See contract
 * doc §8.2 (admin orders surface).
 *
 * Empty/whitespace strings are dropped by the API layer for every
 * string field (`store_id`, `date_from`, `date_to`).
 */
export interface AdminOrdersFilters {
  /**
   * Page size, 1..200. Sent verbatim when defined; backend default
   * applies otherwise.
   */
  limit?: number;
  /**
   * Pagination offset, >=0. Explicit `0` is preserved on the wire.
   */
  offset?: number;
  /**
   * Scope to one store. Optional — when omitted, the feed returns
   * orders across every store the admin can see.
   * Empty/whitespace strings are dropped.
   */
  store_id?: string;
  /** Order status filter. */
  status?: OrderStatus;
  /**
   * ISO 8601 inclusive lower bound for `Order.created_at` (`>=`).
   * Empty/whitespace strings are dropped.
   */
  date_from?: string;
  /**
   * ISO 8601 inclusive upper bound for `Order.created_at` (`<=`).
   * Empty/whitespace strings are dropped.
   */
  date_to?: string;
}
