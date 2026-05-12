// F2.16.4: unified store audit feed read hook.
//
// Cache key: ["audit", "store-feed", storeId, filters] — see
// queryKeys.ts. Read-only: the feed is built by the backend
// aggregator from append-only log rows; the frontend never merges,
// sorts or invalidates per-feature. A consumer that wants fresh
// data calls `refetch()` from the returned `UseQueryResult`.
//
// Hard rules baked in (mirroring useStoreInventoryLogsQuery):
//   - No useAuth, no currentUser inspection, no role-based gating.
//     Backend authorises every read via `require_staff_or_above` +
//     `require_store_member` and the API surfaces 401/403/404
//     through the centralized `apiRequest` error path.
//   - No useQueryClient — read-only hook.
//   - No optimistic update, no manual setQueryData.
//   - No transformation: `AuditListResponse` is returned exactly
//     as the backend produced it. No client-side sort, no
//     relabelling, no merging with other audit hooks.
//   - No fake rows, no fallback to the legacy inventory-logs hook
//     when the feed errors.
//
// `storeId` shape:
//   Accepts `string | null | undefined` so callers can pass
//   `useStoreContext().currentStoreId` directly. The query is
//   `enabled` only when the trimmed storeId is non-empty;
//   otherwise it stays idle and `getStoreAudit` is never called.
//   Same guard pattern as `useStoreInventoryLogsQuery`.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getStoreAudit } from "../api";
import type { AuditListResponse, StoreAuditFilters } from "../types";
import { auditKeys } from "./queryKeys";

export function useStoreAuditQuery(
  storeId: string | null | undefined,
  filters: StoreAuditFilters = {},
): UseQueryResult<AuditListResponse> {
  const trimmedStoreId =
    typeof storeId === "string" ? storeId.trim() : "";
  const enabled = trimmedStoreId.length > 0;

  return useQuery({
    // When disabled, key under the empty store id so simultaneous
    // "no store" mounts share one idle slot rather than fragmenting
    // the cache. The enabled flag prevents the queryFn from ever
    // running while storeId is unusable.
    queryKey: auditKeys.storeFeed(trimmedStoreId, filters),
    queryFn: ({ signal }) => {
      // Defensive: TanStack Query won't call queryFn while
      // `enabled` is false, but throw explicitly if a future
      // refactor ever drops the guard.
      if (!enabled) {
        throw new Error(
          "useStoreAuditQuery: storeId is empty; enabled guard should have prevented this fetch",
        );
      }
      return getStoreAudit(trimmedStoreId, filters, signal);
    },
    enabled,
  });
}
