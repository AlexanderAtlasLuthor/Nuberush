// F2.8.2: paginated/filterable products list hook.
//
// Products are GLOBAL on the backend (not store-scoped), so this hook
// does NOT read `useStoreContext()` — every authenticated user sees the
// same catalogue. The filters object is passed through to the api
// layer untouched and is also the trailing element of the cache key.
//
// Cache key: ["products", "list", filters] — see queryKeys.ts.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { listProducts } from "../api";
import type { Product } from "../types";
import {
  productsKeys,
  type ProductsListQueryFilters,
} from "./queryKeys";

export function useProductsQuery(
  filters: ProductsListQueryFilters = {},
): UseQueryResult<Product[]> {
  return useQuery({
    queryKey: productsKeys.list(filters),
    queryFn: ({ signal }) => listProducts(filters, signal),
  });
}
