// F2.8.2: variants-for-product list hook.
//
// Cache key: ["products", "variants", productId, params] — see
// queryKeys.ts. The trailing `params` object segments the cache by
// `only_active`, so two callers with different filter values get
// independent results. Variant create/update/delete mutations
// invalidate the prefix `productsKeys.variants(productId)`, which
// prefix-matches every `variantsList(productId, ...)` call.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getProductVariants } from "../api";
import type { ProductVariant } from "../types";
import {
  productsKeys,
  type ProductVariantsQueryParams,
} from "./queryKeys";

export function useProductVariantsQuery(
  productId: string,
  params: ProductVariantsQueryParams = {},
): UseQueryResult<ProductVariant[]> {
  return useQuery({
    queryKey: productsKeys.variantsList(productId, params),
    queryFn: ({ signal }) =>
      getProductVariants({ productId, ...params }, signal),
    enabled: productId.length > 0,
  });
}
