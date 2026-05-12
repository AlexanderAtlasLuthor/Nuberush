// F2.7.0 subfase 3: single-order hook.
//
// The backend endpoint is item-scoped (`GET /orders/{order_id}`) and
// resolves the owning store from the row, so this hook does NOT read
// `currentStoreId`. Tenancy is enforced server-side; the frontend
// surfaces 401/403 via ApiError untouched.
//
// Cache key: ["orders", "item", orderId] — see queryKeys.ts.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getOrder } from "../api";
import type { OrderRead } from "../types";
import { ordersKeys } from "./queryKeys";

export function useOrder(orderId: string): UseQueryResult<OrderRead> {
  return useQuery({
    queryKey: ordersKeys.item(orderId),
    queryFn: ({ signal }) => getOrder({ orderId }, signal),
    // Defensive guard for empty-string. Caller-typed as string, but
    // a page that derives the id from a route param can briefly land
    // here with "" before the param resolves.
    enabled: orderId.length > 0,
  });
}
