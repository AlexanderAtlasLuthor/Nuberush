// F2.6.0 subfase 3: paginated inventory list hook.
//
// Reads the active store from `useStoreContext()` so callers never have
// to pass `storeId` and the page can never accidentally render data
// from a different tenant. When the user has no store context (admin
// in global scope, or a non-admin without a bound store), the query is
// disabled — there is no honest fetch to make.
//
// Cache key: ["inventory", "list", storeId, params] — see queryKeys.ts.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { useStoreContext } from "@/auth";
import { getInventoryList } from "../api";
import type { InventoryListResponse } from "../types";
import {
  inventoryKeys,
  type InventoryListQueryParams,
} from "./queryKeys";

export function useInventoryList(
  params: InventoryListQueryParams,
): UseQueryResult<InventoryListResponse> {
  const { currentStoreId } = useStoreContext();

  return useQuery({
    queryKey: inventoryKeys.list(currentStoreId, params),
    queryFn: ({ signal }) => {
      // Defensive: TanStack Query won't call queryFn while `enabled`
      // is false, but TS still narrows here. Throwing yields a real
      // error if a future refactor ever drops the `enabled` guard.
      if (currentStoreId === null) {
        throw new Error(
          "useInventoryList: currentStoreId is null; enabled guard should have prevented this fetch",
        );
      }
      return getInventoryList(
        {
          storeId: currentStoreId,
          limit: params.limit,
          offset: params.offset,
          low_stock_only: params.low_stock_only,
        },
        signal,
      );
    },
    enabled: currentStoreId !== null,
  });
}
