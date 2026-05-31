// F2.24.C7: admin store-applications list query hook.
//
// Thin wrapper over `listStoreApplications`. The hook owns the cache key
// and the queryFn; the page owns the filters and renders the result. No
// business logic — backend is authoritative.

import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";

import { listStoreApplications } from "../api";
import { adminStoreApplicationsKeys } from "./queryKeys";
import type {
  StoreApplicationListFilters,
  StoreApplicationListResponse,
} from "../types";

export function useAdminStoreApplicationsQuery(
  filters: StoreApplicationListFilters = {},
): UseQueryResult<StoreApplicationListResponse> {
  return useQuery({
    queryKey: adminStoreApplicationsKeys.list(filters),
    queryFn: ({ signal }) => listStoreApplications(filters, signal),
  });
}
