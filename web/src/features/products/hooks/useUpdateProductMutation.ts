// F2.8.2: update-product mutation (non-compliance fields only).
//
// Cache invalidation contract (per F2.8.2 brief §5):
//
//   1. productsKeys.lists()                    list rows show name /
//                                              brand / category which
//                                              the body may have changed.
//   2. productsKeys.detail(variables.productId) refetch detail to expose
//                                              new field values + bumped
//                                              updated_at.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateProduct } from "../api";
import type { UpdateProductParams } from "../api";
import type { Product } from "../types";
import { productsKeys } from "./queryKeys";

export function useUpdateProductMutation() {
  const queryClient = useQueryClient();

  return useMutation<Product, Error, UpdateProductParams>({
    mutationFn: (vars) => updateProduct(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: productsKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: productsKeys.detail(variables.productId),
      });
    },
  });
}
