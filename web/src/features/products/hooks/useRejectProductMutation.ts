// Reject-product mutation.
//
// Wraps `POST /products/{id}/reject` (admin-only on the backend).
// Same invalidation surface as useApproveProductMutation — the
// approval state flip is symmetric.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { adminProductsQueryKeys } from "@/features/admin-products/hooks";
import { rejectProduct } from "../api";
import type { RejectProductParams } from "../api";
import type { Product } from "../types";
import { productsKeys } from "./queryKeys";

export function useRejectProductMutation() {
  const queryClient = useQueryClient();

  return useMutation<Product, Error, RejectProductParams>({
    mutationFn: (vars) => rejectProduct(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: productsKeys.detail(variables.productId),
      });
      queryClient.invalidateQueries({ queryKey: productsKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: productsKeys.sellable(variables.productId),
      });
      queryClient.invalidateQueries({
        queryKey: adminProductsQueryKeys.lists(),
      });
    },
  });
}
