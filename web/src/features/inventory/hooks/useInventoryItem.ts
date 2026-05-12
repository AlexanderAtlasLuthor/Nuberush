// F2.6.0 subfase 3: single inventory item hook.
//
// The backend endpoint is item-scoped (`GET /inventory/{item_id}`) and
// resolves the owning store from the row, so this hook does NOT read
// `currentStoreId` — passing the wrong storeId would have no effect on
// the URL anyway. Tenancy is enforced server-side; the frontend
// surfaces its 401/403 via ApiError untouched.
//
// Cache key: ["inventory", "item", itemId] — see queryKeys.ts.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getInventoryItem } from "../api";
import type { InventoryItem } from "../types";
import { inventoryKeys } from "./queryKeys";

export function useInventoryItem(
  inventoryItemId: string,
): UseQueryResult<InventoryItem> {
  return useQuery({
    queryKey: inventoryKeys.item(inventoryItemId),
    queryFn: ({ signal }) =>
      getInventoryItem({ inventoryItemId }, signal),
    // Defensive guard for empty-string. Caller-typed as string, but a
    // page that derives the id from a route param can briefly land
    // here with "" before the param resolves.
    enabled: inventoryItemId.length > 0,
  });
}
