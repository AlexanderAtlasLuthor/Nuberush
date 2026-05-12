// F2.18.2C: admin global orders feed read hook.
//
// Cache key: ["orders", "admin", "list", filters] — see queryKeys.ts.
// Read-only: the feed is built server-side. A consumer that wants
// fresh data calls `refetch()` from the returned `UseQueryResult`.
//
// Hard rules baked in (mirroring useAdminInventoryQuery /
// useAdminAuditQuery):
//   - No useAuth, no currentUser inspection, no role-based gating.
//     Backend authorises every read via `require_admin` and the API
//     surfaces 401/403/404 through the centralized `apiRequest`
//     error path.
//   - No useStoreContext — the admin feed is global by design;
//     `store_id` lives inside the filters object as an optional
//     scope filter.
//   - No useQueryClient — read-only hook.
//   - No mutations.
//   - No transformation: `OrdersListResponse` is returned exactly
//     as the backend produced it.
//   - No fallback to the store-scoped list when the admin feed
//     errors.
//
// No store context is required. Unlike `useOrdersList`, this hook is
// always enabled.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getAdminOrders } from "../api";
import type {
  AdminOrdersFilters,
  OrdersListResponse,
} from "../types";
import { ordersKeys } from "./queryKeys";

export function useAdminOrdersQuery(
  filters: AdminOrdersFilters = {},
): UseQueryResult<OrdersListResponse> {
  return useQuery({
    queryKey: ordersKeys.adminList(filters),
    queryFn: ({ signal }) => getAdminOrders(filters, signal),
  });
}
