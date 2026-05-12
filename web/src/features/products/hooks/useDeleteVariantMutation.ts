// F2.8.2: delete-variant mutation (soft by default, hard if requested).
//
// Backend returns 204 (no body), so we cannot read the parent product
// id from the response like `useUpdateVariantMutation` does. Callers
// MUST pass `productId` in the variables alongside `variantId`, both so
// the hook can invalidate the parent's variant list and so the caller
// has explicitly named which product they think they are operating on.
//
// Cache invalidation contract (per F2.8.2 brief §5):
//
//   1. productsKeys.variants(variables.productId)  list now missing /
//                                                  inactive row.
//   2. productsKeys.detail(variables.productId)    detail page stale.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteProductVariant } from "../api";
import { productsKeys } from "./queryKeys";

export interface DeleteVariantMutationVariables {
  /** Variant UUID. Goes into the URL path. */
  variantId: string;
  /**
   * Parent product UUID. NOT sent on the wire (the route is
   * `DELETE /variants/{variant_id}`); used only for cache invalidation
   * because the 204 response carries no body to read it from.
   */
  productId: string;
  /** Optional. true → hard delete; default / false → soft delete. */
  hard?: boolean;
}

export function useDeleteVariantMutation() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, DeleteVariantMutationVariables>({
    mutationFn: (vars) =>
      deleteProductVariant({
        variantId: vars.variantId,
        hard: vars.hard,
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
