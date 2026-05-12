// F2.6.2 subfase 4: inventory item audit-log hook.
//
// Cache key: ["inventory", "item", itemId, "logs", params] — see
// queryKeys.ts.
//
// Read-only: rows are produced server-side as side effects of movement
// mutations (receive/adjust/damage). Mutation hooks already invalidate
// the parent `inventoryKeys.item(itemId)` prefix, which transitively
// covers this key — no extra invalidation wiring is needed here.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getInventoryItemLogs } from "../api";
import type { InventoryLogEntry } from "../types";
import { inventoryKeys } from "./queryKeys";

export interface UseInventoryItemLogsParams {
  limit?: number;
}

export function useInventoryItemLogs(
  inventoryItemId: string,
  params: UseInventoryItemLogsParams = {},
): UseQueryResult<InventoryLogEntry[]> {
  return useQuery({
    queryKey: inventoryKeys.itemLogs(inventoryItemId, params),
    queryFn: ({ signal }) =>
      getInventoryItemLogs({ inventoryItemId, ...params }, signal),
    enabled: inventoryItemId.length > 0,
  });
}
