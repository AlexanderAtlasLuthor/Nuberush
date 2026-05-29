// F2.22.5.D: barrel for the realtime subscription module.
//
// Public surface: the two table-bound subscription hooks. Internal
// primitives (e.g. `useTableRealtimeSubscription`) stay under
// `./internal/*` and are not re-exported.

export { useOrdersRealtimeSubscription } from "./useOrdersRealtimeSubscription";
export type { UseOrdersRealtimeSubscriptionOptions } from "./useOrdersRealtimeSubscription";

export { useInventoryRealtimeSubscription } from "./useInventoryRealtimeSubscription";
export type { UseInventoryRealtimeSubscriptionOptions } from "./useInventoryRealtimeSubscription";

export { RealtimeInvalidationBridge } from "./RealtimeInvalidationBridge";
