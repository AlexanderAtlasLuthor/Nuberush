// F2.14.4: store-profile API layer.
//
// Pure async functions over the backend stores endpoints. Every call
// goes through `apiRequest` from `@/api` so error normalisation, Bearer
// attach and FastAPI detail parsing stay centralised.
//
// Hard rules baked in (mirroring features/products, features/users,
// features/inventory, features/orders):
//   - No fetch() directly.
//   - No React imports.
//   - No TanStack Query imports — that's the hooks layer.
//   - No try/catch: ApiError propagates to the caller untouched.
//   - No business logic: no client-side permission checks, no
//     snake_case → camelCase mapping, no fake settings.
//
// URL alignment (verified against backend/app/api/routes/stores.py and
// `app.include_router(stores_router)` in app/main.py with prefix
// `/stores`):
//
//   GET    /stores/{store_id}   (any store member or admin)
//   PATCH  /stores/{store_id}   (owner / admin only; require_owner_or_admin)
//
// Endpoints intentionally NOT implemented here because they do not
// exist on the backend today (verified F2.14.0 / F2.14.3):
//   - GET    /stores             (no listing endpoint)
//   - POST   /stores             (no create endpoint)
//   - DELETE /stores/{store_id}  (no delete endpoint)
//   - deactivate / reactivate    (no endpoint)
// Inventing any of these would 404 at runtime; F2.14 is store-profile
// only.

import { apiRequest } from "@/api";
import type { StoreProfile, StoreUpdateRequest } from "./types";

/**
 * GET /stores/{storeId}
 *
 * Returns the full `StoreProfile`. Throws ApiError on:
 *   - 401 (missing/invalid token)
 *   - 403 (non-admin trying a store other than their own; collapsed
 *          with "no such store" so existence isn't probeable)
 *   - 404 (admin path: store_id does not exist)
 *   - 400 (store exists but is inactive)
 */
export function getStore(
  storeId: string,
  signal?: AbortSignal,
): Promise<StoreProfile> {
  const path = `/stores/${encodeURIComponent(storeId)}`;
  return apiRequest<StoreProfile>(path, { signal });
}

/**
 * PATCH /stores/{storeId}
 *
 * Owner/admin-only. Returns the updated `StoreProfile`. Throws ApiError
 * on:
 *   - 401 (missing/invalid token)
 *   - 403 (manager / staff / driver: role gate; or non-admin cross-store
 *          via tenancy gate)
 *   - 404 (admin path: store_id does not exist)
 *   - 400 (store inactive)
 *   - 422 (invalid payload, including any extra field — `StoreUpdate`
 *          uses `extra="forbid"` server-side)
 *
 * Sending an empty body is a server-side no-op (returns the unchanged
 * profile).
 */
export function updateStore(
  storeId: string,
  payload: StoreUpdateRequest,
  signal?: AbortSignal,
): Promise<StoreProfile> {
  const path = `/stores/${encodeURIComponent(storeId)}`;
  return apiRequest<StoreProfile>(path, {
    method: "PATCH",
    body: payload,
    signal,
  });
}
