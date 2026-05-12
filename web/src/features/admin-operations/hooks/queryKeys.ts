// F2.19.4: query-key factory for the admin operations module.
//
// One backend surface, one key namespace under a dedicated root:
//
//   adminOperationsKeys.all       ──────── ["admin-operations"]
//   adminOperationsKeys.alertLists()
//                                  ──────── ["admin-operations", "alerts", "list"]
//   adminOperationsKeys.alertList(filters)
//                                  ──────── ["admin-operations", "alerts", "list", filters]
//
// Shape rules:
//   - `all` is the root namespace for prefix-invalidation. A single
//     `invalidateQueries({ queryKey: adminOperationsKeys.all })`
//     flushes the whole admin-operations cache.
//   - `alertLists()` is the cross-filter prefix so a single
//     `invalidateQueries({ queryKey: adminOperationsKeys.alertLists() })`
//     flushes every alert-list cache slot.
//   - `alertList(filters)` carries the filters object verbatim (or
//     `{}` when omitted) so different filter snapshots get distinct
//     cache slots — same convention used by `auditKeys.adminFeed`.
//   - No role / user value leaks into the key. No store context.
//   - The namespace is intentionally separate from the F2.19.3
//     `adminDashboardKeys` (the two admin surfaces never share
//     cache).
//
// Deliberately NOT exposed:
//
//   adminOperationsKeys.alert(id)         — no per-alert endpoint
//                                            (alerts have no
//                                            persistence and no
//                                            individual fetch path).
//   adminOperationsKeys.dashboard(...)    — dashboard keys live in
//                                            `@/features/admin-dashboard`
//                                            (F2.19.3).
//   adminOperationsKeys.incidents(...)    — incidents are a
//                                            non-goal (F2.19.0 §2).

import type { AdminOperationsAlertsFilters } from "../types";

export const adminOperationsKeys = {
  /** Root namespace. Useful for nuking the whole admin-operations cache. */
  all: ["admin-operations"] as const,

  /**
   * Prefix key for every alert-list cache slot, useful for
   * invalidation:
   *   client.invalidateQueries({ queryKey: adminOperationsKeys.alertLists() })
   */
  alertLists: () =>
    [...adminOperationsKeys.all, "alerts", "list"] as const,

  /**
   * Concrete key for one filter snapshot. The filters object is
   * always present (defaults to `{}`) so the tuple shape stays
   * stable; different filter snapshots get distinct cache slots.
   */
  alertList: (filters: AdminOperationsAlertsFilters = {}) =>
    [...adminOperationsKeys.alertLists(), filters] as const,
};
