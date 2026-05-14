import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getStoreEarnings } from "../api";
import type { StoreEarningsSummary } from "../types";
import { storeEarningsKeys } from "./queryKeys";

export interface UseStoreEarningsQueryParams {
  storeId: string | null | undefined;
}

export function useStoreEarningsQuery(
  params: UseStoreEarningsQueryParams,
): UseQueryResult<StoreEarningsSummary> {
  const trimmedStoreId =
    typeof params.storeId === "string" ? params.storeId.trim() : "";
  const enabled = trimmedStoreId.length > 0;

  return useQuery({
    queryKey: storeEarningsKeys.summary(trimmedStoreId),
    queryFn: ({ signal }) => {
      if (!enabled) {
        throw new Error(
          "useStoreEarningsQuery: storeId is empty; enabled guard should have prevented this fetch",
        );
      }
      return getStoreEarnings({ storeId: trimmedStoreId }, signal);
    },
    enabled,
  });
}
