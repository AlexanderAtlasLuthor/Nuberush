// F2.22.5.D: orders Realtime subscription hook.
//
// Opens a single `postgres_changes` channel on `public.orders` and
// invalidates the TanStack Query `ordersKeys.all` prefix on each
// (debounced) event. `ordersKeys.all` is `["orders"]`, which
// prefix-matches every existing orders cache key:
//
//   - ordersKeys.lists()        (store-scoped lists)
//   - ordersKeys.item(orderId)  (order detail)
//   - ordersKeys.auditLogs(...) (per-order audit feed)
//   - ordersKeys.adminLists()   (admin global feed)
//
// This single root-prefix invalidation matches the §9.1 lock: every
// active orders query refetches from FastAPI after a change, and the
// realtime payload is never read. Over-invalidation on idle screens
// is harmless because TanStack Query refetches only mounted queries.

import { useCallback } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { ordersKeys } from "@/features/orders/hooks";

import { useTableRealtimeSubscription } from "./internal/useTableRealtimeSubscription";

export interface UseOrdersRealtimeSubscriptionOptions {
  /** Coalesce window in ms. Defaults to 200ms (matches the primitive). */
  debounceMs?: number;
}

export function useOrdersRealtimeSubscription(
  options?: UseOrdersRealtimeSubscriptionOptions,
): void {
  const queryClient = useQueryClient();

  const invalidate = useCallback(() => {
    // Single root-prefix invalidation. See file header for the
    // sub-keys this covers.
    queryClient.invalidateQueries({ queryKey: ordersKeys.all });
  }, [queryClient]);

  useTableRealtimeSubscription({
    table: "orders",
    channelName: "realtime:orders",
    invalidate,
    debounceMs: options?.debounceMs,
  });
}
