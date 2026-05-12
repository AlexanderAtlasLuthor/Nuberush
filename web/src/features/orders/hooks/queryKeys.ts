// F2.7.0 subfase 3 + F2.18.2C: query-key factory for the orders module.
//
// Single source of truth for every key shape orders mounts in the
// TanStack Query cache. Centralising keys means:
//
//   - List/item/audit-log hooks build keys via the same helpers.
//   - Mutation hooks invalidate via the same helpers — a key-shape
//     change can never desync read vs. invalidate.
//   - Prefix invalidation is well-defined: `ordersKeys.lists()`
//     prefix-matches every store-scoped `ordersKeys.list(...)`;
//     `ordersKeys.adminLists()` prefix-matches every admin list.
//
// Shape contract:
//
//   ordersKeys.lists() ────────────────── ["orders", "list"]
//   ordersKeys.list(storeId, params) ──── ["orders", "list", storeId, params]
//   ordersKeys.items() ────────────────── ["orders", "item"]
//   ordersKeys.item(orderId) ──────────── ["orders", "item", orderId]
//   ordersKeys.auditLogs(orderId) ─────── ["orders", "auditLogs", orderId]
//
//   // F2.18.2C admin global feed (consumes F2.18.1B backend)
//   ordersKeys.adminLists() ───────────── ["orders", "admin", "list"]
//   ordersKeys.adminList(filters) ─────── ["orders", "admin", "list", filters]
//
// Isolation:
//   - Store-scoped keys live under `["orders", "list", ...]`.
//   - Admin keys live under `["orders", "admin", "list", ...]`.
//   - The two paths share only the `["orders"]` root, so
//     `invalidateQueries({ queryKey: ordersKeys.lists() })` does NOT
//     touch the admin cache, and vice versa.

import type { AdminOrdersFilters, OrderStatus } from "../types";

export interface OrdersListQueryParams {
  /** Page size. Backend bounds: 1 <= limit <= 500. */
  limit: number;
  /** Zero-based offset. Backend bound: offset >= 0. */
  offset: number;
  /** Optional status filter. */
  status?: OrderStatus;
  /** Optional ISO 8601 datetime. Filters by `created_at >= ...`. */
  created_from?: string;
  /** Optional ISO 8601 datetime. Filters by `created_at <= ...`. */
  created_to?: string;
}

export const ordersKeys = {
  /** Root namespace. Useful for nuking the whole orders cache. */
  all: ["orders"] as const,

  /** Prefix for every store-scoped paginated/filtered list query. */
  lists: () => [...ordersKeys.all, "list"] as const,

  /** Concrete key for one store-scoped list query. */
  list: (storeId: string | null, params: OrdersListQueryParams) =>
    [...ordersKeys.lists(), storeId, params] as const,

  /** Prefix for every single-order query. */
  items: () => [...ordersKeys.all, "item"] as const,

  /** Concrete key for one single-order query. */
  item: (orderId: string) => [...ordersKeys.items(), orderId] as const,

  /** Concrete key for one order's audit-log query. */
  auditLogs: (orderId: string) =>
    [...ordersKeys.all, "auditLogs", orderId] as const,

  /**
   * F2.18.2C: prefix for the admin global orders feed, useful for
   * invalidation:
   *   client.invalidateQueries({ queryKey: ordersKeys.adminLists() })
   *
   * Distinct second segment (`"admin"`) so this surface never
   * collides with the store-scoped list, item, or audit-log caches.
   */
  adminLists: () => [...ordersKeys.all, "admin", "list"] as const,

  /**
   * Concrete key for one filter snapshot of the admin global feed.
   * No storeId path segment — the admin feed has no path id;
   * `store_id` is an OPTIONAL filter inside `filters`.
   */
  adminList: (filters: AdminOrdersFilters = {}) =>
    [...ordersKeys.adminLists(), filters] as const,
};
