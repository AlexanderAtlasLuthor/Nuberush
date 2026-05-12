// F2.14.4: store-profile detail hook.
//
// Cache key: ["store", "detail", storeId] — see queryKeys.ts.
//
// Accepts `null | undefined | ""` so callers can pass
// `useStoreContext().currentStoreId` directly without an outer guard.
// The `enabled` flag turns the query off until a concrete id is
// available; `queryFn` keeps a defensive throw so a misconfigured
// `enabled` cannot silently fire with an empty string.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getStore } from "../api";
import type { StoreProfile } from "../types";
import { storeKeys } from "./queryKeys";

export function useStoreQuery(
  storeId: string | null | undefined,
): UseQueryResult<StoreProfile> {
  // `storeKeys.detail` is typed for `string`; using an empty fallback
  // when storeId is missing keeps the key shape stable. The `enabled`
  // guard ensures the corresponding queryFn never runs in that state,
  // so the placeholder key never lands real data.
  const safeId = storeId ?? "";

  return useQuery({
    queryKey: storeKeys.detail(safeId),
    queryFn: ({ signal }) => {
      if (!safeId) {
        throw new Error("Store id is required");
      }
      return getStore(safeId, signal);
    },
    enabled: safeId.length > 0,
  });
}
