// F2.7.0 subfase 2: orders API layer.
//
// Pure async functions over the backend orders endpoints. Every call
// goes through `apiRequest` from `@/api` so error normalisation, Bearer
// attach and FastAPI detail parsing stay centralised.
//
// Hard rules baked in:
//   - No fetch() directly.
//   - No React imports.
//   - No TanStack Query imports — that's the next subfase.
//   - No try/catch: ApiError propagates to the caller untouched.
//
// URL alignment (verified against backend/app/api/routes/orders.py and
// the bare `app.include_router(orders_router)` in app/main.py — no
// prefix):
//
//   POST  /stores/{store_id}/orders         (create, store-scoped)
//   GET   /stores/{store_id}/orders         (list, store-scoped)
//   GET   /orders/{order_id}                (read one, item-scoped)
//   GET   /orders/{order_id}/audit-logs     (audit trail, item-scoped)
//   PATCH /orders/{order_id}/status         (forward transitions)
//   POST  /orders/{order_id}/cancel         (manager-or-above)
//   POST  /orders/{order_id}/return         (manager-or-above)
//   GET   /admin/orders                     (F2.18.1B admin global feed)
//
// Item-scoped endpoints do not take store_id in the URL — the backend
// resolves it from the order row and runs `_assert_can_access_store`
// server-side. The hooks layer (next subfase) scopes its TanStack
// Query cache key by `currentStoreId` from `useStoreContext`, not from
// these function signatures.

import { apiRequest } from "@/api";
import type {
  AdminOrdersFilters,
  OrderAuditLogRead,
  OrderCancelRequest,
  OrderCreateRequest,
  OrderRead,
  OrderReturnRequest,
  OrderStatus,
  OrderStatusUpdateRequest,
  OrdersListResponse,
} from "./types";

// --------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------- //

function trimOrUndefined(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

// --------------------------------------------------------------------- //
// List
// --------------------------------------------------------------------- //

export interface GetOrdersListParams {
  /** Store UUID. Goes into the URL path. */
  storeId: string;
  /** Page size. Backend bounds: 1 <= limit <= 500 (default 100). */
  limit: number;
  /** Zero-based offset. Backend bound: offset >= 0. */
  offset: number;
  /**
   * Optional status filter. Backend query param is `?status=...` (the
   * route aliases it to avoid shadowing `fastapi.status` server-side).
   * Typed as `OrderStatus` so callers cannot send arbitrary strings.
   */
  status?: OrderStatus;
  /** Optional ISO 8601 datetime. Filters by `orders.created_at >= ...`. */
  created_from?: string;
  /** Optional ISO 8601 datetime. Filters by `orders.created_at <= ...`. */
  created_to?: string;
}

/**
 * GET /stores/{store_id}/orders
 *
 * Returns the paginated `OrdersListResponse` envelope. Throws ApiError
 * on any non-2xx (401, 403 for tenancy, 422 on bad params, 5xx).
 */
export function getOrdersList(
  params: GetOrdersListParams,
  signal?: AbortSignal,
): Promise<OrdersListResponse> {
  const query = new URLSearchParams();
  query.set("limit", String(params.limit));
  query.set("offset", String(params.offset));
  if (params.status !== undefined) {
    query.set("status", params.status);
  }
  if (params.created_from !== undefined) {
    query.set("created_from", params.created_from);
  }
  if (params.created_to !== undefined) {
    query.set("created_to", params.created_to);
  }
  const qs = query.toString();
  const path =
    `/stores/${encodeURIComponent(params.storeId)}/orders` +
    (qs.length > 0 ? `?${qs}` : "");
  return apiRequest<OrdersListResponse>(path, { signal });
}

// --------------------------------------------------------------------- //
// Read single
// --------------------------------------------------------------------- //

export interface GetOrderParams {
  /** Order UUID. Backend resolves the owning store_id from the row. */
  orderId: string;
}

/**
 * GET /orders/{order_id}
 *
 * Returns the full `OrderRead` with nested line items. Item-scoped
 * URL on the backend; tenancy is enforced server-side via the order's
 * stored `store_id`.
 */
export function getOrder(
  params: GetOrderParams,
  signal?: AbortSignal,
): Promise<OrderRead> {
  const path = `/orders/${encodeURIComponent(params.orderId)}`;
  return apiRequest<OrderRead>(path, { signal });
}

// --------------------------------------------------------------------- //
// Audit logs
// --------------------------------------------------------------------- //

export interface GetOrderAuditLogsParams {
  /** Order UUID. */
  orderId: string;
}

/**
 * GET /orders/{order_id}/audit-logs
 *
 * Returns the audit trail for an order, ascending by created_at. One
 * row per state transition. No pagination — the backend caps the row
 * count by the natural lifecycle bound (audit rows are append-only and
 * grow only with transitions).
 */
export function getOrderAuditLogs(
  params: GetOrderAuditLogsParams,
  signal?: AbortSignal,
): Promise<OrderAuditLogRead[]> {
  const path = `/orders/${encodeURIComponent(params.orderId)}/audit-logs`;
  return apiRequest<OrderAuditLogRead[]>(path, { signal });
}

// --------------------------------------------------------------------- //
// Create order
// --------------------------------------------------------------------- //

export interface CreateOrderParams {
  /** Store UUID. Goes into the URL path. */
  storeId: string;
  /**
   * Validated payload. `idempotency_key` is mandatory (orders_rules
   * §4); the hooks layer is responsible for generating a fresh
   * UUID4 per submission attempt.
   */
  body: OrderCreateRequest;
}

/**
 * POST /stores/{store_id}/orders
 *
 * Creates an order. Returns the persisted `OrderRead` with totals,
 * resolved `inventory_item_id` per line, and the eight lifecycle
 * timestamps (only `created_at` / `updated_at` populated initially).
 *
 * Idempotency contract:
 *   - Same `idempotency_key` + same caller + same store + same body
 *     → returns the EXISTING order (200 on replay, 201 on first call).
 *   - Same key + DIFFERENT body → 409 (replay protection).
 */
export function createOrder(
  params: CreateOrderParams,
  signal?: AbortSignal,
): Promise<OrderRead> {
  const path = `/stores/${encodeURIComponent(params.storeId)}/orders`;
  return apiRequest<OrderRead>(path, {
    method: "POST",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// Status transition (forward only)
// --------------------------------------------------------------------- //

export interface TransitionOrderStatusParams {
  /** Order UUID — owns the operation. */
  orderId: string;
  /** Validated payload. */
  body: OrderStatusUpdateRequest;
}

/**
 * PATCH /orders/{order_id}/status
 *
 * Used for forward transitions in the lifecycle (pending → accepted →
 * preparing → ready → out_for_delivery → delivered).
 *
 * IMPORTANT: backend rejects with 422 if `body.new_status` is
 * `"canceled"` or `"returned"`, routing the operator to the dedicated
 * `cancelOrder` / `returnOrder` endpoints. Callers MUST NOT use this
 * function for those two transitions.
 */
export function transitionOrderStatus(
  params: TransitionOrderStatusParams,
  signal?: AbortSignal,
): Promise<OrderRead> {
  const path = `/orders/${encodeURIComponent(params.orderId)}/status`;
  return apiRequest<OrderRead>(path, {
    method: "PATCH",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// Cancel (manager-or-above)
// --------------------------------------------------------------------- //

export interface CancelOrderParams {
  /** Order UUID — owns the operation. */
  orderId: string;
  /** Validated payload. `reason` is mandatory. */
  body: OrderCancelRequest;
}

/**
 * POST /orders/{order_id}/cancel
 *
 * Cancels a pre-delivered order. Releases reservations on inventory
 * (decrements `quantity_reserved`) without touching `quantity_on_hand`.
 * Manager-or-above per orders_rules §6.
 */
export function cancelOrder(
  params: CancelOrderParams,
  signal?: AbortSignal,
): Promise<OrderRead> {
  const path = `/orders/${encodeURIComponent(params.orderId)}/cancel`;
  return apiRequest<OrderRead>(path, {
    method: "POST",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// Return (manager-or-above)
// --------------------------------------------------------------------- //

export interface ReturnOrderParams {
  /** Order UUID — owns the operation. */
  orderId: string;
  /** Validated payload. `reason` is mandatory. */
  body: OrderReturnRequest;
}

/**
 * POST /orders/{order_id}/return
 *
 * Marks a delivered order as returned. Replenishes inventory
 * (`quantity_on_hand` rises) and writes the `return_` movement on
 * `inventory_logs`. Manager-or-above per orders_rules §6.
 */
export function returnOrder(
  params: ReturnOrderParams,
  signal?: AbortSignal,
): Promise<OrderRead> {
  const path = `/orders/${encodeURIComponent(params.orderId)}/return`;
  return apiRequest<OrderRead>(path, {
    method: "POST",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// F2.18.2C: admin global orders feed (F2.18.1B)
// --------------------------------------------------------------------- //

/**
 * GET /admin/orders
 *
 * Admin-only global orders feed. Same `OrdersListResponse` envelope
 * and same per-order `OrderRead` shape as the store-scoped
 * `getOrdersList`; the only differences are:
 *
 *   - No `storeId` path segment — admins can list across every
 *     store, or scope to one by setting the `store_id` filter.
 *   - Backend auth is `require_admin` (not `require_store_member` +
 *     `require_staff_or_above`). Non-admin → 403.
 *   - Date filter names are `date_from` / `date_to` (vs.
 *     `created_from` / `created_to` on the store-scoped endpoint).
 *   - `q` is intentionally NOT supported (see F2.18.1B contract
 *     amendment — `Order` has no clean text-search target).
 *
 * Query serialization rules:
 *   - `limit`: forwarded verbatim when defined.
 *   - `offset`: forwarded verbatim when defined, INCLUDING explicit
 *     `0` (deliberate "first page" must be preserved).
 *   - `status`: forwarded verbatim when defined (enum-typed).
 *   - `store_id`, `date_from`, `date_to`: trimmed; empty strings are
 *     dropped so a "no filter" UI state doesn't send `?store_id=`
 *     (which Pydantic would treat as an invalid UUID and 422).
 *
 * Backend authorisation (F2.18.1B):
 *   - `require_admin` — owner / manager / staff / driver → 403.
 *   - `store_id` filter pointing at a non-existent store → 404.
 *     Inactive stores are explicitly allowed.
 *
 * Throws ApiError on:
 *   - 401 (no/invalid token)
 *   - 403 (non-admin caller)
 *   - 404 (`store_id` filter points at an unknown store)
 *   - 422 (query enum / UUID / datetime / bounds validation)
 *   - 5xx (server failure)
 */
export function getAdminOrders(
  filters: AdminOrdersFilters = {},
  signal?: AbortSignal,
): Promise<OrdersListResponse> {
  const search = new URLSearchParams();

  if (filters.limit !== undefined) {
    search.set("limit", String(filters.limit));
  }
  if (filters.offset !== undefined) {
    // Preserve explicit offset=0 — that's "first page", not "skip".
    search.set("offset", String(filters.offset));
  }
  if (filters.status !== undefined) {
    search.set("status", filters.status);
  }

  const storeId = trimOrUndefined(filters.store_id);
  if (storeId !== undefined) {
    search.set("store_id", storeId);
  }
  const dateFrom = trimOrUndefined(filters.date_from);
  if (dateFrom !== undefined) {
    search.set("date_from", dateFrom);
  }
  const dateTo = trimOrUndefined(filters.date_to);
  if (dateTo !== undefined) {
    search.set("date_to", dateTo);
  }

  const query = search.toString();
  const path = `/admin/orders${query ? `?${query}` : ""}`;
  return apiRequest<OrdersListResponse>(path, { method: "GET", signal });
}
