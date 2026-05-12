// F2.7.0 subfase 3 + F2.18.2C: barrel for orders hooks.
//
// Feature pages should import from `@/features/orders/hooks` rather
// than reaching into individual files; that keeps the public surface
// in one place and lets internals change without ripple edits.

export { useOrdersList } from "./useOrdersList";
export { useOrder } from "./useOrder";
export { useOrderAuditLogs } from "./useOrderAuditLogs";
export { useCreateOrderMutation } from "./useCreateOrderMutation";
export { useTransitionOrderStatusMutation } from "./useTransitionOrderStatusMutation";
export { useCancelOrderMutation } from "./useCancelOrderMutation";
export { useReturnOrderMutation } from "./useReturnOrderMutation";

// F2.18.2C — admin global orders feed
export { useAdminOrdersQuery } from "./useAdminOrdersQuery";

export {
  ordersKeys,
  type OrdersListQueryParams,
} from "./queryKeys";
