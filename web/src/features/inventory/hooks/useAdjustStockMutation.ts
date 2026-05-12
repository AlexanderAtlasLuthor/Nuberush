// F2.6.0 subfase 3: adjust-stock mutation.
//
// Same pattern as useReceiveStockMutation: variables mirror the api
// param shape, success invalidates lists + the affected item key. See
// the receive-mutation file for the rationale.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { adjustStock } from "../api";
import type { AdjustStockParams } from "../api";
import type { InventoryItem } from "../types";
import { inventoryKeys } from "./queryKeys";

export function useAdjustStockMutation() {
  const queryClient = useQueryClient();

  return useMutation<InventoryItem, Error, AdjustStockParams>({
    mutationFn: (vars) => adjustStock(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: inventoryKeys.item(variables.inventoryItemId),
      });
    },
  });
}
