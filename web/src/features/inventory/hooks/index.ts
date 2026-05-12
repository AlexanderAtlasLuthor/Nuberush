// F2.6.0 subfase 3 + F2.18.2C: barrel for inventory hooks.
//
// Feature pages should import from `@/features/inventory/hooks` rather
// than reaching into individual files; that keeps the public surface
// in one place and lets internals change without ripple edits.

export { useInventoryList } from "./useInventoryList";
export { useInventoryItem } from "./useInventoryItem";
export { useInventoryItemLogs } from "./useInventoryItemLogs";
export { useReceiveStockMutation } from "./useReceiveStockMutation";
export { useAdjustStockMutation } from "./useAdjustStockMutation";
export { useDamageStockMutation } from "./useDamageStockMutation";
export { useUpdateInventoryThresholdMutation } from "./useUpdateInventoryThresholdMutation";
export { useUpdateInventoryStatusMutation } from "./useUpdateInventoryStatusMutation";

// F2.18.2C — admin global inventory feed
export { useAdminInventoryQuery } from "./useAdminInventoryQuery";

export {
  inventoryKeys,
  type InventoryListQueryParams,
  type InventoryItemLogsQueryParams,
} from "./queryKeys";
