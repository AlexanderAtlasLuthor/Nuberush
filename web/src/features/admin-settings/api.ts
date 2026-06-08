// Admin settings API layer.
//
// One pure async function over `GET /admin/settings`. Goes through
// `apiRequest` from `@/api` so error normalisation, Bearer attach and
// FastAPI detail parsing stay centralised.
//
// Hard rules baked in (mirroring features/admin-compliance/api.ts):
//   - No fetch() directly.
//   - No React imports.
//   - No TanStack Query imports — that's the hooks layer.
//   - No try/catch: ApiError propagates to the caller untouched.
//   - No business logic: every value on the response is produced by
//     the backend.
//   - No store context, no role gating — the backend authorises every
//     read via `require_admin`.

import { apiRequest } from "@/api";

import type {
  AdminSettingsResponse,
  AdminSettingsUpdateRequest,
} from "./types";

/**
 * GET /admin/settings
 *
 * Returns the admin settings snapshot envelope. Backend-computed on
 * every request from existing tables and locked constants — no
 * persistence behind the endpoint.
 *
 * Throws ApiError on:
 *   - 401 (no/invalid token)
 *   - 403 (non-admin caller)
 *   - 5xx (server failure)
 */
export function getAdminSettings(
  signal?: AbortSignal,
): Promise<AdminSettingsResponse> {
  return apiRequest<AdminSettingsResponse>("/admin/settings", {
    method: "GET",
    signal,
  });
}

/**
 * PATCH /admin/settings  (F2.27.10)
 *
 * Partial update of the writable platform-settings cluster. Sends only the
 * fields the caller supplies (snake_case, matching the backend
 * `AdminSettingsUpdate`); the backend persists the change, writes a dedicated
 * audit row, and returns the full refreshed `AdminSettingsResponse`.
 *
 * Backend auth: `require_admin` (anon → 401, non-admin → 403). Unknown or
 * env-backed fields → 422. No store context, no role gating client-side.
 */
export function patchAdminSettings(
  payload: AdminSettingsUpdateRequest,
): Promise<AdminSettingsResponse> {
  return apiRequest<AdminSettingsResponse>("/admin/settings", {
    method: "PATCH",
    body: payload,
  });
}
