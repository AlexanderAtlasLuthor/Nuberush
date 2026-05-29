// F2.22.5.E: authenticated-shell mount point for the realtime hooks.
//
// Single zero-render component that calls the two F2.22.5.D
// subscription hooks. Mounted exactly once per authenticated session
// from `AppShell` — the shared visual wrapper that `AdminLayout` and
// `StoreLayout` both compose, and that `PublicLayout` / `AuthScreen`
// deliberately do NOT. Mounting here gives us:
//
//   - Active only after the user is authenticated (the parents of
//     `AppShell` — `AdminShell` / `StoreShell` — live under
//     `ProtectedRoute` per `web/src/app/router.tsx`).
//   - Never active on public marketing or auth pages (they render
//     `PublicLayout` / `AuthScreen`, neither of which uses `AppShell`).
//   - One subscription per table per session — both `AdminShell` and
//     `StoreShell` mount the same `AppShell`, but a user can render
//     only one shell at a time, so the bridge mounts at most once.
//
// Hard rules (docs/f2.22-contract-lock.md §§9, 9.1):
//
//   - Renders `null`. No JSX, no DOM, no payload reading.
//   - Calls only the two F2.22.5.D hooks, which themselves are
//     payload-opaque (invalidate TanStack Query keys on debounced
//     events; no `setQueryData`, no business-table reads).
//   - Owns no state, no props, no effects beyond the hook calls.

import { useInventoryRealtimeSubscription } from "./useInventoryRealtimeSubscription";
import { useOrdersRealtimeSubscription } from "./useOrdersRealtimeSubscription";

export function RealtimeInvalidationBridge(): null {
  useOrdersRealtimeSubscription();
  useInventoryRealtimeSubscription();
  return null;
}
