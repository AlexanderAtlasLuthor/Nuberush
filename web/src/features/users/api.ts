// F2.9.1 + F2.15.4: users API layer.
//
// Pure async functions over the user-management endpoints exposed by
// the backend. Every call goes through `apiRequest` from `@/api` so
// error normalisation, Bearer attach and FastAPI detail parsing stay
// centralised.
//
// Hard rules baked in (mirroring features/products, features/inventory,
// features/orders):
//   - No fetch() directly.
//   - No React imports.
//   - No TanStack Query imports — those live in ./hooks.
//   - No try/catch: ApiError propagates to the caller untouched.
//   - No business logic: no client-side role matrix, no
//     canCreate/canManage helpers, no permission checks. The backend
//     (USER_CREATION_MATRIX, USER_ROLE_UPDATE_MATRIX, the lifecycle
//     and modify matrices in app/core/permissions.py) is the source
//     of truth and surfaces 401 / 403 / 400 / 404 / 409 / 422 for the
//     frontend to render.
//
// URL alignment (verified against backend/app/api/routes/auth.py and
// backend/app/api/routes/users.py; `app.include_router(auth_router)`
// and `app.include_router(users_router)` are both bare so paths land
// at `/auth/...`):
//
//   POST   /auth/users                       (manager-or-above; matrix)
//   GET    /auth/users                       (paginated, scope-aware)
//   GET    /auth/users/{user_id}
//   PATCH  /auth/users/{user_id}             (full_name / phone)
//   POST   /auth/users/{user_id}/deactivate
//   POST   /auth/users/{user_id}/reactivate
//   PATCH  /auth/users/{user_id}/role
//   PATCH  /auth/users/{user_id}/store
//
// Endpoints still intentionally NOT implemented here because the
// backend does not surface them:
//   - DELETE /auth/users/{id}    (no hard-delete endpoint)
//   - GET    /roles              (closed enum, not server-listable)
//   - GET    /permissions        (no endpoint)
//   - GET    /stores             (no enumeration endpoint at this path)
// Inventing any of these would 404 at runtime.

import { apiRequest } from "@/api";
import type {
  CreateUserRequest,
  UserListFilters,
  UserListResponse,
  UserRead,
  UserRoleChangeRequest,
  UserStoreAssignmentRequest,
  UserUpdateRequest,
} from "./types";

// --------------------------------------------------------------------- //
// Create user (manager-or-above; backend matrix decides the rest)
// --------------------------------------------------------------------- //

export interface CreateUserParams {
  /**
   * Validated payload. Frontend validation is a UX guard only; the
   * backend re-validates and is authoritative on roles, store_id,
   * email uniqueness and password strength.
   */
  body: CreateUserRequest;
}

/**
 * POST /auth/users
 *
 * Returns the persisted `UserRead` (201 Created) including the
 * server-generated id and `is_active=true`. Throws ApiError on:
 *   - 401 (missing/invalid token)
 *   - 403 (role gate or USER_CREATION_MATRIX violation, cross-store
 *          attempt, caller has no store_id)
 *   - 400 (admin target with store_id, admin caller missing store_id
 *          for non-admin target)
 *   - 404 (store_id references a non-existent store)
 *   - 409 (duplicate email — case-insensitive)
 *   - 422 (Pydantic validation: bad email, password length, etc.)
 */
export function createUser(
  params: CreateUserParams,
  signal?: AbortSignal,
): Promise<UserRead> {
  return apiRequest<UserRead>("/auth/users", {
    method: "POST",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// F2.15.4 — list, read, mutate
// --------------------------------------------------------------------- //

/**
 * GET /auth/users
 *
 * Returns the paginated `UserListResponse` envelope. Optional filters
 * are passed verbatim as query params; `is_active` is serialised for
 * BOTH `true` and `false` (an explicit `false` filter is meaningful —
 * "show only deactivated users"). Empty / undefined fields are
 * dropped so the cache key stays stable across logically equivalent
 * filter sets.
 *
 * Throws ApiError on:
 *   - 401 (missing/invalid token)
 *   - 403 (staff/driver caller, or non-admin requesting cross-store)
 */
export function listUsers(
  filters: UserListFilters = {},
  signal?: AbortSignal,
): Promise<UserListResponse> {
  const query = new URLSearchParams();
  if (filters.limit !== undefined) {
    query.set("limit", String(filters.limit));
  }
  if (filters.offset !== undefined) {
    query.set("offset", String(filters.offset));
  }
  if (filters.role !== undefined) {
    query.set("role", filters.role);
  }
  if (filters.is_active !== undefined) {
    query.set("is_active", String(filters.is_active));
  }
  if (filters.store_id !== undefined) {
    query.set("store_id", filters.store_id);
  }
  if (filters.q !== undefined && filters.q.length > 0) {
    query.set("q", filters.q);
  }
  const qs = query.toString();
  const path = `/auth/users${qs.length > 0 ? `?${qs}` : ""}`;
  return apiRequest<UserListResponse>(path, { signal });
}

export interface GetUserParams {
  /** User UUID. */
  userId: string;
}

/**
 * GET /auth/users/{user_id}
 *
 * Returns the full `UserRead`. Throws ApiError 404 if missing, 403 if
 * the caller cannot see the user under the backend matrix.
 */
export function getUser(
  params: GetUserParams,
  signal?: AbortSignal,
): Promise<UserRead> {
  const path = `/auth/users/${encodeURIComponent(params.userId)}`;
  return apiRequest<UserRead>(path, { signal });
}

export interface UpdateUserParams {
  /** User UUID. */
  userId: string;
  /** Partial profile update. Backend rejects extra keys with 422. */
  body: UserUpdateRequest;
}

/**
 * PATCH /auth/users/{user_id}
 *
 * Returns the updated `UserRead`. Backend's `extra="forbid"` schema
 * is the source of truth for which fields are mutable.
 */
export function updateUser(
  params: UpdateUserParams,
  signal?: AbortSignal,
): Promise<UserRead> {
  const path = `/auth/users/${encodeURIComponent(params.userId)}`;
  return apiRequest<UserRead>(path, {
    method: "PATCH",
    body: params.body,
    signal,
  });
}

export interface DeactivateUserParams {
  /** User UUID. */
  userId: string;
}

/**
 * POST /auth/users/{user_id}/deactivate
 *
 * Returns the updated `UserRead` (`is_active === false`). Backend
 * raises 422 on self-target or last-active-admin; the frontend
 * surfaces those unchanged.
 */
export function deactivateUser(
  params: DeactivateUserParams,
  signal?: AbortSignal,
): Promise<UserRead> {
  const path = `/auth/users/${encodeURIComponent(params.userId)}/deactivate`;
  return apiRequest<UserRead>(path, { method: "POST", signal });
}

export interface ReactivateUserParams {
  /** User UUID. */
  userId: string;
}

/**
 * POST /auth/users/{user_id}/reactivate
 *
 * Returns the updated `UserRead` (`is_active === true`). Backend
 * raises 422 if a non-admin target has no `store_id` — admins must
 * assign one first via PATCH /auth/users/{id}/store.
 */
export function reactivateUser(
  params: ReactivateUserParams,
  signal?: AbortSignal,
): Promise<UserRead> {
  const path = `/auth/users/${encodeURIComponent(params.userId)}/reactivate`;
  return apiRequest<UserRead>(path, { method: "POST", signal });
}

export interface ChangeUserRoleParams {
  /** User UUID. */
  userId: string;
  /** New role. Backend `USER_ROLE_UPDATE_MATRIX` decides legality. */
  body: UserRoleChangeRequest;
}

/**
 * PATCH /auth/users/{user_id}/role
 *
 * Returns the updated `UserRead`. Promoting to admin clears the
 * `store_id` server-side; demoting from admin requires the target
 * already have a `store_id` (else 422).
 */
export function changeUserRole(
  params: ChangeUserRoleParams,
  signal?: AbortSignal,
): Promise<UserRead> {
  const path = `/auth/users/${encodeURIComponent(params.userId)}/role`;
  return apiRequest<UserRead>(path, {
    method: "PATCH",
    body: params.body,
    signal,
  });
}

export interface AssignUserStoreParams {
  /** User UUID. */
  userId: string;
  /**
   * `store_id: null` is meaningful — required when the target is
   * admin. Non-admin targets must receive a UUID; the backend
   * enforces the cross-field invariant with 422.
   */
  body: UserStoreAssignmentRequest;
}

/**
 * PATCH /auth/users/{user_id}/store
 *
 * Admin-only. Returns the updated `UserRead`. Inactive store target
 * → 400; missing store → 404.
 */
export function assignUserStore(
  params: AssignUserStoreParams,
  signal?: AbortSignal,
): Promise<UserRead> {
  const path = `/auth/users/${encodeURIComponent(params.userId)}/store`;
  return apiRequest<UserRead>(path, {
    method: "PATCH",
    body: params.body,
    signal,
  });
}