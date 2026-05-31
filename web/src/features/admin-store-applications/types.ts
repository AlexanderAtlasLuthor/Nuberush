// F2.24.C7: admin store-applications wire types.
//
// `features/admin-store-applications/` — admin review of merchant
// onboarding applications (list / detail / approve / reject). This is a
// distinct namespace from the public intake feature
// `features/store-applications/` (the `/apply` wizard); the two never
// share types because the wire contracts differ (public submit vs.
// admin review).
//
// Sources of truth (do not diverge without updating both sides):
//   - backend/app/schemas/store_applications.py
//       StoreApplicationListItem, StoreApplicationListResponse,
//       StoreApplicationDetailResponse, StoreApplicationAuditLogRead,
//       StoreApplicationRejectRequest, StoreApplicationReviewResponse
//   - backend/app/api/routes/admin_store_applications.py
//       GET    /admin/store-applications
//       GET    /admin/store-applications/{application_id}
//       POST   /admin/store-applications/{application_id}/approve
//       POST   /admin/store-applications/{application_id}/reject
//
// Type-design decisions (mirror features/stores, features/users):
//   - Datetime fields are ISO-8601 strings from the wire.
//   - UUIDs are strings.
//   - Snake_case wire contract — no camelCase here.
//   - No business logic, no permission flags. Backend `require_admin`
//     is authoritative for who can list/review; the frontend forwards
//     the request and surfaces the resulting 401/403.

/**
 * Lifecycle status of a store application. Mirrors the backend
 * `StoreApplicationStatus` enum exactly. In F2.24 only `pending_review`,
 * `approved`, and `rejected` are operational, but `draft`/`submitted`
 * exist for forward compatibility and the UI renders them read-only.
 */
export type StoreApplicationStatus =
  | "draft"
  | "submitted"
  | "pending_review"
  | "approved"
  | "rejected";

/**
 * Filter set for `GET /admin/store-applications` (and the matching cache
 * key). Every field is optional. The endpoint is admin-only — non-admins
 * get 401/403 before any filter is read.
 *
 * Field bounds (backend authoritative):
 *   - `limit`: 1..200, default 50 server-side.
 *   - `offset`: >= 0, default 0 server-side.
 *   - `status`: optional status filter.
 *   - `q`: case-insensitive ILIKE across business_name,
 *     owner_full_name, owner_email (trimmed; whitespace-only collapses
 *     to none server-side).
 */
export interface StoreApplicationListFilters {
  limit?: number;
  offset?: number;
  status?: StoreApplicationStatus;
  q?: string;
}

/**
 * One row in the admin list. Mirrors backend `StoreApplicationListItem`.
 */
export interface StoreApplicationListItem {
  id: string;
  business_name: string;
  business_type: string;
  owner_full_name: string;
  owner_email: string;
  status: StoreApplicationStatus;
  location_count: number;
  estimated_weekly_orders: number | null;
  city: string;
  state: string;
  submitted_at: string | null;
  reviewed_at: string | null;
  created_at: string;
}

/**
 * Paginated envelope returned by `GET /admin/store-applications`.
 * Mirrors backend `StoreApplicationListResponse` exactly.
 */
export interface StoreApplicationListResponse {
  items: StoreApplicationListItem[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * One audit-log entry attached to an application detail. Mirrors backend
 * `StoreApplicationAuditLogRead`.
 */
export interface StoreApplicationAuditLog {
  id: string;
  application_id: string;
  event_type: string;
  actor_user_id: string | null;
  message: string | null;
  payload: Record<string, unknown> | null;
  created_at: string;
}

/**
 * Full application detail. Mirrors backend `StoreApplicationDetailResponse`
 * (the `StoreApplicationRead` row plus its `audit_logs`).
 *
 * Server-owned fields (status, timestamps, reviewer, rejection reason,
 * provisioned ids, lookup token) are read-only here — the admin UI never
 * sends them back.
 */
export interface StoreApplicationDetail {
  id: string;
  // Business information
  business_name: string;
  business_type: string;
  // Owner / contact information
  owner_full_name: string;
  owner_email: string;
  owner_phone: string;
  business_phone: string | null;
  // Address
  address_line_1: string;
  address_line_2: string | null;
  city: string;
  state: string;
  postal_code: string;
  country: string;
  // Operations
  location_count: number;
  estimated_weekly_orders: number | null;
  hours_of_operation: string | null;
  website_url: string | null;
  social_url: string | null;
  notes: string | null;
  // Terms
  terms_accepted: boolean;
  terms_accepted_at: string | null;
  // Server-owned review state
  status: StoreApplicationStatus;
  submitted_at: string | null;
  reviewed_at: string | null;
  reviewed_by_user_id: string | null;
  rejection_reason: string | null;
  provisioned_store_id: string | null;
  provisioned_owner_user_id: string | null;
  public_lookup_token: string;
  created_at: string;
  updated_at: string;
  audit_logs: StoreApplicationAuditLog[];
}

/**
 * Response for both approve and reject. Mirrors backend
 * `StoreApplicationReviewResponse`. `provisioned_*` are populated on
 * approve; `rejection_reason` on reject.
 */
export interface StoreApplicationReviewResponse {
  id: string;
  status: StoreApplicationStatus;
  reviewed_by_user_id: string | null;
  reviewed_at: string | null;
  provisioned_store_id: string | null;
  provisioned_owner_user_id: string | null;
  rejection_reason: string | null;
  message: string;
}

/**
 * Body accepted by `POST /admin/store-applications/{id}/reject`.
 * Mirrors backend `StoreApplicationRejectRequest` (with `extra="forbid"`).
 * ONLY `rejection_reason` is sent — never reviewer/store/user/role fields.
 */
export interface StoreApplicationRejectRequest {
  rejection_reason: string;
}
