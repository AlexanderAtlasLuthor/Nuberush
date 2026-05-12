// F2.8.2: single-product detail hook.
//
// Cache key: ["products", "detail", productId] — see queryKeys.ts.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getProduct } from "../api";
import type { Product } from "../types";
import { productsKeys } from "./queryKeys";

export function useProductQuery(
  productId: string,
): UseQueryResult<Product> {
  return useQuery({
    queryKey: productsKeys.detail(productId),
    queryFn: ({ signal }) => getProduct({ productId }, signal),
    // Defensive guard for empty-string. Caller-typed as string, but a
    // page that derives the id from a route param can briefly land
    // here with "" before the param resolves.
    enabled: productId.length > 0,
  });
}
