// F2.8.2: create-variant mutation.
//
// SAFETY (per F2.8.2 brief §6): callers never see `body.product_id`. The
// hook accepts `productId` once and injects it into the body before
// calling the api layer, so the body↔path desync the backend rejects
// (400) is structurally impossible at the hook surface.
//
// Variables shape:
//
//   { productId: string,
//     body: Omit<VariantCreateRequest, "product_id"> }
//
// Cache invalidation contract (per F2.8.2 brief §5):
//
//   1. productsKeys.variants(variables.productId)  the parent product's
//                                                  variant list now has
//                                                  one more row.
//   2. productsKeys.detail(variables.productId)    detail page may
//                                                  surface variant
//                                                  counts / first-row
//                                                  data.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createProductVariant } from "../api";
import type { ProductVariant, VariantCreateRequest } from "../types";
import { productsKeys } from "./queryKeys";

export interface CreateVariantMutationVariables {
  /** Product UUID. Goes into the URL AND is injected into the body. */
  productId: string;
  /**
   * Variant payload WITHOUT `product_id` — the hook injects it from
   * `productId` so the path and body cannot desync.
   */
  body: Omit<VariantCreateRequest, "product_id">;
}

export function useCreateVariantMutation() {
  const queryClient = useQueryClient();

  return useMutation<
    ProductVariant,
    Error,
    CreateVariantMutationVariables
  >({
    mutationFn: (vars) =>
      createProductVariant({
        productId: vars.productId,
        body: { ...vars.body, product_id: vars.productId },
      }),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: productsKeys.variants(variables.productId),
      });
      queryClient.invalidateQueries({
        queryKey: productsKeys.detail(variables.productId),
      });
    },
  });
}
