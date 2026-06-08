import type { StoreRegulatoryFilters } from "../types";

export const storeRegulatoryKeys = {
  all: ["store-regulatory"] as const,
  alerts: (storeId: string, filters: StoreRegulatoryFilters = {}) =>
    [...storeRegulatoryKeys.all, "alerts", storeId, filters] as const,
  detail: (storeId: string, alertId: string) =>
    [...storeRegulatoryKeys.all, "detail", storeId, alertId] as const,
};
