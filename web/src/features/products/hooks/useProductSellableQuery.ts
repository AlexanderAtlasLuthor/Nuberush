// F2.8.2: sellable-check hook.
//
// Cache key: ["products", "sellable", productId] — see queryKeys.ts.
//
// IMPORTANT: this hook is intentionally THIN. The backend route returns
// 200 `{ product_id, sellable: true }` only when the product passes
// `assert_product_sellable`; otherwise it returns 422 with the failing
// flags inside the response body. We do NOT translate the 422 into
// `{ sellable: false }` here — doing so would fork the contract and
// move a backend rule into the frontend. Callers inspect `error`
// (an `ApiError` with `details` carrying the failing flags) to render
// the not-sellable case.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getProductSellable } from "../api";
import type { ProductSellableResponse } from "../api";
import { productsKeys } from "./queryKeys";

export function useProductSellableQuery(
  productId: string,
): UseQueryResult<ProductSellableResponse> {
  return useQuery({
    queryKey: productsKeys.sellable(productId),
    queryFn: ({ signal }) => getProductSellable({ productId }, signal),
    enabled: productId.length > 0,
  });
}
