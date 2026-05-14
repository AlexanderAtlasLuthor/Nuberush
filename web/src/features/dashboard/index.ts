// Public barrel for the store-scoped dashboard feature module.

export { useStoreAlertsQuery } from "./hooks/useStoreAlertsQuery";
export { useStoreDashboardKpisQuery } from "./hooks/useStoreDashboardKpisQuery";
export type {
  StoreAlert,
  StoreAlertCategory,
  StoreAlertEntityType,
  StoreAlertSeverity,
  StoreAlertsListResponse,
  StoreDashboardKpis,
  StoreOrdersByStatus,
} from "./types";
