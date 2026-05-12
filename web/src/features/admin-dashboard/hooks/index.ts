// F2.19.3: barrel for admin-dashboard hooks.
//
// Feature pages should import from `@/features/admin-dashboard/hooks`
// rather than reaching into individual files; that keeps the public
// surface in one place and lets internals change without ripple
// edits.
//
// Surface exposes:
//   - Admin dashboard summary (F2.19.3)
//
// Future hooks belong here only when the corresponding backend
// endpoint exists. Operations alerts are NOT exposed here — they
// live in `@/features/admin-operations` (F2.19.4, separate phase).

export { adminDashboardKeys } from "./queryKeys";
export { useAdminDashboardQuery } from "./useAdminDashboardQuery";
