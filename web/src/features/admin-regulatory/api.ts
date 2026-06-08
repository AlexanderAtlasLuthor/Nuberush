// F2.26.6.B: API layer for the admin Regulatory Intelligence feature.
//
// Pure async functions over the `/admin/regulatory` backend routes. Every
// call goes through `apiRequest` from `@/api` so Bearer attach, FastAPI
// `detail` parsing and `ApiError` normalisation stay centralised.
//
// Hard rules baked in (mirroring features/audit, features/admin-compliance):
//   - No fetch() directly.
//   - No Supabase / session imports — `apiRequest` owns auth.
//   - No auth/store context imports.
//   - No React, no TanStack Query — that's the hooks layer.
//   - No try/catch: ApiError propagates to the caller untouched.
//   - No business logic: lifecycle decisions, compliance changes and audit
//     writes all happen server-side; the frontend only relays the request.
//
// Endpoint alignment (backend admin_regulatory.py):
//   - GET  /admin/regulatory/alerts                          (list)
//   - GET  /admin/regulatory/alerts/{alert_id}               (detail)
//   - GET  /admin/regulatory/alerts/{alert_id}/decisions     (F2.26.6.A)
//   - POST /admin/regulatory/alerts/{alert_id}/acknowledge
//   - POST /admin/regulatory/alerts/{alert_id}/dismiss
//   - POST /admin/regulatory/alerts/{alert_id}/resolve

import { apiRequest } from "@/api";
import type {
  ComplianceAlert,
  ComplianceAlertActionRequest,
  ComplianceAlertAggregate,
  ComplianceAlertFilters,
  ComplianceAlertListResponse,
  ComplianceAlertResolveRequest,
  RegulatoryDecisionAuditLogListResponse,
  RegulatoryDecisionAuditLogParams,
} from "./types";

const ALERTS_PATH = "/admin/regulatory/alerts";
const AGGREGATE_PATH = "/admin/regulatory/aggregate";

/**
 * Trim a string filter, dropping it entirely when empty. Keeps a "no filter"
 * UI state from sending `?product_id=` (which Pydantic would treat as the
 * literal empty string and 422). Mirrors features/audit's `trimOrUndefined`.
 */
function trimOrUndefined(value: string | undefined): string | undefined {
  if (value === undefined) return undefined;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

/**
 * Serialize the shared alert filter dimensions (status / severity /
 * recommended_action / product_id / notice_id) onto a URLSearchParams. Single
 * source of truth so the list and the aggregate (F2.27.5) always send an
 * identical filter surface and can never drift. `limit` / `offset` are NOT
 * handled here — they are list-only pagination, irrelevant to the aggregate.
 */
function appendAlertFilters(
  search: URLSearchParams,
  filters: ComplianceAlertFilters,
): void {
  if (filters.status !== undefined) {
    search.set("status", filters.status);
  }
  if (filters.severity !== undefined) {
    search.set("severity", filters.severity);
  }
  if (filters.recommended_action !== undefined) {
    search.set("recommended_action", filters.recommended_action);
  }
  const productId = trimOrUndefined(filters.product_id);
  if (productId !== undefined) {
    search.set("product_id", productId);
  }
  const noticeId = trimOrUndefined(filters.notice_id);
  if (noticeId !== undefined) {
    search.set("notice_id", noticeId);
  }
}

// --------------------------------------------------------------------- //
// Reads
// --------------------------------------------------------------------- //

/**
 * GET /admin/regulatory/alerts
 *
 * Paginated, newest-first list of compliance alerts. Query serialization:
 *   - `limit` / `offset`: forwarded verbatim when defined, INCLUDING explicit
 *     `0` (a deliberate "first page" must survive on the wire).
 *   - `status` / `severity` / `recommended_action`: enum literals forwarded
 *     verbatim when defined.
 *   - `product_id` / `notice_id`: trimmed; empty strings are dropped.
 *
 * Backend auth: `require_admin` (anon → 401, non-admin → 403).
 */
export function getAdminRegulatoryAlerts(
  filters: ComplianceAlertFilters = {},
  signal?: AbortSignal,
): Promise<ComplianceAlertListResponse> {
  const search = new URLSearchParams();

  if (filters.limit !== undefined) {
    search.set("limit", String(filters.limit));
  }
  if (filters.offset !== undefined) {
    // Preserve explicit offset=0 — that's "first page", not "skip".
    search.set("offset", String(filters.offset));
  }
  appendAlertFilters(search, filters);

  const query = search.toString();
  const path = `${ALERTS_PATH}${query ? `?${query}` : ""}`;
  return apiRequest<ComplianceAlertListResponse>(path, {
    method: "GET",
    signal,
  });
}

/**
 * GET /admin/regulatory/aggregate  (F2.27.5)
 *
 * Global, dense-by-enum counts of compliance alerts for the active filters,
 * computed server-side BEFORE pagination. Sends the SAME filter surface as
 * `getAdminRegulatoryAlerts` (minus `limit`/`offset`, which are list-only),
 * so the KPI cards reflect every matching alert, not just the current page.
 *
 * Backend auth: `require_admin` (anon → 401, non-admin → 403).
 */
export function getAdminRegulatoryAggregate(
  filters: ComplianceAlertFilters = {},
  signal?: AbortSignal,
): Promise<ComplianceAlertAggregate> {
  const search = new URLSearchParams();
  appendAlertFilters(search, filters);

  const query = search.toString();
  const path = `${AGGREGATE_PATH}${query ? `?${query}` : ""}`;
  return apiRequest<ComplianceAlertAggregate>(path, {
    method: "GET",
    signal,
  });
}

/**
 * GET /admin/regulatory/alerts/{alert_id}
 *
 * Single compliance alert. Missing alert → 404. Backend auth: `require_admin`.
 */
export function getAdminRegulatoryAlert(
  alertId: string,
  signal?: AbortSignal,
): Promise<ComplianceAlert> {
  const path = `${ALERTS_PATH}/${encodeURIComponent(alertId)}`;
  return apiRequest<ComplianceAlert>(path, { method: "GET", signal });
}

/**
 * GET /admin/regulatory/alerts/{alert_id}/decisions  (F2.26.6.A)
 *
 * Paginated, newest-first (created_at DESC, id ASC) decision trail for one
 * alert. Query serialization mirrors the list:
 *   - `limit` / `offset`: forwarded verbatim when defined, including `0`.
 *
 * Missing alert → 404. Backend auth: `require_admin`.
 */
export function getAdminRegulatoryAlertDecisions(
  alertId: string,
  params: RegulatoryDecisionAuditLogParams = {},
  signal?: AbortSignal,
): Promise<RegulatoryDecisionAuditLogListResponse> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) {
    search.set("limit", String(params.limit));
  }
  if (params.offset !== undefined) {
    // Preserve explicit offset=0 — that's "first page", not "skip".
    search.set("offset", String(params.offset));
  }

  const query = search.toString();
  const path = `${ALERTS_PATH}/${encodeURIComponent(alertId)}/decisions${
    query ? `?${query}` : ""
  }`;
  return apiRequest<RegulatoryDecisionAuditLogListResponse>(path, {
    method: "GET",
    signal,
  });
}

// --------------------------------------------------------------------- //
// Lifecycle mutations (relay only — all behaviour is server-side)
// --------------------------------------------------------------------- //

/**
 * POST /admin/regulatory/alerts/{alert_id}/acknowledge
 *
 * Marks an open alert acknowledged (seen, not resolved). No product/compliance
 * change. Backend auth: `require_admin`.
 */
export function acknowledgeAdminRegulatoryAlert(
  alertId: string,
  body: ComplianceAlertActionRequest,
): Promise<ComplianceAlert> {
  const path = `${ALERTS_PATH}/${encodeURIComponent(alertId)}/acknowledge`;
  return apiRequest<ComplianceAlert>(path, { method: "POST", body });
}

/**
 * POST /admin/regulatory/alerts/{alert_id}/dismiss
 *
 * Closes an alert as dismissed. No product/compliance change. Backend auth:
 * `require_admin`.
 */
export function dismissAdminRegulatoryAlert(
  alertId: string,
  body: ComplianceAlertActionRequest,
): Promise<ComplianceAlert> {
  const path = `${ALERTS_PATH}/${encodeURIComponent(alertId)}/dismiss`;
  return apiRequest<ComplianceAlert>(path, { method: "POST", body });
}

/**
 * POST /admin/regulatory/alerts/{alert_id}/resolve
 *
 * Resolves an alert (no_action / hold / ban). For hold/ban the backend applies
 * the real compliance change exclusively via `set_product_compliance()` — the
 * frontend never touches product/inventory state. Backend auth: `require_admin`.
 */
export function resolveAdminRegulatoryAlert(
  alertId: string,
  body: ComplianceAlertResolveRequest,
): Promise<ComplianceAlert> {
  const path = `${ALERTS_PATH}/${encodeURIComponent(alertId)}/resolve`;
  return apiRequest<ComplianceAlert>(path, { method: "POST", body });
}
