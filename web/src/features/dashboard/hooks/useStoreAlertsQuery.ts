// Read-only hook for the store-scoped alerts feed.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getStoreAlerts } from "../api";
import type { StoreAlertsListResponse } from "../types";
import {
  dashboardKeys,
  type StoreAlertsQueryParams,
} from "./queryKeys";

export interface UseStoreAlertsQueryParams extends StoreAlertsQueryParams {
  storeId: string | null | undefined;
}

export function useStoreAlertsQuery(
  params: UseStoreAlertsQueryParams,
): UseQueryResult<StoreAlertsListResponse> {
  const { storeId, limit, offset } = params;
  const trimmedStoreId = typeof storeId === "string" ? storeId.trim() : "";
  const enabled = trimmedStoreId.length > 0;

  return useQuery({
    queryKey: dashboardKeys.alerts(trimmedStoreId, { limit, offset }),
    queryFn: ({ signal }) => {
      if (!enabled) {
        throw new Error(
          "useStoreAlertsQuery: storeId is empty; enabled guard should have prevented this fetch",
        );
      }
      return getStoreAlerts(
        { storeId: trimmedStoreId, limit, offset },
        signal,
      );
    },
    enabled,
  });
}
