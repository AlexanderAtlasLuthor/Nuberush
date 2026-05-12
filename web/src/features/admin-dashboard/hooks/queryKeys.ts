// F2.19.3: query-key factory for the admin dashboard module.
//
// One backend surface, one key namespace under the shared root:
//
//   adminDashboardKeys.all       ──────── ["admin-dashboard"]
//   adminDashboardKeys.summary() ──────── ["admin-dashboard", "summary"]
//
// Shape rules:
//   - `all` is the root namespace for prefix-invalidation. A single
//     `invalidateQueries({ queryKey: adminDashboardKeys.all })`
//     flushes the whole admin-dashboard cache.
//   - The endpoint takes no path params and no query params, so the
//     `summary()` key is a stable two-segment tuple. There is no
//     store-id segment, no role/user value, no filters — the
//     dashboard has none of those inputs by contract (F2.19.0 §3.1).
//   - The namespace is intentionally separate from the store-scoped
//     `dashboardKeys` used by `@/features/dashboard` (per-store
//     dashboard). The two surfaces share no cache.
//
// Deliberately NOT exposed:
//
//   adminDashboardKeys.detail(storeId) — admin dashboard has no
//                                          store-scoped variant.
//   adminDashboardKeys.alerts(...)     — operations alerts live in
//                                          a separate namespace
//                                          (`@/features/admin-operations`,
//                                          F2.19.4 — not this phase).

export const adminDashboardKeys = {
  /** Root namespace. Useful for nuking the whole admin-dashboard cache. */
  all: ["admin-dashboard"] as const,

  /**
   * Concrete key for the single dashboard summary the endpoint
   * returns. Two-segment tuple — the endpoint takes no inputs.
   */
  summary: () => [...adminDashboardKeys.all, "summary"] as const,
};
