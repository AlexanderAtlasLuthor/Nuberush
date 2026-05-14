// Query-key factory for the store-scoped dashboard hooks.

export interface StoreAlertsQueryParams {
  limit?: number;
  offset?: number;
}

export const dashboardKeys = {
  all: ["store-dashboard"] as const,

  kpis: (storeId: string) =>
    [...dashboardKeys.all, "kpis", storeId] as const,

  alerts: (storeId: string, params: StoreAlertsQueryParams = {}) =>
    [...dashboardKeys.all, "alerts", storeId, params] as const,
};
