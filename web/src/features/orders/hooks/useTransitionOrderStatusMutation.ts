// F2.7.0 subfase 3: transition-order-status mutation.
//
// Used for forward transitions in the lifecycle (pending → accepted →
// preparing → ready → out_for_delivery → delivered). The backend
// rejects with 422 if `body.new_status` is `"canceled"` / `"returned"`,
// routing the operator to the dedicated cancel/return mutations.
//
// Cache invalidation contract (CRITICAL — F2.7.0 brief §5):
//
//   1. ordersKeys.lists()              status changes alter list views
//                                      that filter by status.
//   2. ordersKeys.item(orderId)        the order's detail must refetch
//                                      to expose the new status and
//                                      lifecycle timestamps.
//   3. ordersKeys.auditLogs(orderId)   a new audit row was written.
//   4. inventoryKeys.lists()           CROSS-FEATURE: only one transition
//                                      actually mutates inventory
//                                      (out_for_delivery → delivered
//                                      consumes reservations: -reserved,
//                                      -on_hand). The other forward
//                                      transitions don't touch inventory.
//                                      We invalidate unconditionally
//                                      because the hook does not branch
//                                      on `body.new_status` (that would
//                                      duplicate orders_rules §3 in
//                                      the frontend); a no-op refetch
//                                      is cheaper than a desync risk.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { inventoryKeys } from "@/features/inventory/hooks";
import { transitionOrderStatus } from "../api";
import type { TransitionOrderStatusParams } from "../api";
import type { OrderRead } from "../types";
import { ordersKeys } from "./queryKeys";

export function useTransitionOrderStatusMutation() {
  const queryClient = useQueryClient();

  return useMutation<OrderRead, Error, TransitionOrderStatusParams>({
    mutationFn: (vars) => transitionOrderStatus(vars),
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
