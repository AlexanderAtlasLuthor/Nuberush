// F2.18.2A: admin stores API layer.
//
// Pure async functions over the backend admin stores endpoints. Every
// call goes through `apiRequest` from `@/api` so error normalisation,
// Bearer attach and FastAPI detail parsing stay centralised.
//
// Hard rules baked in (mirroring features/users, features/store,
// features/inventory, features/orders):
//   - No fetch() directly.
//   - No React imports.
//   - No TanStack Query imports — those live in ./hooks.
//   - No try/catch: ApiError propagates to the caller untouched.
//   - No business logic: no client-side permission checks, no
//     snake_case → camelCase mapping, no fake settings.
//
// URL alignment (verified against backend/app/api/routes/stores.py and
// `app.include_router(stores_router)` in app/main.py with prefix
// `/stores`):
//
//   GET    /stores                          (admin-only; list)
//   POST   /stores                          (admin-only; create)
//   GET    /stores/{store_id}               (any store member or admin)
//   PATCH  /stores/{store_id}               (owner / admin only)
//   POST   /stores/{store_id}/deactivate    (admin-only; not idempotent)
//   POST   /stores/{store_id}/reactivate    (admin-only; not idempotent)
//
// `getStore` and `updateStore` are re-exported from `@/features/store/api`
// because the singular own-store feature already owns them and the wire
// contract is identical regardless of caller role (the backend route
// gates admin vs. owner via `require_owner_or_admin`). Re-exporting
// avoids two parallel implementations of the same endpoint client.
//
// Endpoints intentionally NOT implemented here:
//   - DELETE /stores/{store_id}    (no hard-delete endpoint; lifecycle
//                                   goes through deactivate/reactivate)
//   - GET    /admin/stores         (the backend never created this
//                                   namespace by design — see F2.17
//                                   contract §3 and F2.18.0 §3.3)
// Inventing either would 404 at runtime.

import { apiRequest } from "@/api";
import { getStore, updateStore } from "@/features/store/api";
import type {
  StoreCreateRequest,
  StoreListFilters,
  StoreListResponse,
  StoreProfile,
} from "./types";

// Re-exported so admin-feature consumers can import every store API
// call from a single place — `@/features/stores/api`.
export { getStore, updateStore };

// --------------------------------------------------------------------- //
// listStores (admin-only paginated list)
// --------------------------------------------------------------------- //

/**
 * GET /stores
 *
 * Returns the paginated `StoreListResponse`. Optional filters are
 * serialised as query params; `is_active` is sent for BOTH `true` and
 * `false` (an explicit `false` is meaningful — "show deactivated
 * stores only"). Empty / undefined fields are dropped so the cache key
 * stays stable across logically equivalent filter sets.
 *
 * Throws ApiError on:
 *   - 401 (missing/invalid token)
 *   - 403 (non-admin caller — `require_admin` rejects everyone else)
 */
export function listStores(
  filters: StoreListFilters = {},
  signal?: AbortSignal,
): Promise<StoreListResponse> {
  const query = new URLSearchParams();
  if (filters.limit !== undefined) {
    query.set("limit", String(filters.limit));
  }
  if (filters.offset !== undefined) {
    query.set("offset", String(filters.offset));
  }
  if (filters.is_active !== undefined) {
    query.set("is_active", String(filters.is_active));
  }
  if (filters.q !== undefined && filters.q.length > 0) {
    query.set("q", filters.q);
  }
  const qs = query.toString();
  const path = `/stores${qs.length > 0 ? `?${qs}` : ""}`;
  return apiRequest<StoreListResponse>(path, { signal });
}

// --------------------------------------------------------------------- //
// createStore (admin-only)
// --------------------------------------------------------------------- //

export interface CreateStoreParams {
  /**
   * Validated payload. Frontend validation is a UX guard only; the
   * backend re-validates and is authoritative on name/code/timezone
   * non-empty and code uniqueness.
   */
  body: StoreCreateRequest;
}

/**
 * POST /stores
 *
 * Admin-only. Returns the persisted `StoreProfile` (201 Created) with
 * `is_active=true` and a server-generated UUID. Throws ApiError on:
 *   - 401 (missing/invalid token)
 *   - 403 (non-admin caller)
 *   - 422 (validation error — empty name/code, duplicate code,
 *          extra field via `extra="forbid"`)
 */
export function createStore(
  params: CreateStoreParams,
  signal?: AbortSignal,
): Promise<StoreProfile> {
  return apiRequest<StoreProfile>("/stores", {
    method: "POST",
    body: params.body,
    signal,
  });
}

// --------------------------------------------------------------------- //
// Lifecycle: deactivateStore / reactivateStore (admin-only; NOT idempotent)
// --------------------------------------------------------------------- //

export interface DeactivateStoreParams {
  /** Store UUID. */
  storeId: string;
}

/**
 * POST /stores/{store_id}/deactivate
 *
 * Admin-only. Returns the updated `StoreProfile` (`is_active === false`).
 * The backend is **not idempotent** — deactivating an already-inactive
 * store surfaces as 422 (intentional conflict signal so operators
 * notice no-op state changes).
 *
 * Throws ApiError on:
 *   - 401 (missing/invalid token)
 *   - 403 (non-admin caller)
 *   - 404 (admin path: store_id does not exist)
 *   - 422 (already inactive)
 */
export function deactivateStore(
  params: DeactivateStoreParams,
  signal?: AbortSignal,
): Promise<StoreProfile> {
  const path = `/stores/${encodeURIComponent(params.storeId)}/deactivate`;
  return apiRequest<StoreProfile>(path, { method: "POST", signal });
}

export interface ReactivateStoreParams {
  /** Store UUID. */
  storeId: string;
}

/**
 * POST /stores/{store_id}/reactivate
 *
 * Admin-only. Returns the updated `StoreProfile` (`is_active === true`).
 * Like deactivate, **not idempotent** — reactivating an already-active
 * store surfaces as 422.
 *
 * Throws ApiError on:
 *   - 401 (missing/invalid token)
 *   - 403 (non-admin caller)
 *   - 404 (admin path: store_id does not exist)
 *   - 422 (already active)
 */
export function reactivateStore(
  params: ReactivateStoreParams,
  signal?: AbortSignal,
): Promise<StoreProfile> {
  const path = `/stores/${encodeURIComponent(params.storeId)}/reactivate`;
  return apiRequest<StoreProfile>(path, { method: "POST", signal });
}
