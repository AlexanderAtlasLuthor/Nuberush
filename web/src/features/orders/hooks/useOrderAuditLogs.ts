// F2.7.0 subfase 3: order audit-log hook.
//
// Cache key: ["orders", "auditLogs", orderId] — see queryKeys.ts.
//
// Audit rows are append-only by convention (orders_rules §8). This
// hook is read-only; the rows are produced by the orders service in
// the same transaction as each state mutation, so refetching after a
// mutation is the only way to see new entries (mutations invalidate
// this key explicitly — see the mutation hooks).

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getOrderAuditLogs } from "../api";
import type { OrderAuditLogRead } from "../types";
import { ordersKeys } from "./queryKeys";

export function useOrderAuditLogs(
  orderId: string,
): UseQueryResult<OrderAuditLogRead[]> {
  return useQuery({
    queryKey: ordersKeys.auditLogs(orderId),
    queryFn: ({ signal }) => getOrderAuditLogs({ orderId }, signal),
    enabled: orderId.length > 0,
  });
}
