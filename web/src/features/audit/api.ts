// F2.16.4: audit API layer — legacy inventory logs + unified feed.
//
// Two pure async functions over the backend audit-shaped endpoints
// the feature consumes. Every call goes through `apiRequest` from
// `@/api` so error normalisation, Bearer attach and FastAPI detail
// parsing stay centralised.
//
// Hard rules baked in (mirroring features/products, features/inventory,
// features/orders, features/users):
//   - No fetch() directly.
//   - No React imports.
//   - No TanStack Query imports — that's the hooks layer.
//   - No try/catch: ApiError propagates to the caller untouched.
//   - No business logic: the unified-feed aggregation happens
//     server-side; the frontend never merges, sorts, or normalizes
//     log shapes.
//
// URL alignment:
//   - GET /stores/{store_id}/inventory/logs  (legacy, F2.10)
//       inventory.py::list_store_inventory_logs
//   - GET /stores/{store_id}/audit           (F2.16.3 unified feed)
//       audit.py::list_store_audit_endpoint
//   - GET /admin/audit                        (F2.17.5 admin global feed)
//       audit.py::list_admin_audit_endpoint
//
// Endpoints intentionally NOT implemented here (already wrapped in
// their owning features):
//   - GET /inventory/{item_id}/logs             → features/inventory
//   - GET /orders/{order_id}/audit-logs         → features/orders
//   - GET /products/{product_id}/compliance-audit → features/products

import { apiRequest } from "@/api";
import type {
  AdminAuditFilters,
  AuditListResponse,
  GetStoreInventoryLogsParams,
  StoreAuditFilters,
  StoreInventoryLogEntry,
} from "./types";

// --------------------------------------------------------------------- //
// Legacy: store inventory logs (F2.10)
// --------------------------------------------------------------------- //

/**
 * GET /stores/{store_id}/inventory/logs
 *
 * Returns the store-scoped inventory audit trail as a bare array
 * (`list[InventoryLogRead]` on the wire — there is NO paginated
 * envelope here). The backend currently only supports the `limit`
 * query param.
 *
 * Backend authorisation:
 *   - `require_store_member` on the path — non-admin must own this
 *     store; cross-store non-admin → 403; missing store → 404;
 *     inactive store → 400.
 *   - `require_staff_or_above` on the caller — driver and anonymous
 *     callers receive 403.
 *
 * Throws ApiError on:
 *   - 401 (no/invalid token)
 *   - 403 (role gate or cross-store)
 *   - 404 (missing store)
 *   - 400 (inactive store)
 *   - 422 (Pydantic validation on bad query params)
 *   - 5xx (server failure)
 */
export function getStoreInventoryLogs(
  params: GetStoreInventoryLogsParams,
  signal?: AbortSignal,
): Promise<StoreInventoryLogEntry[]> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) {
    search.set("limit", String(params.limit));
  }
  const query = search.toString();
  const path = `/stores/${encodeURIComponent(params.storeId)}/inventory/logs${
    query ? `?${query}` : ""
  }`;
  return apiRequest<StoreInventoryLogEntry[]>(path, {
    method: "GET",
    signal,
  });
}

// --------------------------------------------------------------------- //
// F2.16: unified store audit feed
// --------------------------------------------------------------------- //

function trimOrUndefined(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

/**
 * GET /stores/{store_id}/audit
 *
 * Returns the unified, store-scoped audit feed as a paginated
 * envelope. The backend aggregates `inventory_logs`,
 * `order_audit_logs`, and `product_compliance_audit_logs` into a
 * single normalized `AuditEvent` shape, then applies filters,
 * stable sort (created_at DESC, source ASC, id ASC) and
 * post-merge pagination.
 *
 * Query serialization rules (mirror the F2.16.3 route contract):
 *   - `limit`: forwarded verbatim when defined (including 0/-1 so
 *     server-side `Query(ge=1, le=200)` produces a clean 422 for
 *     validation tests).
 *   - `offset`: forwarded verbatim when defined, INCLUDING explicit
 *     `0` (a deliberate "first page" must be preserved on the wire
 *     so a hook re-render with the same key doesn't drop the param).
 *   - `source`, `entity_type`: forwarded verbatim when defined.
 *   - `action`, `actor_id`, `date_from`, `date_to`: trimmed; empty
 *     strings are dropped so a "no filter" UI state doesn't send
 *     `?action=` (which Pydantic would treat as the literal empty
 *     string and never match anything).
 *
 * Backend authorisation (F2.16.3):
 *   - `require_store_member` on the path — admin global, non-admin
 *     own-store; cross-store / unknown collapse to 403; inactive
 *     store → 400; admin + unknown store → 404.
 *   - `require_staff_or_above` on the caller — driver → 403.
 *
 * Throws ApiError on:
 *   - 401 (no/invalid token)
 *   - 403 (role gate or cross-store)
 *   - 404 (admin requesting unknown store)
 *   - 400 (inactive store)
 *   - 422 (path UUID / query enum / UUID / datetime / bounds)
 *   - 5xx (server failure)
 */
export function getStoreAudit(
  storeId: string,
  filters: StoreAuditFilters = {},
  signal?: AbortSignal,
): Promise<AuditListResponse> {
  const search = new URLSearchParams();

  if (filters.limit !== undefined) {
    search.set("limit", String(filters.limit));
  }
  if (filters.offset !== undefined) {
    // Preserve explicit offset=0 — that's "first page", not "skip".
    search.set("offset", String(filters.offset));
  }
  if (filters.source !== undefined) {
    search.set("source", filters.source);
  }
  if (filters.entity_type !== undefined) {
    search.set("entity_type", filters.entity_type);
  }

  const action = trimOrUndefined(filters.action);
  if (action !== undefined) {
    search.set("action", action);
  }
  const actorId = trimOrUndefined(filters.actor_id);
  if (actorId !== undefined) {
    search.set("actor_id", actorId);
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
  const path = `/stores/${encodeURIComponent(storeId)}/audit${
    query ? `?${query}` : ""
  }`;
  return apiRequest<AuditListResponse>(path, {
    method: "GET",
    signal,
  });
}

// --------------------------------------------------------------------- //
// F2.18.2B: admin global audit feed (F2.17.5)
// --------------------------------------------------------------------- //

/**
 * GET /admin/audit
 *
 * Admin-only global audit feed. Same `AuditListResponse` envelope and
 * same per-event `AuditEvent` shape as `getStoreAudit`; the only
 * differences are:
 *
 *   - No `storeId` path segment — admins can list across every
 *     store, or scope to one by setting the `store_id` filter.
 *   - Backend auth is `require_admin` (not `require_store_member` +
 *     `require_staff_or_above`). Non-admin → 403.
 *
 * Query serialization rules (mirror `getStoreAudit`):
 *   - `limit`: forwarded verbatim when defined.
 *   - `offset`: forwarded verbatim when defined, INCLUDING explicit
 *     `0` (deliberate "first page" must be preserved).
 *   - `source`, `entity_type`: forwarded verbatim when defined.
 *   - `store_id`, `action`, `actor_id`, `date_from`, `date_to`:
 *     trimmed; empty strings are dropped so a "no filter" UI state
 *     doesn't send `?store_id=` (which Pydantic would treat as the
 *     literal empty string and 422 the request).
 *
 * Backend authorisation (F2.17.5):
 *   - `require_admin` — owner / manager / staff / driver → 403.
 *   - `store_id` filter pointing at a non-existent store → 404
 *     (consistent with `list_admin_inventory` / `list_admin_orders`
 *     precedent). Inactive stores are explicitly allowed —
 *     deactivated stores retain audit history.
 *
 * Throws ApiError on:
 *   - 401 (no/invalid token)
 *   - 403 (non-admin caller)
 *   - 404 (`store_id` filter points at an unknown store)
 *   - 422 (query enum / UUID / datetime / bounds validation)
 *   - 5xx (server failure)
 */
export function getAdminAudit(
  filters: AdminAuditFilters = {},
  signal?: AbortSignal,
): Promise<AuditListResponse> {
  const search = new URLSearchParams();

  if (filters.limit !== undefined) {
    search.set("limit", String(filters.limit));
  }
  if (filters.offset !== undefined) {
    // Preserve explicit offset=0 — that's "first page", not "skip".
    search.set("offset", String(filters.offset));
  }
  if (filters.source !== undefined) {
    search.set("source", filters.source);
  }
  if (filters.entity_type !== undefined) {
    search.set("entity_type", filters.entity_type);
  }

  const storeId = trimOrUndefined(filters.store_id);
  if (storeId !== undefined) {
    search.set("store_id", storeId);
  }
  const action = trimOrUndefined(filters.action);
  if (action !== undefined) {
    search.set("action", action);
  }
  const actorId = trimOrUndefined(filters.actor_id);
  if (actorId !== undefined) {
    search.set("actor_id", actorId);
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
  const path = `/admin/audit${query ? `?${query}` : ""}`;
  return apiRequest<AuditListResponse>(path, {
    method: "GET",
    signal,
  });
}
