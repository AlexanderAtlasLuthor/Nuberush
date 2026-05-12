// F2.19.3: admin dashboard API layer.
//
// One pure async function over the backend admin dashboard endpoint
// the feature consumes. Every call goes through `apiRequest` from
// `@/api` so error normalisation, Bearer attach and FastAPI detail
// parsing stay centralised.
//
// Hard rules baked in (mirroring features/audit, features/orders,
// features/inventory):
//   - No fetch() directly.
//   - No React imports.
//   - No TanStack Query imports — that's the hooks layer.
//   - No try/catch: ApiError propagates to the caller untouched.
//   - No business logic: the dashboard aggregation happens
//     server-side; the frontend never recomputes KPIs, never merges
//     audit sources, never densifies the histogram (the backend has
//     already done that).
//   - No store context, no auth/role gating — the backend
//     authorises every read via `require_admin` and the API surfaces
//     401/403 through the centralized `apiRequest` error path.
//
// URL alignment:
//   - GET /admin/dashboard                    (F2.19.1 backend)
//       admin_dashboard.py::get_admin_dashboard_endpoint

import { apiRequest } from "@/api";

import type { AdminDashboardSummary } from "./types";

/**
 * GET /admin/dashboard
 *
 * Returns the admin dashboard summary as a single aggregate object
 * (no pagination envelope). The backend derives every value from
 * existing tables on every call — no persistence, no caching, no
 * fake fallback values.
 *
 * Backend authorisation (F2.19.1):
 *   - `require_admin` — owner / manager / staff / driver → 403.
 *
 * Throws ApiError on:
 *   - 401 (no/invalid token)
 *   - 403 (non-admin caller)
 *   - 5xx (server failure)
 *
 * No path params. No query params. The endpoint takes nothing on the
 * wire beyond the standard `Authorization: Bearer ...` header.
 */
export function getAdminDashboard(
  signal?: AbortSignal,
): Promise<AdminDashboardSummary> {
  return apiRequest<AdminDashboardSummary>("/admin/dashboard", {
    method: "GET",
    signal,
  });
}
