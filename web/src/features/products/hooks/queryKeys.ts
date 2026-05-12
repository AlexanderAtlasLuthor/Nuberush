// F2.8.2: query-key factory for the products module.
//
// Single source of truth for every key shape this feature mounts in
// the TanStack Query cache. Centralising keys means:
//
//   - Read hooks build keys via the same helpers, never by hand.
//   - Mutation hooks invalidate via the same helpers, so a key shape
//     change can never desync read vs. invalidate.
//   - Prefix invalidation is well-defined: `productsKeys.lists()`
//     prefix-matches every concrete `productsKeys.list(...)` regardless
//     of filters, and `productsKeys.variants(productId)` prefix-matches
//     any future `variantsList(productId, params)` calls.
//
// Shape contract (must stay aligned with the F2.8.2 brief):
//
//   productsKeys.all ──────────────────────── ["products"]
//   productsKeys.lists() ──────────────────── ["products", "list"]
//   productsKeys.list(filters) ────────────── ["products", "list", filters]
//   productsKeys.details() ────────────────── ["products", "detail"]
//   productsKeys.detail(productId) ────────── ["products", "detail", productId]
//   productsKeys.variants(productId) ──────── ["products", "variants", productId]
//   productsKeys.variantsList(productId, params)
//                                ─────────── ["products", "variants", productId, params]
//   productsKeys.sellable(productId) ──────── ["products", "sellable", productId]
//   productsKeys.complianceAudit(productId) ─ ["products", "complianceAudit", productId]
//
// Filter / param objects are stored verbatim. TanStack Query's `hashKey`
// JSON-stringifies with sorted keys and drops `undefined` values, so two
// callers passing logically-equivalent filters share one cache slot
// regardless of property order or whether they spread `undefined` keys.
// We do NOT pre-normalise here — that would just duplicate framework
// behaviour and obscure what the cache key actually contains.

import type { ProductComplianceStatus } from "../types";

/**
 * Filter shape consumed by `useProductsQuery` and stored on the
 * `productsKeys.list(...)` cache key. Mirrors `ProductListFilters` from
 * the api layer 1:1 — re-declaring it here would create a drift risk;
 * importing it would create a hooks → api type cycle that's harmless
 * but noisy. The local re-definition is intentional and documented.
 */
export interface ProductsListQueryFilters {
  only_active?: boolean;
  only_sellable?: boolean;
  compliance_status?: ProductComplianceStatus;
  category?: string;
  limit?: number;
  offset?: number;
}

/**
 * Optional filter shape consumed by `useProductVariantsQuery` and
 * stored as the trailing element of `productsKeys.variantsList(...)`.
 */
export interface ProductVariantsQueryParams {
  only_active?: boolean;
}

export const productsKeys = {
  /** Root namespace. Useful for nuking the entire products cache. */
  all: ["products"] as const,

  // ----- list -------------------------------------------------------- //

  /** Prefix for every list query (any filter set). */
  lists: () => [...productsKeys.all, "list"] as const,

  /** Concrete key for one list query. */
  list: (filters: ProductsListQueryFilters = {}) =>
    [...productsKeys.lists(), filters] as const,

  // ----- detail ------------------------------------------------------ //

  /** Prefix for every single-product detail query. */
  details: () => [...productsKeys.all, "detail"] as const,

  /** Concrete key for one single-product detail query. */
  detail: (productId: string) =>
    [...productsKeys.details(), productId] as const,

  // ----- variants ---------------------------------------------------- //

  /**
   * Prefix for every variants query of a given product. Used as the
   * invalidation target after variant create/update/delete — prefix-
   * matches any concrete `variantsList(productId, params)` call.
   */
  variants: (productId: string) =>
    [...productsKeys.all, "variants", productId] as const,

  /**
   * Concrete key for one variants query. Trailing `params` object is
   * always present (defaults to `{}`) so the tuple shape is stable
   * across callers; TanStack hashes objects deterministically.
   */
  variantsList: (
    productId: string,
    params: ProductVariantsQueryParams = {},
  ) => [...productsKeys.variants(productId), params] as const,

  // ----- sellable ---------------------------------------------------- //

  /** Concrete key for one sellable-check query. */
  sellable: (productId: string) =>
    [...productsKeys.all, "sellable", productId] as const,

  // ----- compliance audit ------------------------------------------- //

  /** Concrete key for one product's compliance-audit query. */
  complianceAudit: (productId: string) =>
    [...productsKeys.all, "complianceAudit", productId] as const,
};
