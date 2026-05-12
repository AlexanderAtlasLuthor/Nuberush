// F2.6.2 subfase 2: update-threshold mutation.
//
// Same shape as the movement mutations: variables mirror the api-layer
// params verbatim, success invalidates list + item caches. No
// optimistic update, no setQueryData — the backend is the authority on
// the post-mutation row, including any side effects on `low_stock_only`
// list membership.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateInventoryThreshold } from "../api";
import type { UpdateInventoryThresholdParams } from "../api";
import type { InventoryItem } from "../types";
import { inventoryKeys } from "./queryKeys";

export function useUpdateInventoryThresholdMutation() {
  const queryClient = useQueryClient();

  return useMutation<InventoryItem, Error, UpdateInventoryThresholdParams>({
    mutationFn: (vars) => updateInventoryThreshold(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: inventoryKeys.item(variables.inventoryItemId),
      });
    },
  });
}
