// F2.6.2 subfase 1: damage-stock mutation.
//
// Same shape as useReceiveStockMutation / useAdjustStockMutation:
// variables mirror the api-layer params verbatim, success invalidates
// list + item caches. No optimistic update, no setQueryData — the
// backend is the authority on the post-mutation balance.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { damageStock } from "../api";
import type { DamageStockParams } from "../api";
import type { InventoryItem } from "../types";
import { inventoryKeys } from "./queryKeys";

export function useDamageStockMutation() {
  const queryClient = useQueryClient();

  return useMutation<InventoryItem, Error, DamageStockParams>({
    mutationFn: (vars) => damageStock(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: inventoryKeys.item(variables.inventoryItemId),
      });
    },
  });
}
