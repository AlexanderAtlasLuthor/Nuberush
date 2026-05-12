// F2.8.2: update-variant mutation.
//
// Variables shape mirrors the api-layer params exactly. The variant
// route is `PATCH /variants/{variant_id}` (NOT nested under products),
// so the hook only needs the `variantId`. The parent `productId` for
// invalidation comes from the response body (`data.product_id`) — the
// backend always returns the full updated variant.
//
// Cache invalidation contract (per F2.8.2 brief §5):
//
//   1. productsKeys.variants(data.product_id)  parent product's variant
//                                              list now has stale row
//                                              data (price / sku / etc).
//   2. productsKeys.detail(data.product_id)    detail page may surface
//                                              variant info.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateProductVariant } from "../api";
import type { UpdateProductVariantParams } from "../api";
import type { ProductVariant } from "../types";
import { productsKeys } from "./queryKeys";

export function useUpdateVariantMutation() {
  const queryClient = useQueryClient();

  return useMutation<
    ProductVariant,
    Error,
    UpdateProductVariantParams
  >({
    mutationFn: (vars) => updateProductVariant(vars),
    onSuccess: (data) => {
      queryClient.invalidateQueries({
        queryKey: productsKeys.variants(data.product_id),
      });
      queryClient.invalidateQueries({
        queryKey: productsKeys.detail(data.product_id),
      });
    },
  });
}
