// F2.19.4: barrel for admin-operations hooks.
//
// Feature pages should import from `@/features/admin-operations/hooks`
// rather than reaching into individual files; that keeps the public
// surface in one place and lets internals change without ripple
// edits.
//
// Surface exposes:
//   - Admin operations alerts list (F2.19.4)
//
// Deliberately NOT exposed:
//   - acknowledge / dismiss / resolve / snooze hooks (forbidden by
//     the F2.19.0 contract — alerts have no mutation surface).
//   - Per-alert detail / get-by-id hooks (no such backend endpoint).
//   - Dashboard hooks (live in `@/features/admin-dashboard`).

export { adminOperationsKeys } from "./queryKeys";
export { useAdminOperationsAlertsQuery } from "./useAdminOperationsAlertsQuery";
