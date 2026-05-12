// F2.8.2: delete-product mutation (soft by default, hard if requested).
//
// Backend returns 204; the mutationFn resolves to `void`.
//
// Cache invalidation contract (per F2.8.2 brief §5):
//
//   1. productsKeys.lists()                    row removed (hard) or
//                                              flipped to inactive (soft).
//   2. productsKeys.detail(variables.productId) detail page now stale or
//                                              404; either way it must
//                                              refetch.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deleteProduct } from "../api";
import type { DeleteProductParams } from "../api";
import { productsKeys } from "./queryKeys";

export function useDeleteProductMutation() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, DeleteProductParams>({
    mutationFn: (vars) => deleteProduct(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: productsKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: productsKeys.detail(variables.productId),
      });
    },
  });
}
