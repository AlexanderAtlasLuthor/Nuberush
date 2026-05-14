import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getAdminEarnings } from "../api";
import type { AdminEarningsSummary } from "../types";
import { adminEarningsKeys } from "./queryKeys";

export function useAdminEarningsQuery(): UseQueryResult<AdminEarningsSummary> {
  return useQuery({
    queryKey: adminEarningsKeys.summary(),
    queryFn: ({ signal }) => getAdminEarnings(signal),
  });
}
