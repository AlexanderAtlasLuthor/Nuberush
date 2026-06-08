import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getStoreRegulatoryAlerts } from "../api";
import type {
  StoreRegulatoryAlertsResponse,
  StoreRegulatoryFilters,
} from "../types";
import { storeRegulatoryKeys } from "./queryKeys";

export function useStoreRegulatoryAlertsQuery(
  storeId: string | null | undefined,
  filters: StoreRegulatoryFilters = {},
): UseQueryResult<StoreRegulatoryAlertsResponse> {
  const trimmedStoreId = typeof storeId === "string" ? storeId.trim() : "";
  const enabled = trimmedStoreId.length > 0;

  return useQuery({
    queryKey: storeRegulatoryKeys.alerts(trimmedStoreId, filters),
    queryFn: ({ signal }) => {
      if (!enabled) {
        throw new Error(
          "useStoreRegulatoryAlertsQuery: storeId is empty; enabled guard should have prevented this fetch",
        );
      }
      return getStoreRegulatoryAlerts(trimmedStoreId, filters, signal);
    },
    enabled,
  });
}
