// F2.16.4 + F2.18.2B: barrel for audit hooks.
//
// Feature pages should import from `@/features/audit/hooks` rather
// than reaching into individual files; that keeps the public
// surface in one place and lets internals change without ripple
// edits.
//
// Surface exposes:
//   - Legacy inventory-logs (F2.10)
//   - Unified store-scoped feed (F2.16.4)
//   - Admin global feed (F2.18.2B)
//
// Future cross-resource audit hooks (events, activity, user
// activity, per-feature audit re-wrappers) belong here ONLY when
// the corresponding backend endpoints exist.

export {
  auditKeys,
  type StoreInventoryLogsQueryParams,
} from "./queryKeys";

export {
  useStoreInventoryLogsQuery,
  type UseStoreInventoryLogsQueryParams,
} from "./useStoreInventoryLogsQuery";

export { useStoreAuditQuery } from "./useStoreAuditQuery";
export { useAdminAuditQuery } from "./useAdminAuditQuery";
