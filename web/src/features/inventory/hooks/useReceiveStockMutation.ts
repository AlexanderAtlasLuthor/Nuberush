// F2.6.0 subfase 3: receive-stock mutation.
//
// Mutation variables match the api-layer params shape exactly so the
// mutationFn is a pass-through. Callers invoke as:
//
//   const m = useReceiveStockMutation();
//   m.mutate({ inventoryItemId, body: { quantity: 5 } });
//
// On success we invalidate two cache scopes:
//
//   1. Every paginated list (`["inventory","list"]` prefix) — quantity
//      changes can shift `low_stock_only` membership and pagination
//      totals, so any list view in the cache is stale.
//   2. The specific item key — detail pages re-fetch the post-mutation
//      balance instead of re-using the optimistic-stale row.
//
// We do NOT setQueryData with the response on purpose: invalidation is
// the conservative default and avoids subtle bugs where a list and a
// detail view end up with inconsistent shapes after a refactor. We can
// add an opportunistic setQueryData later if profiling demands it.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { receiveStock } from "../api";
import type { ReceiveStockParams } from "../api";
import type { InventoryItem } from "../types";
import { inventoryKeys } from "./queryKeys";

export function useReceiveStockMutation() {
  const queryClient = useQueryClient();

  return useMutation<InventoryItem, Error, ReceiveStockParams>({
    mutationFn: (vars) => receiveStock(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: inventoryKeys.item(variables.inventoryItemId),
      });
    },
  });
}
