// F2.7.0 subfase 3: orders list hook.
//
// Reads the active store from `useStoreContext()` so callers never
// pass `storeId` and the page can never accidentally render data
// from a different tenant. When the user has no store context (admin
// in global scope, or a non-admin without a bound store), the query
// is disabled — there is no honest fetch to make.
//
// Cache key: ["orders", "list", storeId, params] — see queryKeys.ts.
//
// The backend returns the BO_PAG envelope: { items, total, limit, offset }.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { useStoreContext } from "@/auth";
import { getOrdersList } from "../api";
import type { OrdersListResponse } from "../types";
import { ordersKeys, type OrdersListQueryParams } from "./queryKeys";

export function useOrdersList(
  params: OrdersListQueryParams,
): UseQueryResult<OrdersListResponse> {
  const { currentStoreId } = useStoreContext();

  return useQuery({
    queryKey: ordersKeys.list(currentStoreId, params),
    queryFn: ({ signal }) => {
      // Defensive: TanStack Query won't call queryFn while `enabled`
      // is false, but TS still narrows here. Throwing yields a real
      // error if a future refactor ever drops the `enabled` guard.
      if (currentStoreId === null) {
        throw new Error(
          "useOrdersList: currentStoreId is null; enabled guard should have prevented this fetch",
        );
      }
      return getOrdersList(
        {
          storeId: currentStoreId,
          limit: params.limit,
          offset: params.offset,
          status: params.status,
          created_from: params.created_from,
          created_to: params.created_to,
        },
        signal,
      );
    },
    enabled: currentStoreId !== null,
  });
}
