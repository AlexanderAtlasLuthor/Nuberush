// Read-only hook for the store-scoped KPI bundle.
//
// Mirrors the `useStoreInventoryLogsQuery` pattern: accepts a nullable
// storeId, disables itself until a non-empty store is in scope, and
// returns the raw wire shape unchanged.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getStoreDashboardKpis } from "../api";
import type { StoreDashboardKpis } from "../types";
import { dashboardKeys } from "./queryKeys";

export interface UseStoreDashboardKpisQueryParams {
  storeId: string | null | undefined;
}

export function useStoreDashboardKpisQuery(
  params: UseStoreDashboardKpisQueryParams,
): UseQueryResult<StoreDashboardKpis> {
  const trimmedStoreId =
    typeof params.storeId === "string" ? params.storeId.trim() : "";
  const enabled = trimmedStoreId.length > 0;

  return useQuery({
    queryKey: dashboardKeys.kpis(trimmedStoreId),
    queryFn: ({ signal }) => {
      if (!enabled) {
        throw new Error(
          "useStoreDashboardKpisQuery: storeId is empty; enabled guard should have prevented this fetch",
        );
      }
      return getStoreDashboardKpis(
        { storeId: trimmedStoreId },
        signal,
      );
    },
    enabled,
  });
}
