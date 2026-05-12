// F2.6.0 subfase 3 + F2.18.2C: query-key factory for the inventory module.
//
// Single source of truth for every key shape this feature mounts in
// the TanStack Query cache. Centralising keys means:
//
//   - List/item hooks build keys via the same helpers, never by hand.
//   - Mutation hooks invalidate via the same helpers, so a key shape
//     change can never desync read vs. invalidate.
//   - Prefix invalidation is well-defined: `inventoryKeys.lists()`
//     prefix-matches every store-scoped `inventoryKeys.list(...)`;
//     `inventoryKeys.adminLists()` prefix-matches every admin list.
//
// Shape contract:
//
//   inventoryKeys.lists() ──────────────── ["inventory", "list"]
//   inventoryKeys.list(storeId, params) ── ["inventory", "list", storeId, params]
//   inventoryKeys.items() ──────────────── ["inventory", "item"]
//   inventoryKeys.item(itemId) ─────────── ["inventory", "item", itemId]
//   inventoryKeys.itemLogs(itemId, params)
//                                ──────── ["inventory", "item", itemId, "logs", params]
//
//   // F2.18.2C admin global feed (consumes F2.18.1A backend)
//   inventoryKeys.adminLists() ──────────── ["inventory", "admin", "list"]
//   inventoryKeys.adminList(filters) ───── ["inventory", "admin", "list", filters]
//
// Isolation:
//   - The store-scoped `list(storeId, params)` tuple is length 4.
//   - The admin `adminList(filters)` tuple is length 4 too but the
//     SECOND segment is `"admin"` (vs. nothing extra in the store
//     case). They share only the `["inventory"]` root, so a
//     `inventoryKeys.lists()` invalidation does NOT touch admin
//     cache, and vice versa.

import type { AdminInventoryFilters } from "../types";

export interface InventoryListQueryParams {
  limit: number;
  offset: number;
  low_stock_only?: boolean;
}

export interface InventoryItemLogsQueryParams {
  limit?: number;
}

export const inventoryKeys = {
  /** Root namespace. Useful for nuking the whole inventory cache. */
  all: ["inventory"] as const,

  /** Prefix for every store-scoped paginated-list query. */
  lists: () => [...inventoryKeys.all, "list"] as const,

  /** Concrete key for a single store-scoped paginated-list query. */
  list: (storeId: string | null, params: InventoryListQueryParams) =>
    [...inventoryKeys.lists(), storeId, params] as const,

  /** Prefix for every single-item query. */
  items: () => [...inventoryKeys.all, "item"] as const,

  /** Concrete key for a single inventory-item query. */
  item: (itemId: string) => [...inventoryKeys.items(), itemId] as const,

  /**
   * Concrete key for an item's audit-log fetch. Keyed under the same
   * item prefix so a future `inventoryKeys.item(id)` invalidation also
   * refreshes its logs. The trailing params object is always present
   * (defaults to `{}`) to keep the tuple shape stable across callers.
   */
  itemLogs: (
    itemId: string,
    params: InventoryItemLogsQueryParams = {},
  ) =>
    [...inventoryKeys.item(itemId), "logs", params] as const,

  /**
   * F2.18.2C: prefix for the admin global inventory feed, useful for
   * invalidation:
   *   client.invalidateQueries({ queryKey: inventoryKeys.adminLists() })
   *
   * Distinct second segment (`"admin"`) so this surface never
   * collides with the store-scoped feed or item caches.
   */
  adminLists: () => [...inventoryKeys.all, "admin", "list"] as const,

  /**
   * Concrete key for one filter snapshot of the admin global feed.
   * No storeId path segment — the admin feed has no path id;
   * `store_id` is an OPTIONAL filter inside `filters`.
   */
  adminList: (filters: AdminInventoryFilters = {}) =>
    [...inventoryKeys.adminLists(), filters] as const,
};
