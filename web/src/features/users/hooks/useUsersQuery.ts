// F2.15.4: paginated users list hook.
//
// Tenancy is decided server-side: admins see global, owners/managers
// see their own store, staff/driver get 403. The hook does not pass
// the current store context — the backend uses the JWT subject to
// decide scope.
//
// Cache key: ["users", "list", filters] — see queryKeys.ts.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { listUsers } from "../api";
import type { UserListFilters, UserListResponse } from "../types";
import { usersQueryKeys } from "./queryKeys";

export function useUsersQuery(
  filters: UserListFilters = {},
): UseQueryResult<UserListResponse> {
  return useQuery({
    queryKey: usersQueryKeys.list(filters),
    queryFn: ({ signal }) => listUsers(filters, signal),
  });
}
