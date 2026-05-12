// F2.6.2 subfase 3: update-status mutation.
//
// Same shape as the other inventory mutations: variables mirror the
// api-layer params verbatim, success invalidates list + item caches.
// No optimistic update, no setQueryData — backend is authority on the
// post-mutation row, including any side effects on filtered list
// membership.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateInventoryStatus } from "../api";
import type { UpdateInventoryStatusParams } from "../api";
import type { InventoryItem } from "../types";
import { inventoryKeys } from "./queryKeys";

export function useUpdateInventoryStatusMutation() {
  const queryClient = useQueryClient();

  return useMutation<InventoryItem, Error, UpdateInventoryStatusParams>({
    mutationFn: (vars) => updateInventoryStatus(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: inventoryKeys.item(variables.inventoryItemId),
      });
    },
  });
}
