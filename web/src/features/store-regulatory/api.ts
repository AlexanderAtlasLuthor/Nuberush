// Store-scoped Regulatory API client (F2.27.6).
//
// Read-only: two GET calls against the store-scoped backend routes. No mutation
// function exists here by design — acknowledge/dismiss/resolve live only on the
// admin surface and are never imported into this feature.

import { apiRequest } from "@/api";

import type {
  StoreRegulatoryAlert,
  StoreRegulatoryAlertsResponse,
  StoreRegulatoryFilters,
} from "./types";

function buildAlertsQuery(filters: StoreRegulatoryFilters): string {
  const query = new URLSearchParams();
  if (filters.status !== undefined) query.set("status", filters.status);
  if (filters.severity !== undefined) query.set("severity", filters.severity);
  if (filters.recommended_action !== undefined) {
    query.set("recommended_action", filters.recommended_action);
  }
  if (filters.product_id !== undefined) {
    query.set("product_id", filters.product_id);
  }
  if (filters.limit !== undefined) query.set("limit", String(filters.limit));
  if (filters.offset !== undefined) {
    query.set("offset", String(filters.offset));
  }
  const qs = query.toString();
  return qs.length > 0 ? `?${qs}` : "";
}

export function getStoreRegulatoryAlerts(
  storeId: string,
  filters: StoreRegulatoryFilters = {},
  signal?: AbortSignal,
): Promise<StoreRegulatoryAlertsResponse> {
  const path = `/stores/${encodeURIComponent(storeId)}/regulatory/alerts${buildAlertsQuery(
    filters,
  )}`;
  return apiRequest<StoreRegulatoryAlertsResponse>(path, {
    method: "GET",
    signal,
  });
}

export function getStoreRegulatoryAlertDetail(
  storeId: string,
  alertId: string,
  signal?: AbortSignal,
): Promise<StoreRegulatoryAlert> {
  const path = `/stores/${encodeURIComponent(
    storeId,
  )}/regulatory/alerts/${encodeURIComponent(alertId)}`;
  return apiRequest<StoreRegulatoryAlert>(path, { method: "GET", signal });
}
