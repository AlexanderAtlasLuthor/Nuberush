// F2.18.2A: paginated admin stores list hook.
//
// Backend `GET /stores` is admin-only — non-admins get 403 before any
// filter is read. The hook is permission-blind on purpose; the UI
// caller decides whether to render this query based on the session
// user's role. The 403 path is real and is surfaced as ApiError to
// the caller (UI renders the server detail).
//
// Cache key: ["stores", "list", filters] — see queryKeys.ts.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { listStores } from "../api";
import type { StoreListFilters, StoreListResponse } from "../types";
import { adminStoresKeys } from "./queryKeys";

export function useAdminStoresQuery(
  filters: StoreListFilters = {},
): UseQueryResult<StoreListResponse> {
  return useQuery({
    queryKey: adminStoresKeys.list(filters),
    queryFn: ({ signal }) => listStores(filters, signal),
  });
}
