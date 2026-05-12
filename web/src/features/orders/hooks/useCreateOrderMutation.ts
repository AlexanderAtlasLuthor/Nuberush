// F2.7.0 subfase 3: create-order mutation.
//
// Mutation variables match the api-layer params shape exactly so the
// mutationFn is a pass-through. Callers invoke as:
//
//   const m = useCreateOrderMutation();
//   m.mutate({ storeId, body: { idempotency_key, items, notes } });
//
// Cache invalidation contract (CRITICAL — F2.7.0 brief §5):
//
//   1. ordersKeys.lists()              every paginated/filtered list
//   2. ordersKeys.item(data.id)        the brand-new order's detail
//   3. ordersKeys.auditLogs(data.id)   the brand-new audit trail (the
//                                      service writes the create-row
//                                      in the same transaction)
//   4. inventoryKeys.lists()           CROSS-FEATURE: creating an
//                                      order RAISES quantity_reserved
//                                      on every line item's inventory
//                                      row (orders_rules §3 — reserve
//                                      effect on CREATE), so any
//                                      InventoryPage open in another
//                                      tab/route is now stale.
//
// We use `data.id` (the response) for the item / auditLogs invalidations
// because the order id is not in the variables — it's server-generated.
// The other three mutations carry `orderId` in variables and use that.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { inventoryKeys } from "@/features/inventory/hooks";
import { createOrder } from "../api";
import type { CreateOrderParams } from "../api";
import type { OrderRead } from "../types";
import { ordersKeys } from "./queryKeys";

export function useCreateOrderMutation() {
  const queryClient = useQueryClient();

  return useMutation<OrderRead, Error, CreateOrderParams>({
    mutationFn: (vars) => createOrder(vars),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ordersKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: ordersKeys.item(data.id),
      });
      queryClient.invalidateQueries({
        queryKey: ordersKeys.auditLogs(data.id),
      });
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
    },
  });
}
