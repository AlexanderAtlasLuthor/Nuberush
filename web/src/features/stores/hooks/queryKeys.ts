// F2.18.2A: query-key factory for the admin stores module.
//
// Single source of truth for every key shape this feature mounts in
// the TanStack Query cache. Read hooks build keys via these helpers,
// never by hand. Mutation hooks invalidate via the same helpers, so a
// key shape change can never desync read vs. invalidate.
//
// Shape contract (matches features/users and features/products):
//
//   adminStoresKeys.all ───────────── ["stores"]
//   adminStoresKeys.lists() ───────── ["stores", "list"]
//   adminStoresKeys.list(filters) ─── ["stores", "list", filters]
//   adminStoresKeys.details() ─────── ["stores", "detail"]
//   adminStoresKeys.detail(id) ────── ["stores", "detail", storeId]
//
// Filter objects are stored verbatim; TanStack Query's `hashKey`
// JSON-stringifies with sorted keys and drops `undefined`, so two
// callers passing logically-equivalent filters share one cache slot
// regardless of property order.
//
// Namespace note: the singular own-store feature uses `storeKeys`
// under the root `["store"]`. This admin module uses
// `adminStoresKeys` under `["stores"]`. The two cache namespaces are
// intentionally disjoint — an admin operation invalidates the admin
// cache; own-store settings refetches independently when its own
// store-id-bound query refetches.

import type { StoreListFilters } from "../types";

export const adminStoresKeys = {
  /** Root namespace. Useful for nuking the entire admin stores cache. */
  all: ["stores"] as const,

  // ----- list -------------------------------------------------------- //

  /** Prefix for every list query (any filter set). */
  lists: () => [...adminStoresKeys.all, "list"] as const,

  /** Concrete key for one list query. */
  list: (filters: StoreListFilters = {}) =>
    [...adminStoresKeys.lists(), filters] as const,

  // ----- detail ------------------------------------------------------ //

  /** Prefix for every single-store detail query. */
  details: () => [...adminStoresKeys.all, "detail"] as const,

  /** Concrete key for one single-store detail query. */
  detail: (storeId: string) =>
    [...adminStoresKeys.details(), storeId] as const,
};
