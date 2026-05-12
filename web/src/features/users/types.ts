// F2.9.1: users wire types.
//
// 1:1 mirror of the FastAPI users contract surfaced by POST /auth/users
// and GET /auth/me. Field names and casing match the JSON over the wire
// exactly (snake_case). Do NOT camelCase here; that mapping, if ever
// needed, belongs in the UI layer.
//
// Sources of truth (do not diverge without updating both sides):
//   - backend/app/schemas/auth.py
//       CreateUserRequest, UserRead
//   - backend/app/db/models.py
//       UserRole
//   - backend/app/api/routes/auth.py
//
// Type-design decisions:
//   - UserRole is reused from `@/auth` (the canonical declaration lives
//     in src/auth/types.ts). Re-defining it here would split the source
//     of truth and risk drift the day a new role lands on the backend.
//   - UserRead mirrors `backend/app/schemas/auth.py::UserRead` exactly
//     and is intentionally identical in shape to `AuthUser` from @/auth.
//     They are kept as distinct names because semantically AuthUser is
//     "the session's current user" and UserRead is "any user record
//     returned by a users endpoint" — today the only such endpoint is
//     POST /auth/users (which returns the freshly-created row).
//   - CreateUserRequest mirrors the backend Pydantic schema. Optional
//     fields are typed `string | null` (not `?`) when the backend wire
//     accepts an explicit null, which CreateUserRequest does for both
//     store_id and phone. Sending `null` is a meaningful signal to the
//     backend (admin caller signalling "no store" for an admin target,
//     or owner/manager signalling "use my store"). Callers may also
//     omit the field entirely; the union allows both call shapes.
//   - No frontend authorisation logic, no role matrix, no canCreate
//     helpers. The backend matrix in app/core/permissions.py is the
//     single source of truth; the frontend simply forwards the role
//     and surfaces the resulting 403 when the matrix rejects it.
//   - No timestamps, no last_login, no password_hash, no permissions
//     field — the backend response_model `UserRead` carries none of
//     those, and inventing them here would set up silent drift.

import type { UserRole } from "@/auth";

// Re-exported so feature consumers (form, hook layer in F2.9.2+) can
// import the role enum from a single place — `@/features/users` —
// without reaching across into the auth module's barrel.
export type { UserRole };

/**
 * Body accepted by POST /auth/users.
 *
 * Mirrors backend `app.schemas.auth.CreateUserRequest`. Validation
 * reminders (the backend is authoritative — these notes exist so the
 * UI can mirror the constraints as a UX guard, not as authoritative
 * checks):
 *
 *   - full_name: 1..150 chars (backend Field(min_length=1, max_length=150))
 *   - email:     EmailStr (lowercased server-side before persistence)
 *   - password:  8..128 chars (backend Field(min_length=8, max_length=128))
 *   - role:      one of UserRole. The backend matrix rejects creating
 *                "admin" for every caller in MVP — the wire still
 *                accepts the value and the server returns 403, which is
 *                the contract the frontend should surface unchanged.
 *   - store_id:  optional. Semantics depend on caller and target role
 *                and are resolved server-side by resolve_target_store_id:
 *                  • target=admin       → must be null/omitted (else 400)
 *                  • caller=admin       → must be a UUID for non-admin
 *                                         targets (else 400); 404 if the
 *                                         store does not exist
 *                  • caller=owner/mgr   → ignored if matches caller's
 *                                         store; 403 if it points to
 *                                         another store
 *   - phone:     optional, max 30 chars.
 */
export interface CreateUserRequest {
  full_name: string;
  email: string;
  password: string;
  role: UserRole;
  store_id?: string | null;
  phone?: string | null;
}

/**
 * Response shape for POST /auth/users (201) and GET /auth/me (200).
 *
 * Mirrors backend `app.schemas.auth.UserRead`. The backend's response
 * key set is locked by tests to exactly these six fields — see
 * `tests/test_register_security.py::TestResponseShape` and
 * `tests/test_login_me.py::TestMeSuccess`. Adding fields here without
 * a backend change would create a silent contract divergence.
 *
 * Identical in shape to `AuthUser` from `@/auth`. The two names are
 * preserved as separate identifiers so call sites read clearly:
 *   - AuthUser  → "the user attached to my session"
 *   - UserRead  → "a user record returned by a users endpoint"
 *
 * NOTE on `phone`: the backend column is nullable and the PATCH
 * endpoint accepts it, but `UserRead` does NOT carry it on the wire
 * today (verified F2.15.1 schemas + F2.15.3 API tests assert exactly
 * these six keys). Reading `phone` requires a future contract change
 * on the backend side — do not invent it here.
 */
export interface UserRead {
  id: string;
  full_name: string;
  email: string;
  role: UserRole;
  store_id: string | null;
  is_active: boolean;
}

// --------------------------------------------------------------------- //
// F2.15.4: list + mutation contracts for users management.
//
// Each interface mirrors a Pydantic schema in
// `backend/app/schemas/users.py`. snake_case is preserved end-to-end so
// payloads pass straight through `apiRequest` without remapping. UI
// concerns (camelCase, label strings, validation copy) live in
// components, never here.
// --------------------------------------------------------------------- //

/**
 * Filter set for `GET /auth/users` (and the matching cache key).
 * Every field is optional. Backend service applies tenancy so a
 * non-admin caller cannot use `store_id` to escape their store.
 *
 * Field bounds (backend authoritative):
 *   - `limit`: 1..100, default 25 server-side.
 *   - `offset`: >= 0, default 0 server-side.
 *   - `q`: free-text ILIKE on full_name / email / phone.
 */
export interface UserListFilters {
  limit?: number;
  offset?: number;
  role?: UserRole;
  is_active?: boolean;
  store_id?: string;
  q?: string;
}

/**
 * Paginated envelope returned by `GET /auth/users`.
 * Mirrors backend `UserListResponse` exactly.
 */
export interface UserListResponse {
  items: UserRead[];
  total: number;
  limit: number;
  offset: number;
}

/**
 * Body accepted by `PATCH /auth/users/{user_id}`.
 *
 * Mirrors backend `UserUpdateRequest` (with `extra="forbid"`). Only
 * `full_name` and `phone` are mutable through this endpoint; sending
 * any other key surfaces as 422 from the backend, which is the
 * intentional escalation guard. `phone` accepts an explicit `null`
 * to clear the value; the backend also coerces empty strings to null.
 */
export interface UserUpdateRequest {
  full_name?: string;
  phone?: string | null;
}

/**
 * Body accepted by `PATCH /auth/users/{user_id}/role`.
 * Mirrors backend `UserRoleChangeRequest` exactly.
 */
export interface UserRoleChangeRequest {
  role: UserRole;
}

/**
 * Body accepted by `PATCH /auth/users/{user_id}/store`.
 *
 * `null` is meaningful: clearing the store is required when the
 * target is admin. Non-admin targets must receive a UUID; the
 * backend returns 422 on the cross-field invariant violation.
 */
export interface UserStoreAssignmentRequest {
  store_id: string | null;
}

/**
 * Body accepted by `POST /auth/users/{user_id}/password`.
 *
 * Backend bounds: 8..128 chars. The wire NEVER carries a hash —
 * `password_hash` is intentionally absent here so a future careless
 * caller cannot send one even by accident. The response is a plain
 * `UserRead`, also without the hash.
 */
export interface AdminSetPasswordRequest {
  new_password: string;
}
