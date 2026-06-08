import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getStoreRegulatoryAlertDetail } from "../api";
import type { StoreRegulatoryAlert } from "../types";
import { storeRegulatoryKeys } from "./queryKeys";

export function useStoreRegulatoryAlertDetailQuery(
  storeId: string | null | undefined,
  alertId: string | null | undefined,
): UseQueryResult<StoreRegulatoryAlert> {
  const trimmedStoreId = typeof storeId === "string" ? storeId.trim() : "";
  const trimmedAlertId = typeof alertId === "string" ? alertId.trim() : "";
  const enabled = trimmedStoreId.length > 0 && trimmedAlertId.length > 0;

  return useQuery({
    queryKey: storeRegulatoryKeys.detail(trimmedStoreId, trimmedAlertId),
    queryFn: ({ signal }) => {
      if (!enabled) {
        throw new Error(
          "useStoreRegulatoryAlertDetailQuery: storeId/alertId is empty; enabled guard should have prevented this fetch",
        );
      }
      return getStoreRegulatoryAlertDetail(
        trimmedStoreId,
        trimmedAlertId,
        signal,
      );
    },
    enabled,
  });
}
