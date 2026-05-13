// F2.20.3: query-key factory for the admin-products module.
//
// Single source of truth for every cache key the admin-products
// feature mounts. Centralising keys means:
//
//   - Read hooks build keys via the same helpers, never by hand.
//   - Future invalidations from compliance UI (F2.20.6) target the
//     same key shape that this list mounted under — no drift risk.
//   - Prefix invalidation is well-defined:
//     `adminProductsQueryKeys.lists()` prefix-matches every concrete
//     `adminProductsQueryKeys.list(filters)` regardless of filters.
//
// Shape contract:
//
//   adminProductsQueryKeys.all
//                                       ─── ["admin-products"]
//   adminProductsQueryKeys.lists()
//                                       ─── ["admin-products", "list"]
//   adminProductsQueryKeys.list(filters)
//                                       ─── ["admin-products", "list", filters ?? {}]
//
// Filter object is stored verbatim. TanStack Query's `hashKey`
// JSON-stringifies with sorted keys and drops `undefined` values, so
// two callers passing logically-equivalent filters share one cache
// slot regardless of property order.
//
// Rules baked in (F2.20.3):
//   - Stable shape across renders.
//   - Filters are part of the key.
//   - NO store context in the key (Product is global per F2.20.0 §4).
//   - NO user / role context in the key.
//   - NO route path in the key (a key is a cache identifier, not a
//     navigation token).

import type { AdminProductsFilters } from "../types";

export const adminProductsQueryKeys = {
  /** Root namespace. Useful for nuking the entire admin-products cache. */
  all: ["admin-products"] as const,

  /** Prefix for every list query (any filter set). */
  lists: () => [...adminProductsQueryKeys.all, "list"] as const,

  /**
   * Concrete key for one list query. Trailing `filters` object is
   * always present (defaults to `{}`) so the tuple shape is stable
   * across callers; TanStack hashes objects deterministically.
   */
  list: (filters?: AdminProductsFilters) =>
    [...adminProductsQueryKeys.lists(), filters ?? {}] as const,
};
