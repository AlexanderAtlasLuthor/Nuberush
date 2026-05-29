// F2.22.5.D: inventory Realtime subscription hook.
//
// Opens a single `postgres_changes` channel on `public.inventory_items`
// and invalidates the TanStack Query `inventoryKeys.all` prefix on
// each (debounced) event. `inventoryKeys.all` is `["inventory"]`,
// which prefix-matches every existing inventory cache key:
//
//   - inventoryKeys.lists()        (store-scoped lists)
//   - inventoryKeys.item(itemId)   (item detail)
//   - inventoryKeys.itemLogs(...)  (per-item log feed)
//   - inventoryKeys.adminLists()   (admin global feed)
//
// Same shape as `useOrdersRealtimeSubscription` — see that file for
// the §9.1 boundary commentary; this hook is the mirror image bound
// to `public.inventory_items`.

import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { inventoryKeys } from "@/features/inventory/hooks";

import { useTableRealtimeSubscription } from "./internal/useTableRealtimeSubscription";

export interface UseInventoryRealtimeSubscriptionOptions {
  /** Coalesce window in ms. Defaults to 200ms (matches the primitive). */
  debounceMs?: number;
}

export function useInventoryRealtimeSubscription(
  options?: UseInventoryRealtimeSubscriptionOptions,
): void {
  const queryClient = useQueryClient();

  const invalidate = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: inventoryKeys.all });
  }, [queryClient]);

  useTableRealtimeSubscription({
    table: "inventory_items",
    channelName: "realtime:inventory_items",
    invalidate,
    debounceMs: options?.debounceMs,
  });
}
