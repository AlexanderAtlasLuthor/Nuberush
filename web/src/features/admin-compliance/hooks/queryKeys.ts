// F2.20.4: query-key factory for the admin-compliance module.
//
// Single source of truth for every cache key the admin-compliance
// feature mounts. Two endpoint families share the `admin-compliance`
// root so a future "nuke all compliance caches" invalidation can
// prefix-match both with one call.
//
// Shape contract:
//
//   adminComplianceQueryKeys.all
//                              ─── ["admin-compliance"]
//
//   adminComplianceQueryKeys.summary()
//                              ─── ["admin-compliance", "summary"]
//
//   adminComplianceQueryKeys.products()
//                              ─── ["admin-compliance", "products"]
//
//   adminComplianceQueryKeys.productsList(filters)
//                              ─── ["admin-compliance", "products", "list", filters ?? {}]
//
// Why summary() and products() share the root but live in their own
// namespaces: a compliance-state change (PATCH /products/{id}/compliance
// in F2.20.6) needs to invalidate BOTH the summary KPIs AND every
// queue list. `adminComplianceQueryKeys.all` is the shared prefix
// that covers both.
//
// Filter objects are stored verbatim on the productsList key.
// TanStack Query's `hashKey` JSON-stringifies with sorted keys and
// drops `undefined` values, so two callers passing logically-
// equivalent filters share one cache slot regardless of property
// order.
//
// Rules baked in (F2.20.4):
//   - Stable shape across renders.
//   - Filters are part of the productsList key only.
//   - Summary and productsList keys are DISTINCT — no accidental
//     prefix collision.
//   - NO store context in any key (Product is global per F2.20.0 §4).
//   - NO user / role context in any key.
//   - NO route path in any key.

import type { AdminComplianceProductsFilters } from "../types";

export const adminComplianceQueryKeys = {
  /** Root namespace. Useful as the prefix invalidation target for any
   * mutation that affects compliance state (e.g. PATCH compliance in
   * F2.20.6) — invalidating this prefix nukes summary + every
   * productsList slot in one call. */
  all: ["admin-compliance"] as const,

  // ----- GET /admin/compliance ------------------------------------- //

  /** Concrete key for the parameter-free summary endpoint. */
  summary: () => [...adminComplianceQueryKeys.all, "summary"] as const,

  // ----- GET /admin/compliance/products ---------------------------- //

  /** Prefix for every products-queue query (any filter set). Useful
   * as a coarser invalidation target than the root when only the
   * queue needs refreshing. */
  products: () =>
    [...adminComplianceQueryKeys.all, "products"] as const,

  /** Concrete key for one products-queue query. Trailing `filters`
   * object is always present (defaults to `{}`) so the tuple shape
   * is stable across callers. */
  productsList: (filters?: AdminComplianceProductsFilters) =>
    [
      ...adminComplianceQueryKeys.products(),
      "list",
      filters ?? {},
    ] as const,
};
