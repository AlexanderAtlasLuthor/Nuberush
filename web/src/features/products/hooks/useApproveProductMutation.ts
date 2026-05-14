// Approve-product mutation.
//
// Wraps `POST /products/{id}/approve` (admin-only on the backend).
// Invalidation surface mirrors `useUpdateComplianceMutation` because an
// approval state flip touches the same cache scopes:
//
//   1. productsKeys.detail(id)            approval_status / reviewed_*
//                                         fields changed.
//   2. productsKeys.lists()               list rows display the badge
//                                         and visibility rules differ
//                                         between approval states.
//   3. productsKeys.sellable(id)          a previously-pending product
//                                         may now be sellable.
//   4. adminProductsQueryKeys.lists()     the admin oversight list has
//                                         its own key namespace and
//                                         needs to refresh too.
//
// We do not setQueryData with the response: invalidation is the
// conservative default and matches every other mutation in this module.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { adminProductsQueryKeys } from "@/features/admin-products/hooks";
import { approveProduct } from "../api";
import type { ApproveProductParams } from "../api";
import type { Product } from "../types";
import { productsKeys } from "./queryKeys";

export function useApproveProductMutation() {
  const queryClient = useQueryClient();

  return useMutation<Product, Error, ApproveProductParams>({
    mutationFn: (vars) => approveProduct(vars),
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
