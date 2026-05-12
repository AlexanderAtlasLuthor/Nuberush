// F2.18.2C: admin global inventory feed read hook.
//
// Cache key: ["inventory", "admin", "list", filters] — see
// queryKeys.ts. Read-only: the feed is built server-side; the
// frontend never merges, sorts, or normalises inventory rows here.
// A consumer that wants fresh data calls `refetch()` from the
// returned `UseQueryResult`.
//
// Hard rules baked in (mirroring useAdminAuditQuery):
//   - No useAuth, no currentUser inspection, no role-based gating.
//     Backend authorises every read via `require_admin` and the API
//     surfaces 401/403/404 through the centralized `apiRequest`
//     error path.
//   - No useStoreContext — the admin feed is global by design;
//     `store_id` lives inside the filters object as an optional
//     scope filter.
//   - No useQueryClient — read-only hook.
//   - No mutations.
//   - No transformation: `InventoryListResponse` is returned exactly
//     as the backend produced it.
//   - No fallback to the store-scoped list when the admin feed
//     errors.
//
// No store context is required. Unlike `useInventoryList`, this
// hook is always enabled.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getAdminInventory } from "../api";
import type {
  AdminInventoryFilters,
  InventoryListResponse,
} from "../types";
import { inventoryKeys } from "./queryKeys";

export function useAdminInventoryQuery(
  filters: AdminInventoryFilters = {},
): UseQueryResult<InventoryListResponse> {
  return useQuery({
    queryKey: inventoryKeys.adminList(filters),
    queryFn: ({ signal }) => getAdminInventory(filters, signal),
  });
}
