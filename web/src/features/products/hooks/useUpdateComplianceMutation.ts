// F2.8.2: update-compliance mutation.
//
// Every successful call writes one row to product_compliance_audit_logs
// server-side, atomically with the product update. The frontend never
// writes audit rows.
//
// Cache invalidation contract (per F2.8.2 brief §5) — broadest of any
// mutation in this module because compliance shifts touch four cache
// scopes simultaneously:
//
//   1. productsKeys.detail(variables.productId)         status fields
//                                                       changed on the
//                                                       row itself.
//   2. productsKeys.lists()                             list cards show
//                                                       compliance_status
//                                                       and a status flip
//                                                       can also evict
//                                                       a row from
//                                                       `only_sellable`
//                                                       filtered lists.
//   3. productsKeys.sellable(variables.productId)       a previously-OK
//                                                       product may now
//                                                       422 (or vice
//                                                       versa).
//   4. productsKeys.complianceAudit(variables.productId) a new audit row
//                                                       was just written
//                                                       server-side.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateProductCompliance } from "../api";
import type { UpdateProductComplianceParams } from "../api";
import type { Product } from "../types";
import { productsKeys } from "./queryKeys";

export function useUpdateComplianceMutation() {
  const queryClient = useQueryClient();

  return useMutation<Product, Error, UpdateProductComplianceParams>({
    mutationFn: (vars) => updateProductCompliance(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: productsKeys.detail(variables.productId),
      });
      queryClient.invalidateQueries({ queryKey: productsKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: productsKeys.sellable(variables.productId),
      });
      queryClient.invalidateQueries({
        queryKey: productsKeys.complianceAudit(variables.productId),
      });
    },
  });
}
