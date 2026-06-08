// F2.26.6.B: TypeScript contracts for the admin Regulatory Intelligence
// feature (compliance alerts + per-alert decision trail).
//
// Snake_case on every field — these interfaces mirror the FastAPI response
// and request bodies verbatim (see backend/app/schemas/regulatory.py and the
// F2.26.6.A decision-trail endpoint). No frontend-only camelCase remapping,
// no codegen: the wire contract is the contract.
//
// Enum-like values are declared as string-literal unions (the project
// convention — see features/admin-compliance/types.ts), not TS `enum`s, so
// they erase at build time and compare structurally against the JSON.

// --------------------------------------------------------------------- //
// Enums (string-literal unions matching the backend enum string values)
// --------------------------------------------------------------------- //

/**
 * Lifecycle status of a compliance alert.
 * Backend: `ComplianceAlertStatus` (open → acknowledged/actioned/dismissed).
 */
export type ComplianceAlertStatus =
  | "open"
  | "acknowledged"
  | "actioned"
  | "dismissed";

/** Backend: `ComplianceAlertSeverity`. */
export type ComplianceAlertSeverity = "low" | "medium" | "high" | "critical";

/**
 * Advisory action surfaced on an alert. Advisory ONLY — never an applied
 * mutation. Backend: `ComplianceRecommendedAction`.
 */
export type ComplianceRecommendedAction = "none" | "hold" | "ban";

/**
 * Terminal `resolve` actions an admin may take. `dismiss` is a separate
 * lifecycle verb (its own endpoint), so it is intentionally absent here.
 * Backend: `ComplianceAlertResolutionAction`.
 */
export type ComplianceAlertResolutionAction = "no_action" | "hold" | "ban";

/**
 * Closed verb set recorded on an append-only regulatory decision audit row.
 * Backend: `RegulatoryDecisionAction` (F2.26.6.A).
 */
export type RegulatoryDecisionAction =
  | "alert_acknowledged"
  | "alert_dismissed"
  | "alert_resolved_hold"
  | "alert_resolved_ban"
  | "alert_resolved_no_action";

// --------------------------------------------------------------------- //
// Compliance alert
// --------------------------------------------------------------------- //

/**
 * A human-reviewable compliance alert. `recommended_action` is advisory; the
 * `resolved_*` fields are populated together only once an admin closes the
 * alert. Backend: `ComplianceAlertRead`.
 */
export interface ComplianceAlert {
  id: string;
  notice_id: string;
  product_id: string | null;
  match_id: string | null;
  severity: ComplianceAlertSeverity;
  status: ComplianceAlertStatus;
  recommended_action: ComplianceRecommendedAction;
  resolution_note: string | null;
  resolved_by_user_id: string | null;
  resolved_at: string | null;
  created_at: string;
  updated_at: string;
}

/** Paginated envelope for compliance alerts. Backend: `ComplianceAlertListResponse`. */
export interface ComplianceAlertListResponse {
  items: ComplianceAlert[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Global, dense-by-enum counts of compliance alerts (F2.27.5). Computed
 * server-side BEFORE pagination, so these are TRUE global counts for the
 * active filters — never derived from a single page of rows. The backend
 * densifies every map so every enum key is present (zero-filled). Backend:
 * `ComplianceAlertAggregate`.
 */
export interface ComplianceAlertAggregate {
  total: number;
  by_status: Record<ComplianceAlertStatus, number>;
  by_severity: Record<ComplianceAlertSeverity, number>;
  by_recommended_action: Record<ComplianceRecommendedAction, number>;
}

/**
 * Optional query filters for the alert list. Mirrors the
 * `GET /admin/regulatory/alerts` query params. All optional; omitted /
 * empty filters are dropped from the query string by the API layer.
 */
export interface ComplianceAlertFilters {
  limit?: number;
  offset?: number;
  status?: ComplianceAlertStatus;
  severity?: ComplianceAlertSeverity;
  recommended_action?: ComplianceRecommendedAction;
  product_id?: string;
  notice_id?: string;
}

// --------------------------------------------------------------------- //
// Regulatory decision audit log (decision trail) — F2.26.6.A
// --------------------------------------------------------------------- //

/**
 * One append-only decision audit row for a compliance alert. `before` /
 * `after` / `metadata` are opaque JSON snapshots. The wire field is
 * `metadata` (the backend serialization alias). Backend:
 * `RegulatoryDecisionAuditLogRead`.
 */
export interface RegulatoryDecisionAuditLog {
  id: string;
  alert_id: string;
  notice_id: string;
  product_id: string | null;
  actor_user_id: string;
  action: RegulatoryDecisionAction;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  metadata: Record<string, unknown> | null;
  reason: string;
  created_at: string;
}

/** Paginated envelope for decision audit rows. Backend: `RegulatoryDecisionAuditLogListResponse`. */
export interface RegulatoryDecisionAuditLogListResponse {
  items: RegulatoryDecisionAuditLog[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Query params for the per-alert decision trail
 * (`GET /admin/regulatory/alerts/{alert_id}/decisions`). The `alert_id`
 * itself is a path segment, not a filter, so it is not included here.
 */
export interface RegulatoryDecisionAuditLogParams {
  limit?: number;
  offset?: number;
}

// --------------------------------------------------------------------- //
// Lifecycle request bodies
// --------------------------------------------------------------------- //

/**
 * Body for the non-resolving lifecycle verbs (acknowledge / dismiss).
 * `reason` is required and non-empty. Backend: `ComplianceAlertActionRequest`.
 */
export interface ComplianceAlertActionRequest {
  reason: string;
}

/**
 * Body for resolving an alert (no_action / hold / ban). `resolution_note` is
 * required and non-empty. Backend: `ComplianceAlertResolveRequest`.
 */
export interface ComplianceAlertResolveRequest {
  action: ComplianceAlertResolutionAction;
  resolution_note: string;
}
