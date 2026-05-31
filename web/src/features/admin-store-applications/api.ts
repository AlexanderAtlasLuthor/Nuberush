// F2.24.C7: admin store-applications API layer.
//
// Pure async functions over the backend admin store-applications
// endpoints. Every call goes through `apiRequest` from `@/api` so error
// normalisation, Bearer attach and FastAPI detail parsing stay
// centralised.
//
// Hard rules baked in (mirroring features/stores, features/users):
//   - No fetch() directly.
//   - No React imports.
//   - No TanStack Query imports — those live in ./hooks.
//   - No Supabase client — no `.from()` / `.rpc()`. Business reads and
//     writes go through the backend, which is authoritative for RLS,
//     provisioning, and audit logging.
//   - No try/catch: ApiError propagates to the caller untouched.
//   - No business logic: no client-side permission checks, no
//     snake_case → camelCase mapping.
//   - Never send server-owned fields. Approve sends no body; reject
//     sends ONLY `{ rejection_reason }`.
//
// URL alignment (verified against
// backend/app/api/routes/admin_store_applications.py and
// `app.include_router(admin_store_applications_router)` in app/main.py —
// the router hardcodes the `/admin/store-applications` prefix):
//
//   GET    /admin/store-applications                         (list)
//   GET    /admin/store-applications/{application_id}        (detail)
//   POST   /admin/store-applications/{application_id}/approve
//   POST   /admin/store-applications/{application_id}/reject

import { apiRequest } from "@/api";
import type {
  StoreApplicationDetail,
  StoreApplicationListFilters,
  StoreApplicationListResponse,
  StoreApplicationRejectRequest,
  StoreApplicationReviewResponse,
} from "./types";

const BASE_PATH = "/admin/store-applications";

// --------------------------------------------------------------------- //
// listStoreApplications (admin-only paginated list)
// --------------------------------------------------------------------- //

/**
 * GET /admin/store-applications
 *
 * Returns the paginated `StoreApplicationListResponse`. Optional filters
 * are serialised as query params; empty / undefined fields are dropped so
 * the cache key stays stable across logically equivalent filter sets.
 *
 * Throws ApiError on:
 *   - 401 (missing/invalid token)
 *   - 403 (non-admin caller — `require_admin` rejects everyone else)
 */
export function listStoreApplications(
  filters: StoreApplicationListFilters = {},
  signal?: AbortSignal,
): Promise<StoreApplicationListResponse> {
  const query = new URLSearchParams();
  if (filters.limit !== undefined) {
    query.set("limit", String(filters.limit));
  }
  if (filters.offset !== undefined) {
    query.set("offset", String(filters.offset));
  }
  if (filters.status !== undefined) {
    query.set("status", filters.status);
  }
  if (filters.q !== undefined && filters.q.length > 0) {
    query.set("q", filters.q);
  }
  const qs = query.toString();
  const path = `${BASE_PATH}${qs.length > 0 ? `?${qs}` : ""}`;
  return apiRequest<StoreApplicationListResponse>(path, { signal });
}

// --------------------------------------------------------------------- //
// getStoreApplication (admin-only detail)
// --------------------------------------------------------------------- //

/**
 * GET /admin/store-applications/{application_id}
 *
 * Returns the full `StoreApplicationDetail` (including `audit_logs`).
 *
 * Throws ApiError on:
 *   - 401 / 403 (auth)
 *   - 404 (application id does not exist)
 */
export function getStoreApplication(
  applicationId: string,
  signal?: AbortSignal,
): Promise<StoreApplicationDetail> {
  const path = `${BASE_PATH}/${encodeURIComponent(applicationId)}`;
  return apiRequest<StoreApplicationDetail>(path, { signal });
}

// --------------------------------------------------------------------- //
// approveStoreApplication (admin-only; atomic provisioning)
// --------------------------------------------------------------------- //

export interface ApproveStoreApplicationParams {
  /** Application UUID. */
  applicationId: string;
}

/**
 * POST /admin/store-applications/{application_id}/approve
 *
 * Admin-only. The backend atomically provisions a store + owner user +
 * Auth user and marks the application approved. NO request body is sent —
 * the frontend never supplies role/store/user/Auth fields; provisioning
 * is entirely server-owned.
 *
 * Returns `StoreApplicationReviewResponse` with `provisioned_store_id`
 * and `provisioned_owner_user_id` populated.
 *
 * Throws ApiError on:
 *   - 401 / 403 (auth)
 *   - 404 (application not found)
 *   - 409 (no longer pending_review, or a provisioning collision)
 *   - 502 / 500 (identity provider / DB failure during provisioning)
 */
export function approveStoreApplication(
  params: ApproveStoreApplicationParams,
  signal?: AbortSignal,
): Promise<StoreApplicationReviewResponse> {
  const path = `${BASE_PATH}/${encodeURIComponent(params.applicationId)}/approve`;
  return apiRequest<StoreApplicationReviewResponse>(path, {
    method: "POST",
    signal,
  });
}

// --------------------------------------------------------------------- //
// rejectStoreApplication (admin-only; requires a reason)
// --------------------------------------------------------------------- //

export interface RejectStoreApplicationParams {
  /** Application UUID. */
  applicationId: string;
  /** Non-blank rejection reason. Backend re-validates 1..2000 chars. */
  body: StoreApplicationRejectRequest;
}

/**
 * POST /admin/store-applications/{application_id}/reject
 *
 * Admin-only. Sends ONLY `{ rejection_reason }` — no reviewer/store/user
 * fields (the backend forbids extras via `extra="forbid"` and stamps the
 * reviewer from the authenticated admin).
 *
 * Returns `StoreApplicationReviewResponse` with `rejection_reason` set.
 *
 * Throws ApiError on:
 *   - 401 / 403 (auth)
 *   - 404 (application not found)
 *   - 409 (no longer pending_review)
 *   - 422 (blank/too-long reason)
 */
export function rejectStoreApplication(
  params: RejectStoreApplicationParams,
  signal?: AbortSignal,
): Promise<StoreApplicationReviewResponse> {
  const path = `${BASE_PATH}/${encodeURIComponent(params.applicationId)}/reject`;
  return apiRequest<StoreApplicationReviewResponse>(path, {
    method: "POST",
    body: params.body,
    signal,
  });
}
