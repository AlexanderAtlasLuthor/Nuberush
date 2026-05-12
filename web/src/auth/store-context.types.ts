// F2.4: tenancy/store context types.
//
// Backend contract being modelled (do NOT diverge):
//   - User.store_id is a single nullable UUID FK to stores.id
//     (backend/app/db/models.py L125-L143).
//   - Business rule: admin → store_id MUST be NULL (global, no store);
//     owner / manager / staff / driver → store_id MUST NOT be NULL
//     (one user, exactly one bound store).
//   - There is NO membership/junction table — multi-store membership
//     is not supported by the schema.
//   - There is NO /stores listing endpoint registered in
//     backend/app/main.py — the frontend cannot enumerate stores.
//   - /auth/me returns store_id directly inside UserRead, so the
//     frontend can derive the current store from the session alone
//     without an extra round-trip.
//
// Consequence for this module:
//   - We model `currentStoreId` as a single nullable string and derive
//     it from `useAuth().user.store_id`.
//   - We do NOT expose a `setCurrentStoreId` action: there is nothing
//     for a non-admin to switch to (data model rules it out), and admin
//     has no listing endpoint to pick from. When backend grows a
//     /stores route + admin store-selection UX, extend this file.
//   - We do NOT cache the selection in localStorage. There is no
//     selection to cache.

/**
 * Final, derived store-context value the rest of the app reads.
 *
 * Field semantics:
 *   currentStoreId   — user.store_id verbatim, or null when the user
 *                      has no bound store (admin) or is unauthenticated.
 *   hasStoreContext  — `currentStoreId !== null`. Convenience flag.
 *   isStoreRequired  — true when the user's role is non-admin AND a
 *                      user is present. Admin and unauthenticated do
 *                      NOT require a store.
 *   storeError       — populated only when isStoreRequired is true but
 *                      currentStoreId is null (data anomaly: a non-
 *                      admin user without a store_id should not exist
 *                      per backend invariants). Used by StoreGate.
 */
export interface StoreContextState {
  currentStoreId: string | null;
  hasStoreContext: boolean;
  isStoreRequired: boolean;
  storeError: string | null;
}

/**
 * Public name for the "currently scoped store" concept. Today it is
 * just an ID (the backend exposes nothing else without a /stores
 * endpoint), but the type is named so feature code can later switch
 * to a richer object (`{ id, name, code, timezone }`) without a wide
 * rename.
 */
export type CurrentStore = string;
