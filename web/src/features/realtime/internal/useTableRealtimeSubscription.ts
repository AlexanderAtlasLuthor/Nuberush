// F2.22.5.D: shared Supabase Realtime subscription primitive.
//
// Opens a single Supabase Realtime channel on the given `public.<table>`,
// listens for `postgres_changes`, and coalesces bursts of events into a
// single invalidation call via a small debounce window. Cleanup removes
// the channel and clears any pending timer.
//
// Hard rules (docs/f2.22-contract-lock.md §§7, 9, 9.1):
//
//   - Payload is treated as OPAQUE. The callback discards the event
//     object and calls `invalidate()` only. The UI re-renders from
//     the FastAPI refetch that follows; nothing in this module reads
//     or stores business row data.
//   - No `supabase.from(...)`. The channel API is the only Supabase
//     surface this hook touches.
//   - No `setQueryData` and no payload-derived cache mutations.
//   - No service-role key. The supabase-js client is anon-only.
//   - No presence, no broadcast, no custom WebSocket — only
//     `postgres_changes` on the locked table.
//
// Single-mount intent: this hook owns a fixed channel name per table.
// Mount it at most once per app shell. Mounting from multiple
// surfaces in the same page tree would collide on the channel name
// and multiply WebSocket connections without benefit.

import { useEffect, useRef } from "react";
import type { RealtimeChannel } from "@supabase/supabase-js";

import { supabase } from "@/lib/supabase";

/** Tables that F2.22.5 allows on the realtime channel. */
export type RealtimeTable = "orders" | "inventory_items";

export interface UseTableRealtimeSubscriptionOptions {
  /** Locked `public.<table>` target. */
  table: RealtimeTable;
  /**
   * Fixed channel name (e.g. `"realtime:orders"`). Pinned per table so
   * concurrent mounts of the same hook collapse onto one connection.
   */
  channelName: string;
  /**
   * Invalidation callback. Invoked at most once per debounce window
   * regardless of how many Realtime events arrived during that window.
   * Implementations should call `queryClient.invalidateQueries({...})`;
   * they MUST NOT read or store any payload, and MUST NOT call
   * `queryClient.setQueryData(...)` with payload-derived data.
   */
  invalidate: () => void;
  /** Coalesce window in ms. Defaults to 200ms. */
  debounceMs?: number;
}

const DEFAULT_DEBOUNCE_MS = 200;

export function useTableRealtimeSubscription({
  table,
  channelName,
  invalidate,
  debounceMs = DEFAULT_DEBOUNCE_MS,
}: UseTableRealtimeSubscriptionOptions): void {
  // Latch the latest invalidate without retriggering the effect when
  // the caller passes a fresh closure on each render.
  const invalidateRef = useRef(invalidate);
  invalidateRef.current = invalidate;

  useEffect(() => {
    let timerId: ReturnType<typeof setTimeout> | null = null;

    const scheduleInvalidate = (): void => {
      // Already scheduled in this window — ride the existing timer
      // so N events collapse to one invalidation.
      if (timerId !== null) return;
      timerId = setTimeout(() => {
        timerId = null;
        invalidateRef.current();
      }, debounceMs);
    };

    const channel: RealtimeChannel = supabase
      .channel(channelName)
      .on(
        // F2.22.5.B locked surface — postgres_changes only.
        "postgres_changes" as unknown as never,
        { event: "*", schema: "public", table },
        () => {
          // F2.22.5 contract §9.1: payload is OPAQUE — discarded.
          // We only signal "something changed on this table"; the
          // refetch through FastAPI is what surfaces the new data.
          scheduleInvalidate();
        },
      )
      .subscribe();

    return () => {
      if (timerId !== null) {
        clearTimeout(timerId);
        timerId = null;
      }
      // Use `removeChannel` (supabase-js 2.x recommended cleanup).
      // It both unsubscribes and removes the channel from the client.
      supabase.removeChannel(channel);
    };
  }, [table, channelName, debounceMs]);
}
