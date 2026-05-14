// API wrappers for the store-scoped dashboard endpoints introduced in
// `backend/app/api/routes/store_dashboard.py`. Every call routes
// through `apiRequest` from `@/api` so error normalisation and Bearer
// attach stay centralised.

import { apiRequest } from "@/api";

import type {
  StoreAlertsListResponse,
  StoreDashboardKpis,
} from "./types";

export interface GetStoreDashboardKpisParams {
  storeId: string;
}

/**
 * GET /stores/{store_id}/dashboard/kpis
 *
 * Returns the headline KPI bundle. Read-only, computed on request.
 */
export function getStoreDashboardKpis(
  params: GetStoreDashboardKpisParams,
  signal?: AbortSignal,
): Promise<StoreDashboardKpis> {
  const path = `/stores/${encodeURIComponent(params.storeId)}/dashboard/kpis`;
  return apiRequest<StoreDashboardKpis>(path, { signal });
}

export interface GetStoreAlertsParams {
  storeId: string;
  limit?: number;
  offset?: number;
}

/**
 * GET /stores/{store_id}/alerts
 *
 * Returns a paginated, deterministic feed of operational alerts
 * (low_stock, aging_order, no_inventory). Sorted by severity DESC,
 * created_at DESC.
 */
export function getStoreAlerts(
  params: GetStoreAlertsParams,
  signal?: AbortSignal,
): Promise<StoreAlertsListResponse> {
  const search = new URLSearchParams();
  if (params.limit !== undefined) {
    search.set("limit", String(params.limit));
  }
  if (params.offset !== undefined) {
    search.set("offset", String(params.offset));
  }
  const query = search.toString();
  const path = `/stores/${encodeURIComponent(params.storeId)}/alerts${
    query ? `?${query}` : ""
  }`;
  return apiRequest<StoreAlertsListResponse>(path, { signal });
}
