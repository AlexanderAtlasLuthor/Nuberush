// F2.19.4: admin operations alerts API layer.
//
// One pure async function over the backend admin operations alerts
// endpoint the feature consumes. Every call goes through `apiRequest`
// from `@/api` so error normalisation, Bearer attach and FastAPI
// detail parsing stay centralised.
//
// Hard rules baked in (mirroring features/admin-dashboard, features/audit,
// features/orders):
//   - No fetch() directly.
//   - No React imports.
//   - No TanStack Query imports — that's the hooks layer.
//   - No try/catch: ApiError propagates to the caller untouched.
//   - No business logic: alert computation, sorting, severity rules,
//     and id derivation all happen server-side. The frontend never
//     synthesises alerts, never re-orders them, never relabels them.
//   - No store context, no auth/role gating — the backend authorises
//     every read via `require_admin` and the API surfaces 401/403
//     through the centralized `apiRequest` error path.
//   - No call to `/admin/dashboard` — that's a different feature.
//
// URL alignment:
//   - GET /admin/operations/alerts            (F2.19.2 backend)
//       admin_operations.py::list_admin_operations_alerts_endpoint

import { apiRequest } from "@/api";

import type {
  AdminOperationsAlertsFilters,
  AdminOperationsAlertsListResponse,
} from "./types";

function trimOrUndefined(
  value: string | undefined | null,
): string | undefined {
  // Defensively accept `null` even though the TS signature forbids
  // it — a JS caller (e.g. an untyped form binding) can leak null
  // for "cleared" inputs, and we want to drop it like undefined
  // rather than crash on `null.trim()`.
  if (value === undefined || value === null) return undefined;
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

/**
 * GET /admin/operations/alerts
 *
 * Returns a paginated, filterable list of operational alerts
 * computed on the backend from existing tables. No persistence sits
 * behind this endpoint — the same call produces the same alerts
 * (deterministic ids) as long as the underlying rows don't change.
 *
 * Backend authorisation (F2.19.2):
 *   - `require_admin` — owner / manager / staff / driver → 403.
 *
 * Query serialization rules (mirror the F2.19.0 §3.2.1 contract):
 *   - `limit` / `offset` / `aging_minutes`: forwarded verbatim when
 *     defined (including the explicit `0` case, so the server-side
 *     `Query(ge=1, le=200)` / `Query(ge=0)` / `Query(ge=1)` produces
 *     a clean 422 for validation tests rather than the frontend
 *     silently dropping the param).
 *   - `category` / `severity`: forwarded verbatim when defined.
 *   - `store_id`: trimmed; empty / whitespace-only values are
 *     dropped so a "no filter" UI state doesn't send `?store_id=`
 *     (which Pydantic would treat as an invalid UUID and 422).
 *
 * Throws ApiError on:
 *   - 401 (no/invalid token)
 *   - 403 (non-admin caller)
 *   - 422 (query enum / UUID / bounds validation)
 *   - 5xx (server failure)
 */
export function getAdminOperationsAlerts(
  filters: AdminOperationsAlertsFilters = {},
  signal?: AbortSignal,
): Promise<AdminOperationsAlertsListResponse> {
  const search = new URLSearchParams();

  if (filters.limit !== undefined && filters.limit !== null) {
    // Preserve explicit `0` (and other invalid values) so the
    // backend's `Query(ge=1, le=200)` produces a deterministic 422
    // rather than the frontend silently substituting the default.
    search.set("limit", String(filters.limit));
  }
  if (filters.offset !== undefined && filters.offset !== null) {
    // Preserve explicit offset=0 — that's "first page", not "skip".
    search.set("offset", String(filters.offset));
  }
  if (filters.category !== undefined && filters.category !== null) {
    search.set("category", filters.category);
  }
  if (filters.severity !== undefined && filters.severity !== null) {
    search.set("severity", filters.severity);
  }

  const storeId = trimOrUndefined(filters.store_id);
  if (storeId !== undefined) {
    search.set("store_id", storeId);
  }

  if (
    filters.aging_minutes !== undefined &&
    filters.aging_minutes !== null
  ) {
    // Preserve explicit aging_minutes=0 so the backend's
    // `Query(ge=1)` produces a 422 rather than the frontend
    // silently applying the default.
    search.set("aging_minutes", String(filters.aging_minutes));
  }

  const query = search.toString();
  const path = `/admin/operations/alerts${query ? `?${query}` : ""}`;
  return apiRequest<AdminOperationsAlertsListResponse>(path, {
    method: "GET",
    signal,
  });
}
