import { apiRequest } from "@/api";

import type { StoreEarningsSummary } from "./types";

export interface GetStoreEarningsParams {
  storeId: string;
}

export function getStoreEarnings(
  params: GetStoreEarningsParams,
  signal?: AbortSignal,
): Promise<StoreEarningsSummary> {
  const path = `/stores/${encodeURIComponent(params.storeId)}/earnings`;
  return apiRequest<StoreEarningsSummary>(path, { method: "GET", signal });
}
