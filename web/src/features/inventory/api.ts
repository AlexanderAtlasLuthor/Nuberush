// F2.6.0 subfase 2: inventory API layer.
//
// Pure async functions over the backend inventory endpoints. Every call
// goes through `apiRequest` from `@/api` so error normalisation, Bearer
// attach and FastAPI detail parsing stay centralised.
//
// Hard rules baked in:
//   - No fetch() directly.
//   - No React imports.
//   - No TanStack Query imports — that's the next subfase.
//   - No try/catch: ApiError propagates to the caller untouched.
//
// URL alignment (verified against backend/app/api/routes/inventory.py
// and the bare `app.include_router(inventory_router)` in app/main.py —
// no prefix):
//
//   GET  /stores/{store_id}/inventory         (store-scoped, paginated)
//   GET  /inventory/{item_id}                 (item-scoped)
//   POST /inventory/{item_id}/receive         (item-scoped)
//   POST /inventory/{item_id}/adjust          (item-scoped)
//   GET  /admin/inventory                     (F2.18.1A admin global feed)
//
// The brief listed item-scoped paths under `/stores/{storeId}/inventory/{id}/...`,
// but those routes do not exist on the backend. Calling them would 404.
// The store-tenancy gate is enforced server-side by
// `_assert_can_access_store(current_user, item.store_id)`, which loads
// the real store_id from the item — there is nothing for the client to
// re-assert via the URL. The hooks layer scopes its TanStack Query
// cache key by `currentStoreId` from `useStoreContext`, not from these
// function signatures.

import { apiRequest } from "@/api";
import type {
  AdjustStockRequest,
  AdminInventoryFilters,
  DamageStockRequest,
  InventoryImportConfirmResponse,
  InventoryImportPreviewResponse,
  InventoryItem,
  InventoryListResponse,
  InventoryLogEntry,
  ReceiveStockRequest,
  UpdateInventoryStatusRequest,
  UpdateInventoryThresholdRequest,
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

export interface GetInventoryListParams {
  /** Store UUID. Goes into the URL path. */
  storeId: string;
  /** Page size. Backend bounds: 1 ≤ limit ≤ 500 (default 100). */
  limit: number;
  /** Zero-based offset. Backend bound: offset ≥ 0. */
  offset: number;
  /**
   * If true, only items where quantity_on_hand <= reorder_threshold are
   * returned. Optional; omitted query string defaults to backend false.
   *
   * The wire field name is `low_stock_only` exactly — kept as snake_case
   * even on the JS-side params interface to make the URL composition
   * mechanical and grep-friendly against backend code.
   */
  low_stock_only?: boolean;
}

/**
 * GET /stores/{store_id}/inventory
 *
 * Paginated inventory listing. Resolves to the standard
 * `PaginatedResponse<InventoryItem>` envelope; throws ApiError on any
 * non-2xx (401, 403 for tenancy, 422 on bad params, 5xx).
 *
 * NOTE: the brief listed `search` and `status` query params; neither
 * exists on the backend wire today (verified in
 * `app/api/routes/inventory.py::list_store_inventory`). They are
 * intentionally omitted here to avoid silently no-op filters.
 * `low_stock_only` is the only filter currently supported.
 */
export function getInventoryList(
  params: GetInventoryListParams,
  signal?: AbortSignal,
): Promise<InventoryListResponse> {
  const query = new URLSearchParams();
  query.set("limit", String(params.limit));
  query.set("offset", String(params.offset));
  if (params.low_stock_only !== undefined) {
    query.set("low_stock_only", String(params.low_stock_only));
  }

  const path = `/stores/${encodeURIComponent(params.storeId)}/inventory?${query.toString()}`;
  return apiRequest<InventoryListResponse>(path, { signal });
}

// --------------------------------------------------------------------- //
// Read single
// --------------------------------------------------------------------- //

export interface GetInventoryItemParams {
  /** Inventory item UUID. Backend resolves the owning store_id from the row. */
  inventoryItemId: string;
}

/**
 * GET /inventory/{item_id}
 *
 * Returns the enriched `InventoryItem` (with `variant.product`).
 *
 * NOTE: this endpoint is item-scoped on the backend, NOT store-scoped.
 * The brief asked for `GET /stores/{storeId}/inventory/{id}` but no
 * such route is registered. Server enforces tenancy by reading the
 * item's store_id and comparing against the caller's user.store_id.
 */
export function getInventoryItem(
  params: GetInventoryItemParams,
  signal?: AbortSignal,
): Promise<InventoryItem> {
  const path = `/inventory/${encodeURIComponent(params.inventoryItemId)}`;
  return apiRequest<InventoryItem>(path, { signal });
}

// --------------------------------------------------------------------- //
// Receive stock (manager-or-above)
// --------------------------------------------------------------------- //

export interface ReceiveStockParams {
  /** Inventory item UUID — owns the operation. */
  inventoryItemId: string;
  /** Validated payload (quantity > 0; reason optional). */
  body: ReceiveStockRequest;
}

/**
 * POST /inventory/{item_id}/receive
 *
 * Adds stock from a supplier or inbound transfer. Returns the updated
 * `InventoryItem`. Backend writes both the mutation and the audit log
 * atomically; the response shape carries the post-mutation balance.
 *
 * NOTE: item-scoped URL on the backend. The brief listed
 * `/stores/{storeId}/inventory/{id}/receive`, which does not exist.
 */
export function receiveStock(
  params: ReceiveStockParams,
  signal?: AbortSignal,
): Promise<InventoryItem> {
  const path = `/inventory/${encodeURIComponent(params.inventoryItemId)}/receive`;
  return apiRequest<InventoryItem>(path, {
    method: "POST",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// Adjust stock (manager-or-above)
// --------------------------------------------------------------------- //

export interface AdjustStockParams {
  /** Inventory item UUID — owns the operation. */
  inventoryItemId: string;
  /** Validated payload (delta non-zero; reason mandatory and non-empty). */
  body: AdjustStockRequest;
}

/**
 * POST /inventory/{item_id}/adjust
 *
 * Signed adjustment. Positive delta adds, negative removes; backend
 * rejects delta=0 with 422. Returns the updated `InventoryItem`.
 *
 * NOTE: item-scoped URL on the backend. The brief listed
 * `/stores/{storeId}/inventory/{id}/adjust`, which does not exist.
 */
export function adjustStock(
  params: AdjustStockParams,
  signal?: AbortSignal,
): Promise<InventoryItem> {
  const path = `/inventory/${encodeURIComponent(params.inventoryItemId)}/adjust`;
  return apiRequest<InventoryItem>(path, {
    method: "POST",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// Damage stock (manager-or-above)
// --------------------------------------------------------------------- //

export interface DamageStockParams {
  /** Inventory item UUID — owns the operation. */
  inventoryItemId: string;
  /** Validated payload (quantity > 0; reason mandatory and non-empty). */
  body: DamageStockRequest;
}

/**
 * POST /inventory/{item_id}/damage
 *
 * Records units lost / damaged / stolen. The wire `quantity` is the
 * unsigned magnitude; the service layer applies the negative sign on
 * the server when it reduces stock. Returns the updated `InventoryItem`.
 *
 * NOTE: item-scoped URL on the backend, mirroring `receive` and
 * `adjust`. Tenancy is enforced server-side via the item's store_id.
 */
export function damageStock(
  params: DamageStockParams,
  signal?: AbortSignal,
): Promise<InventoryItem> {
  const path = `/inventory/${encodeURIComponent(params.inventoryItemId)}/damage`;
  return apiRequest<InventoryItem>(path, {
    method: "POST",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// Update threshold (manager-or-above)
// --------------------------------------------------------------------- //

export interface UpdateInventoryThresholdParams {
  /** Inventory item UUID — owns the operation. */
  inventoryItemId: string;
  /** Validated payload (reorder_threshold >= 0, integer). */
  body: UpdateInventoryThresholdRequest;
}

/**
 * PATCH /inventory/{item_id}/threshold
 *
 * Updates the reorder / low-stock threshold for an inventory item.
 * Returns the updated `InventoryItem`. The body is sent verbatim with
 * the wire-shaped field name `reorder_threshold`; the backend route
 * uses `Body(embed=True)` and reads exactly that key.
 *
 * NOTE: item-scoped URL on the backend, mirroring the movement
 * endpoints. Tenancy is enforced server-side via the item's store_id.
 */
export function updateInventoryThreshold(
  params: UpdateInventoryThresholdParams,
  signal?: AbortSignal,
): Promise<InventoryItem> {
  const path = `/inventory/${encodeURIComponent(params.inventoryItemId)}/threshold`;
  return apiRequest<InventoryItem>(path, {
    method: "PATCH",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// Update status (manager-or-above)
// --------------------------------------------------------------------- //

export interface UpdateInventoryStatusParams {
  /** Inventory item UUID — owns the operation. */
  inventoryItemId: string;
  /** Validated payload (status from MVP-settable union; reason required). */
  body: UpdateInventoryStatusRequest;
}

/**
 * PATCH /inventory/{item_id}/status
 *
 * Updates the operational status of an inventory item. Returns the
 * updated `InventoryItem`. Body is sent verbatim with the wire-shaped
 * field `status`; backend validates the enum + MVP-settable subset.
 *
 * NOTE: item-scoped URL on the backend, mirroring the threshold route.
 * Tenancy is enforced server-side via the item's store_id.
 */
export function updateInventoryStatus(
  params: UpdateInventoryStatusParams,
  signal?: AbortSignal,
): Promise<InventoryItem> {
  const path = `/inventory/${encodeURIComponent(params.inventoryItemId)}/status`;
  return apiRequest<InventoryItem>(path, {
    method: "PATCH",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// Item logs (staff-or-above)
// --------------------------------------------------------------------- //

export interface GetInventoryItemLogsParams {
  /** Inventory item UUID. Goes into the URL path. */
  inventoryItemId: string;
  /**
   * Maximum rows to return. Backend default is 100, no documented
   * upper bound. Passed verbatim as the `limit` query param when
   * defined; omitted otherwise so the backend uses its own default.
   */
  limit?: number;
}

/**
 * GET /inventory/{item_id}/logs
 *
 * Returns the append-only audit trail for a single inventory item as a
 * bare array (`list[InventoryLogRead]` on the wire — there is NO
 * paginated envelope here). The backend currently only supports the
 * `limit` query param; `offset` is not bound by the route.
 *
 * The hooks layer scopes this query under the same item prefix as
 * `getInventoryItem`, so invalidating an item's cache also refreshes
 * its logs.
 */
export function getInventoryItemLogs(
  params: GetInventoryItemLogsParams,
  signal?: AbortSignal,
): Promise<InventoryLogEntry[]> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) {
    search.set("limit", String(params.limit));
  }
  const query = search.toString();
  const path = `/inventory/${encodeURIComponent(params.inventoryItemId)}/logs${
    query ? `?${query}` : ""
  }`;
  return apiRequest<InventoryLogEntry[]>(path, { method: "GET", signal });
}

// --------------------------------------------------------------------- //
// F2.18.2C: admin global inventory feed (F2.18.1A)
// --------------------------------------------------------------------- //

/**
 * GET /admin/inventory
 *
 * Admin-only global inventory feed. Same `InventoryListResponse`
 * envelope and same per-item `InventoryItem` shape as the store-scoped
 * `getInventoryList`; the only differences are:
 *
 *   - No `storeId` path segment — admins can list across every store,
 *     or scope to one by setting the `store_id` filter.
 *   - Backend auth is `require_admin` (not `require_store_member` +
 *     `require_staff_or_above`). Non-admin → 403.
 *   - Admin endpoint uses `low_stock` (not `low_stock_only`) — see
 *     F2.18.1A contract amendment.
 *   - Extra admin filters: `q`, `product_id`, `variant_id`, `status`.
 *
 * Query serialization rules:
 *   - `limit`: forwarded verbatim when defined.
 *   - `offset`: forwarded verbatim when defined, INCLUDING explicit
 *     `0` (deliberate "first page" must be preserved).
 *   - `low_stock`: forwarded verbatim when defined (including `false`);
 *     omitted when undefined so the backend default applies.
 *   - `status`: forwarded verbatim when defined (enum-typed).
 *   - `store_id`, `q`, `product_id`, `variant_id`: trimmed; empty
 *     strings are dropped so a "no filter" UI state doesn't send
 *     `?q=` (which Pydantic would treat as the literal empty string).
 *
 * Backend authorisation (F2.18.1A):
 *   - `require_admin` — owner / manager / staff / driver → 403.
 *   - `store_id` filter pointing at a non-existent store → 404.
 *     Inactive stores are explicitly allowed.
 *
 * Throws ApiError on:
 *   - 401 (no/invalid token)
 *   - 403 (non-admin caller)
 *   - 404 (`store_id` filter points at an unknown store)
 *   - 422 (query enum / UUID / bounds validation)
 *   - 5xx (server failure)
 */
export function getAdminInventory(
  filters: AdminInventoryFilters = {},
  signal?: AbortSignal,
): Promise<InventoryListResponse> {
  const search = new URLSearchParams();

  if (filters.limit !== undefined) {
    search.set("limit", String(filters.limit));
  }
  if (filters.offset !== undefined) {
    // Preserve explicit offset=0 — that's "first page", not "skip".
    search.set("offset", String(filters.offset));
  }
  if (filters.low_stock !== undefined) {
    // Preserve explicit `false` even though it matches the backend
    // default; a deliberate `?low_stock=false` round-trip is part of
    // the cache-key stability contract.
    search.set("low_stock", String(filters.low_stock));
  }
  if (filters.status !== undefined) {
    search.set("status", filters.status);
  }

  const storeId = trimOrUndefined(filters.store_id);
  if (storeId !== undefined) {
    search.set("store_id", storeId);
  }
  const q = trimOrUndefined(filters.q);
  if (q !== undefined) {
    search.set("q", q);
  }
  const productId = trimOrUndefined(filters.product_id);
  if (productId !== undefined) {
    search.set("product_id", productId);
  }
  const variantId = trimOrUndefined(filters.variant_id);
  if (variantId !== undefined) {
    search.set("variant_id", variantId);
  }

  const query = search.toString();
  const path = `/admin/inventory${query ? `?${query}` : ""}`;
  return apiRequest<InventoryListResponse>(path, { method: "GET", signal });
}

// --------------------------------------------------------------------- //
// F2.27.8: Excel inventory import (manager-or-above, store-scoped)
// --------------------------------------------------------------------- //

export interface InventoryImportParams {
  /** Store UUID. Goes into the URL path. */
  storeId: string;
  /** The QuickBooks POS `.xlsx` file selected by the user. */
  file: File;
  /**
   * F2.27.9 (admin only): when true, rows whose SKU has no existing
   * variant create a new product + variant (not for sale, pending
   * review) instead of being blocked. Omitted from the request when
   * falsy so non-admin imports stay byte-for-byte as before.
   */
  createMissing?: boolean;
}

function buildImportFormData(file: File, createMissing?: boolean): FormData {
  const form = new FormData();
  // Field name MUST be `file` — it matches the FastAPI `UploadFile`
  // parameter name on both import endpoints.
  form.append("file", file);
  if (createMissing) {
    // Matches the `create_missing: bool = Form(...)` endpoint param.
    form.append("create_missing", "true");
  }
  return form;
}

/**
 * POST /stores/{store_id}/inventory/import/preview
 *
 * Uploads a QuickBooks POS `.xlsx` and returns a non-destructive
 * preview: per-row diff against existing variants/inventory plus an
 * aggregate summary. NO DB writes happen server-side.
 *
 * The body is a `FormData` with a single `file` field; `apiRequest`
 * intentionally does NOT set Content-Type for FormData so the browser
 * supplies its own multipart boundary.
 *
 * Throws ApiError on:
 *   - 400 (unsupported file type / empty file)
 *   - 401 (no/invalid token), 403 (staff or cross-store caller)
 *   - 413 (file too large)
 *   - 422 (bad headers / unreadable workbook)
 */
export function previewInventoryImport(
  params: InventoryImportParams,
  signal?: AbortSignal,
): Promise<InventoryImportPreviewResponse> {
  const path = `/stores/${encodeURIComponent(
    params.storeId,
  )}/inventory/import/preview`;
  return apiRequest<InventoryImportPreviewResponse>(path, {
    method: "POST",
    body: buildImportFormData(params.file, params.createMissing),
    signal,
  });
}

/**
 * POST /stores/{store_id}/inventory/import/confirm
 *
 * Re-uploads the SAME `.xlsx` and applies the import in one
 * all-or-nothing transaction. The server re-validates from scratch and
 * refuses (422 with code `BLOCKING_ERRORS`) if any row has a blocking
 * error — a stale preview cannot smuggle bad rows through.
 *
 * Throws ApiError with the same status family as `previewInventoryImport`,
 * plus 422 (`BLOCKING_ERRORS`) when the import cannot be applied.
 */
export function confirmInventoryImport(
  params: InventoryImportParams,
  signal?: AbortSignal,
): Promise<InventoryImportConfirmResponse> {
  const path = `/stores/${encodeURIComponent(
    params.storeId,
  )}/inventory/import/confirm`;
  return apiRequest<InventoryImportConfirmResponse>(path, {
    method: "POST",
    body: buildImportFormData(params.file, params.createMissing),
    signal,
  });
}
