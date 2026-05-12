// F2.7.0 subfase 3: return-order mutation.
//
// Return replenishes inventory by raising `quantity_on_hand` and writes
// `return_` movements on inventory_logs (orders_rules §3). Only valid
// after `delivered`. Manager-or-above per orders_rules §6.
//
// Cache invalidation contract — same four scopes; cross-feature
// invalidation is mandatory because return mutates inventory by
// definition:
//
//   1. ordersKeys.lists()              status flips to "returned".
//   2. ordersKeys.item(orderId)        detail must refetch to expose
//                                      returned_at.
//   3. ordersKeys.auditLogs(orderId)   a new audit row was written.
//   4. inventoryKeys.lists()           CROSS-FEATURE: quantity_on_hand
//                                      raised on every line item, so
//                                      any open inventory list is
//                                      stale.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { inventoryKeys } from "@/features/inventory/hooks";
import { returnOrder } from "../api";
import type { ReturnOrderParams } from "../api";
import type { OrderRead } from "../types";
import { ordersKeys } from "./queryKeys";

export function useReturnOrderMutation() {
  const queryClient = useQueryClient();

  return useMutation<OrderRead, Error, ReturnOrderParams>({
    mutationFn: (vars) => returnOrder(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: ordersKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: ordersKeys.item(variables.orderId),
      });
      queryClient.invalidateQueries({
        queryKey: ordersKeys.auditLogs(variables.orderId),
      });
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
    },
  });
}
