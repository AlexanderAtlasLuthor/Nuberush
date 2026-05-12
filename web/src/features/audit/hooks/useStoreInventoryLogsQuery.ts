// F2.10.2: store inventory logs read hook.
//
// Cache key: ["audit", "store-inventory-logs", storeId, params] —
// see queryKeys.ts.
//
// Read-only: rows are produced server-side by inventory mutations
// (receive / adjust / damage / movement-as-side-effect-of-orders).
// The inventory feature's mutation hooks already invalidate
// `inventoryKeys.lists()` / `inventoryKeys.item(...)` after each
// movement; this audit hook is intentionally NOT auto-invalidated by
// those — its rows are append-only by convention, and TanStack Query
// will refetch on remount or via explicit `refetch()` from the panel.
// We avoid adding a cross-feature invalidation rule here because
// (a) it would couple two feature caches together implicitly, and
// (b) the audit page in F2.10.3 owns its refresh UX explicitly.
//
// Hard rules baked in (mirroring features/inventory/hooks):
//   - No useAuth, no currentUser inspection, no role-based gating.
//     Backend authorises every read via `require_staff_or_above` +
//     `require_store_member` and the API surfaces 401/403/404
//     through the centralized `apiRequest` error path.
//   - No useQueryClient — this hook only reads.
//   - No optimistic update, no manual setQueryData.
//   - No transformation: the resolved `StoreInventoryLogEntry[]` is
//     returned exactly as the backend produced it. No client-side
//     sort, no relabelling, no merging with order/compliance audit
//     rows. The backend orders DESC by `created_at`; we don't
//     re-sort.
//   - No unsupported filter params (offset/total/user_id/event_type/
//     entity_type/created_from/created_to) — those are not in the
//     hook signature, not in the cache key, and not forwarded to
//     the API.
//
// `storeId` shape:
//   The hook accepts `string | null | undefined` so the F2.10.3 page
//   can pass `currentStoreId` from `useStoreContext()` without
//   pre-narrowing. The query is `enabled` only when the trimmed
//   storeId is non-empty; otherwise it stays idle and `getStoreInventoryLogs`
//   is never called. Same enabled-guard pattern as
//   `useInventoryItem` / `useInventoryItemLogs`.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getStoreInventoryLogs } from "../api";
import type { StoreInventoryLogEntry } from "../types";
import {
  auditKeys,
  type StoreInventoryLogsQueryParams,
} from "./queryKeys";

export interface UseStoreInventoryLogsQueryParams
  extends StoreInventoryLogsQueryParams {
  /**
   * Store UUID. Accepts `string | null | undefined` so callers can
   * pass `useStoreContext().currentStoreId` directly. The query is
   * disabled while the value is null/undefined/empty/whitespace and
   * `getStoreInventoryLogs` is not called.
   */
  storeId: string | null | undefined;
}

export function useStoreInventoryLogsQuery(
  params: UseStoreInventoryLogsQueryParams,
): UseQueryResult<StoreInventoryLogEntry[]> {
  const { storeId, limit } = params;
  const trimmedStoreId =
    typeof storeId === "string" ? storeId.trim() : "";
  const enabled = trimmedStoreId.length > 0;

  return useQuery({
    // When disabled, key the query under an empty store sentinel so
    // two simultaneous "no store" mounts share one idle slot rather
    // than fragmenting the cache. The enabled flag prevents the
    // queryFn from ever running while storeId is unusable.
    queryKey: auditKeys.storeInventoryLogs(trimmedStoreId, { limit }),
    queryFn: ({ signal }) => {
      // Defensive: TanStack Query won't call queryFn while
      // `enabled` is false, but TS still narrows `storeId` here.
      // Throwing keeps the failure mode honest if a future refactor
      // ever drops the `enabled` guard.
      if (!enabled) {
        throw new Error(
          "useStoreInventoryLogsQuery: storeId is empty; enabled guard should have prevented this fetch",
        );
      }
      return getStoreInventoryLogs(
        { storeId: trimmedStoreId, limit },
        signal,
      );
    },
    enabled,
  });
}
