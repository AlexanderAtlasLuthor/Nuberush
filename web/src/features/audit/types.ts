// F2.16.4: audit feature wire types — extended for the unified feed.
//
// The audit feature now exposes TWO backend surfaces:
//
//   1. GET /stores/{store_id}/inventory/logs   →  list[InventoryLogRead]
//      (legacy, F2.10; one source, returns a bare array).
//   2. GET /stores/{store_id}/audit            →  AuditEventListResponse
//      (F2.16 unified feed; aggregates inventory_logs, order_audit_logs
//      and product_compliance_audit_logs into one normalized shape with
//      a paginated envelope and rich filters).
//
// Sources of truth (do not diverge without updating both sides):
//   - backend/app/schemas/audit.py
//       AuditSource, AuditEntityType, AuditEventRead,
//       AuditEventListResponse
//   - backend/app/services/audit.py
//       list_store_audit
//   - backend/app/api/routes/audit.py
//       GET /stores/{store_id}/audit
//   - backend/app/api/routes/inventory.py
//       list_store_inventory_logs (legacy)
//   - backend/app/schemas/inventory.py
//       InventoryLogRead (legacy)
//
// Type-design decisions (F2.16.4):
//   - `AuditSource` / `AuditEntityType` are string-literal unions, not
//     TS enums. The backend serializes the Pydantic enums as bare
//     strings on the wire (e.g. `"inventory"`, `"inventory_item"`),
//     so string unions match the JSON shape exactly without the
//     runtime overhead and import quirks of TS enums.
//   - `AuditEvent` mirrors the wire-shape of `AuditEventRead`
//     field-by-field. NO derived/display-only fields here
//     (`actor_name`, `actor_email`, `store_name`, `severity`,
//     `source_label`, `entity_label`) — those are not on the wire
//     and inventing them would lie to the UI.
//   - `metadata` is `Record<string, unknown>` because each source
//     contributes a different shape (inventory: quantity_delta /
//     quantity_after / reference_*; order: previous_status /
//     new_status / reason; compliance: previous_* / new_*); UI
//     consumers narrow per-source at the render site.
//   - `StoreAuditFilters` uses snake_case keys to match the backend
//     query params 1:1, so the API layer serializes them verbatim
//     without a mapping step.

import type { InventoryLogEntry } from "@/features/inventory/types";

// Re-exported so audit consumers can import the legacy row shape
// from a single place — `@/features/audit` — without reaching into
// the inventory module's types.
export type { InventoryLogEntry };

/**
 * Wire shape for one row of the store-scoped inventory log endpoint.
 *
 * Alias of `InventoryLogEntry` (same wire shape on both per-store and
 * per-item endpoints). Kept as a named export so call sites express
 * intent clearly and can be re-targeted later if/when the backend
 * grows a richer store-audit shape.
 */
export type StoreInventoryLogEntry = InventoryLogEntry;

/**
 * Parameters for the legacy `getStoreInventoryLogs` function.
 *
 * Mirrors EXACTLY what the legacy backend route accepts:
 *   - storeId: path segment, required.
 *   - limit:   optional query param. Backend default is 100.
 *
 * Deliberately ABSENT (and must NOT be added until the legacy
 * inventory-logs route grows them on its own):
 *   - offset / total / cursor — no paginated envelope on this route.
 *   - user_id, performed_by_user_id — no such filter param.
 *   - event_type, entity_type, movement_type — no such filter param.
 *   - created_from, created_to — no date-range filter.
 *
 * For rich filters and the unified feed, use `StoreAuditFilters` +
 * `getStoreAudit` instead — those target the new F2.16 route.
 */
export interface GetStoreInventoryLogsParams {
  /** Store UUID. Goes into the URL path. */
  storeId: string;
  /**
   * Maximum rows to return. Backend default is 100. Passed verbatim
   * as the `limit` query param when defined; omitted otherwise.
   */
  limit?: number;
}

// --------------------------------------------------------------------- //
// F2.16 unified store audit feed
// --------------------------------------------------------------------- //

/**
 * Source table that produced an audit event.
 *
 * Locked set — adding a new source means extending the backend
 * aggregator AND this union in lockstep. Serialized as a bare
 * string on the wire (no enum-name prefix).
 */
export type AuditSource = "inventory" | "order" | "product_compliance";

/**
 * Business entity the event targets.
 *
 * Distinct from `AuditSource` because the source identifies the
 * underlying log table while the entity identifies what the
 * operator is reasoning about. An inventory event targets an
 * `inventory_item`; an order event targets an `order`; a
 * compliance event targets a `product`.
 */
export type AuditEntityType = "inventory_item" | "order" | "product";

/**
 * One normalized audit event as returned by
 * `GET /stores/{store_id}/audit`.
 *
 * Field-by-field projection of the backend `AuditEventRead`. UUIDs
 * and datetimes are strings on the wire (the backend's
 * `model_dump(mode="json")` serialization). Nullable fields carry
 * `null` (not `undefined`) because that is what the backend emits.
 */
export interface AuditEvent {
  id: string;
  source: AuditSource;
  store_id: string | null;
  actor_id: string | null;
  action: string;
  entity_type: AuditEntityType;
  entity_id: string;
  summary: string;
  /**
   * Source-specific structured payload. Shape varies by source:
   *   - inventory: variant_id, quantity_delta, quantity_after,
   *     reason, reference_type, reference_id.
   *   - order: previous_status, new_status, reason.
   *   - product_compliance: previous_compliance_status,
   *     new_compliance_status, previous_allowed_for_sale,
   *     new_allowed_for_sale, reason.
   * UI consumers narrow per-source at the render site.
   */
  metadata: Record<string, unknown>;
  created_at: string;
}

/**
 * Paginated envelope returned by `GET /stores/{store_id}/audit`.
 *
 * `total` is the full pre-pagination row count (after filters);
 * `items` carries only the current page. `limit` / `offset` echo
 * the request so the UI can render pagination controls without
 * re-deriving them.
 */
export interface AuditListResponse {
  items: AuditEvent[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Optional filters for `getStoreAudit`.
 *
 * Snake_case keys mirror the backend query params 1:1 so the API
 * layer can serialize them verbatim. Every field is optional — an
 * empty filter object requests the unfiltered first page (server
 * applies defaults: limit=50, offset=0).
 */
export interface StoreAuditFilters {
  /**
   * Page size, 1..200. Sent verbatim when defined; backend default
   * applies otherwise.
   */
  limit?: number;
  /**
   * Pagination offset, >=0. Sent verbatim when defined including
   * the explicit `0` case (the API layer preserves a deliberate
   * `offset=0` to distinguish "first page" from "not specified").
   */
  offset?: number;
  source?: AuditSource;
  entity_type?: AuditEntityType;
  /**
   * Free-text action filter (matches the inventory `movement_type`,
   * the order `action`, or the literal `"compliance_changed"`).
   * Empty/whitespace strings are dropped by the API layer.
   */
  action?: string;
  /** Actor UUID. Empty/whitespace strings are dropped. */
  actor_id?: string;
  /** ISO 8601 lower bound for `created_at`. Empty strings dropped. */
  date_from?: string;
  /** ISO 8601 upper bound for `created_at`. Empty strings dropped. */
  date_to?: string;
}

// --------------------------------------------------------------------- //
// F2.18.2B — admin global audit feed (GET /admin/audit)
// --------------------------------------------------------------------- //

/**
 * Optional filters for `getAdminAudit`.
 *
 * Same shape as `StoreAuditFilters` plus an OPTIONAL `store_id`
 * filter (the admin endpoint takes `store_id` as a query param, not
 * a path segment — admins can list across every store or scope to
 * one by setting this filter).
 *
 * Backend route: `app.api.routes.audit::list_admin_audit_endpoint`
 * (F2.17.5). Backend service: `app.services.audit::list_admin_audit`.
 *
 * The admin endpoint accepts EXACTLY the same query params as
 * `StoreAuditFilters` plus `store_id`; no other admin-only filter is
 * defined server-side. Adding fields here without a backend change
 * would create a silent contract divergence.
 *
 * Empty/whitespace strings are dropped by the API layer for every
 * string field (including `store_id`) so a "no filter" UI state
 * doesn't send `?store_id=` (which Pydantic would treat as an
 * invalid UUID and 422).
 */
export interface AdminAuditFilters {
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
   * events across every store the admin can see.
   * Empty/whitespace strings are dropped.
   */
  store_id?: string;
  source?: AuditSource;
  entity_type?: AuditEntityType;
  /** Free-text action filter. Empty/whitespace strings are dropped. */
  action?: string;
  /** Actor UUID. Empty/whitespace strings are dropped. */
  actor_id?: string;
  /** ISO 8601 lower bound for `created_at`. Empty strings dropped. */
  date_from?: string;
  /** ISO 8601 upper bound for `created_at`. Empty strings dropped. */
  date_to?: string;
}
