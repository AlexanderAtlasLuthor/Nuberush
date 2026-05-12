// F2.18.2A: admin store-detail hook.
//
// Reads a single store under the admin cache namespace so admin pages
// don't share a cache slot with the singular own-store
// `useStoreQuery`. The underlying API call `getStore` is reused from
// `@/features/store/api` because the wire contract is identical
// regardless of caller role.
//
// Cache key: ["stores", "detail", storeId] — see queryKeys.ts.
//
// Accepts `null | undefined | ""` so callers can pass values from
// route params without an outer guard; the `enabled` flag turns the
// query off until a concrete id is available.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getStore } from "../api";
import type { StoreProfile } from "../types";
import { adminStoresKeys } from "./queryKeys";

export function useAdminStoreQuery(
  storeId: string | null | undefined,
): UseQueryResult<StoreProfile> {
  const safeId = storeId ?? "";

  return useQuery({
    queryKey: adminStoresKeys.detail(safeId),
    queryFn: ({ signal }) => {
      if (!safeId) {
        throw new Error("Store id is required");
      }
      return getStore(safeId, signal);
    },
    enabled: safeId.length > 0,
  });
}
