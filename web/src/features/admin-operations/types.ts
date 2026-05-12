// F2.19.4: admin operations alerts wire types.
//
// 1:1 mirror of the FastAPI admin operations contract. Field names
// and casing match the JSON over the wire exactly (snake_case). The
// schemas are owned by the backend feature module
// `backend/app/schemas/admin_operations.py` — do NOT camelCase here.
//
// Sources of truth (keep in lockstep):
//   - backend/app/schemas/admin_operations.py
//       AdminOperationsAlertCategory, AdminOperationsAlertSeverity,
//       AdminOperationsAlertEntityType, AdminOperationsAlert,
//       AdminOperationsAlertsListResponse
//   - backend/app/services/admin_operations.py
//       list_admin_operations_alerts
//   - backend/app/api/routes/admin_operations.py
//       GET /admin/operations/alerts
//   - docs/f2.19-contract-lock.md §3.2
//
// Type-design decisions (mirroring features/audit/types.ts):
//   - `AdminOperationsAlertCategory` / `Severity` / `EntityType` are
//     string-literal unions, not TS enums. The backend serializes
//     the Pydantic enums as bare strings on the wire, so unions
//     match the JSON shape exactly without enum-runtime overhead.
//   - `AdminOperationsAlert` mirrors the wire shape field-by-field.
//     NO derived/display-only fields here (badge label, severity
//     color, entity_label) — those are not on the wire and inventing
//     them would lie to the UI.
//   - `AdminOperationsAlertsFilters` uses snake_case keys to match
//     the backend query params 1:1, so the API layer can serialize
//     them verbatim without a mapping step.

/**
 * Locked alert category set (F2.19.0 §3.2.2). Five categories cover
 * the operational surfaces this phase exposes; adding a new value
 * requires both a backend update and a contract update.
 */
export type AdminOperationsAlertCategory =
  | "low_stock"
  | "aging_order"
  | "compliance_blocker"
  | "inactive_store"
  | "store_no_inventory";

/**
 * Locked severity set (F2.19.0 §3.2.3). Three discrete levels. The
 * DESC priority `high > medium > low` is enforced by the backend
 * sort; the frontend never re-orders by severity.
 */
export type AdminOperationsAlertSeverity = "low" | "medium" | "high";

/**
 * Business entity the alert targets (F2.19.0 §3.2). Distinct from
 * `category` because two different categories can target the same
 * entity type (`inactive_store` and `store_no_inventory` both point
 * at `store`).
 */
export type AdminOperationsAlertEntityType =
  | "store"
  | "inventory_item"
  | "order"
  | "product";

/**
 * One computed alert row as returned by
 * `GET /admin/operations/alerts`. Field-by-field projection of the
 * backend `AdminOperationsAlert` schema.
 *
 * `id` is a deterministic, category-prefixed string the backend
 * derives from the underlying row (no persistence layer):
 *   - low_stock:<inventory_item_id>
 *   - aging_order:<order_id>:<aging_minutes>
 *   - compliance_blocker:<product_id>
 *   - inactive_store:<store_id>
 *   - store_no_inventory:<store_id>
 *
 * `store_id` is nullable. Today the only category that emits a null
 * `store_id` is `compliance_blocker` (Product has no `store_id`
 * column in the current model). Filtering by `store_id` excludes
 * alerts with `store_id === null` — see the backend contract for
 * the exact semantics.
 */
export interface AdminOperationsAlert {
  id: string;
  category: AdminOperationsAlertCategory;
  severity: AdminOperationsAlertSeverity;
  store_id: string | null;
  entity_type: AdminOperationsAlertEntityType;
  entity_id: string;
  summary: string;
  created_at: string;
}

/**
 * Optional filters for `getAdminOperationsAlerts`.
 *
 * Snake_case keys mirror the backend query params 1:1 so the API
 * layer can serialize them verbatim. Every field is optional — an
 * empty filter object requests the unfiltered first page (server
 * applies defaults: limit=50, offset=0, aging_minutes=1440).
 */
export interface AdminOperationsAlertsFilters {
  /** Page size, 1..200. Sent verbatim when defined. */
  limit?: number;
  /**
   * Pagination offset, >=0. Sent verbatim when defined — the API
   * layer preserves an explicit `offset=0` to distinguish "first
   * page" from "not specified".
   */
  offset?: number;
  category?: AdminOperationsAlertCategory;
  severity?: AdminOperationsAlertSeverity;
  /**
   * Optional store scope. Empty / whitespace-only values are dropped
   * by the API layer (Pydantic would otherwise 422 on the literal
   * empty string).
   */
  store_id?: string;
  /**
   * Aging threshold in minutes (>=1, default 1440). Drives both the
   * `aging_order` inclusion predicate and the deterministic id
   * suffix; the same alert under different thresholds has different
   * ids.
   */
  aging_minutes?: number;
}

/**
 * Paginated response envelope returned by
 * `GET /admin/operations/alerts`.
 *
 * `total` is the full filtered count BEFORE pagination is applied
 * (computed server-side after category / severity / store_id /
 * aging_minutes filtering, before offset/limit slicing). `items`
 * carries only the current page; `limit` / `offset` echo the
 * request so the UI can render pagination controls without
 * re-deriving them.
 */
export interface AdminOperationsAlertsListResponse {
  items: AdminOperationsAlert[];
  total: number;
  limit: number;
  offset: number;
}
