// F2.16.4 + F2.18.2B: query-key factory for the audit module.
//
// Three backend surfaces, three key namespaces under the shared root:
//
//   auditKeys.all ────────────────────────────── ["audit"]
//
//   // legacy F2.10
//   auditKeys.storeInventoryLogs(storeId, params)
//                              ──────────────── ["audit", "store-inventory-logs", storeId, params]
//
//   // F2.16 unified store-scoped feed
//   auditKeys.storeFeeds()    ──────────────── ["audit", "store-feed"]
//   auditKeys.storeFeed(storeId, filters)
//                              ──────────────── ["audit", "store-feed", storeId, filters]
//
//   // F2.18.2B admin global feed (consumes F2.17.5 backend)
//   auditKeys.adminFeeds()    ──────────────── ["audit", "admin-feed"]
//   auditKeys.adminFeed(filters)
//                              ──────────────── ["audit", "admin-feed", filters]
//
// Shape rules:
//   - `all` is the root namespace for prefix-invalidation.
//   - `storeFeeds()` / `adminFeeds()` are prefixes for the
//     corresponding unified-feed surfaces, so a single
//     `invalidateQueries({ queryKey: auditKeys.<…>Feeds() })` flushes
//     the whole feed cache for that surface.
//   - The "store-feed" and "admin-feed" segments are distinct so the
//     two surfaces never collide.
//   - The admin feed has no storeId path segment — `store_id` is an
//     OPTIONAL filter and lives inside the filters object.
//
// Deliberately NOT exposed:
//
//   auditKeys.events()             — no GET /audit/events endpoint
//   auditKeys.activity()           — no activity feed endpoint
//   auditKeys.userActivity(userId) — no per-user activity endpoint
//   auditKeys.storeAudit(storeId)  — covered by storeFeed(...)
//   auditKeys.orderAuditLogs(...)  — already keyed under ordersKeys
//   auditKeys.inventoryItemLogs(...) — already keyed under inventoryKeys
//   auditKeys.complianceAudit(...)  — already keyed under productsKeys

import type { AdminAuditFilters, StoreAuditFilters } from "../types";

/**
 * Optional filters for the legacy store inventory logs query.
 * Mirrors what `getStoreInventoryLogs` accepts (excluding
 * `storeId`, which is keyed separately).
 */
export interface StoreInventoryLogsQueryParams {
  /**
   * Maximum rows to return. Backend default is 100. Stored on the
   * cache key verbatim so different page sizes get distinct slots.
   */
  limit?: number;
}

export const auditKeys = {
  /** Root namespace. Useful for nuking the whole audit cache. */
  all: ["audit"] as const,

  // Legacy F2.10 surface.
  storeInventoryLogs: (
    storeId: string,
    params: StoreInventoryLogsQueryParams = {},
  ) =>
    [...auditKeys.all, "store-inventory-logs", storeId, params] as const,

  /**
   * Prefix key for the unified store audit feed, useful for
   * cross-store invalidation:
   *   client.invalidateQueries({ queryKey: auditKeys.storeFeeds() })
   */
  storeFeeds: () => [...auditKeys.all, "store-feed"] as const,

  /**
   * Concrete key for one (store, filters) combination of the
   * unified feed. The filters object is always present (defaults
   * to `{}`) so the tuple shape stays stable; different filter
   * snapshots get distinct cache slots.
   */
  storeFeed: (storeId: string, filters: StoreAuditFilters = {}) =>
    [...auditKeys.storeFeeds(), storeId, filters] as const,

  /**
   * Prefix key for the admin global audit feed (F2.18.2B), useful
   * for invalidation:
   *   client.invalidateQueries({ queryKey: auditKeys.adminFeeds() })
   *
   * Distinct second segment ("admin-feed") so this surface never
   * collides with the store-scoped feed or the legacy inventory
   * logs cache.
   */
  adminFeeds: () => [...auditKeys.all, "admin-feed"] as const,

  /**
   * Concrete key for one filter snapshot of the admin global feed.
   * No storeId segment — the admin feed has no path id; `store_id`
   * is an OPTIONAL filter and lives inside `filters`. Different
   * filter snapshots (including different `store_id` values) get
   * distinct cache slots.
   */
  adminFeed: (filters: AdminAuditFilters = {}) =>
    [...auditKeys.adminFeeds(), filters] as const,
};
