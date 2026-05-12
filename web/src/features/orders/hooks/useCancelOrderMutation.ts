// F2.7.0 subfase 3: cancel-order mutation.
//
// Cancel releases inventory reservations (decrements `quantity_reserved`)
// without touching `quantity_on_hand` (orders_rules §3). Manager-or-
// above per orders_rules §6 — backend returns 403 for staff and below.
//
// Cache invalidation contract — same four scopes as the other mutations,
// always-on cross-feature inventory invalidation because cancel
// definitionally changes inventory state:
//
//   1. ordersKeys.lists()              status flips to "canceled".
//   2. ordersKeys.item(orderId)        detail must refetch to expose
//                                      canceled_at + cancel_reason.
//   3. ordersKeys.auditLogs(orderId)   a new audit row was written.
//   4. inventoryKeys.lists()           CROSS-FEATURE: reservations
//                                      released, so any open inventory
//                                      list is stale.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { inventoryKeys } from "@/features/inventory/hooks";
import { cancelOrder } from "../api";
import type { CancelOrderParams } from "../api";
import type { OrderRead } from "../types";
import { ordersKeys } from "./queryKeys";

export function useCancelOrderMutation() {
  const queryClient = useQueryClient();

  return useMutation<OrderRead, Error, CancelOrderParams>({
    mutationFn: (vars) => cancelOrder(vars),
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
