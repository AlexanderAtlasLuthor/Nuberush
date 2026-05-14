// Wire types for the store-scoped dashboard surfaces backed by the
// new `/stores/{store_id}/...` endpoints (kpis, alerts, summary,
// activity, per-section summaries). Field names mirror the Pydantic
// schemas in `backend/app/schemas/store_dashboard.py` 1:1.

import type { OrderStatus } from "@/features/orders/types";

export type StoreOrdersByStatus = Record<OrderStatus, number>;

export interface StoreDashboardKpis {
  orders_open: number;
  orders_by_status: StoreOrdersByStatus;
  inventory_total_items: number;
  inventory_low_stock: number;
  products_in_store: number;
  products_blocked: number;
}

export type StoreAlertCategory =
  | "low_stock"
  | "aging_order"
  | "no_inventory";

export type StoreAlertSeverity = "low" | "medium" | "high";

export type StoreAlertEntityType =
  | "store"
  | "inventory_item"
  | "order";

export interface StoreAlert {
  id: string;
  category: StoreAlertCategory;
  severity: StoreAlertSeverity;
  store_id: string;
  entity_type: StoreAlertEntityType;
  entity_id: string;
  summary: string;
  created_at: string;
}

export interface StoreAlertsListResponse {
  items: StoreAlert[];
  total: number;
  limit: number;
  offset: number;
}
