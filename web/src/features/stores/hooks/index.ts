// F2.18.2A: barrel for the admin stores hooks.
//
// Feature pages should import from `@/features/stores/hooks` rather
// than reaching into individual files; that keeps the public surface
// in one place and lets internals change without ripple edits.

export { adminStoresKeys } from "./queryKeys";

// Queries
export { useAdminStoresQuery } from "./useAdminStoresQuery";
export { useAdminStoreQuery } from "./useAdminStoreQuery";

// Mutations
export { useCreateStoreMutation } from "./useCreateStoreMutation";
export {
  useUpdateStoreMutation,
  type UpdateAdminStoreVariables,
} from "./useUpdateStoreMutation";
export { useDeactivateStoreMutation } from "./useDeactivateStoreMutation";
export { useReactivateStoreMutation } from "./useReactivateStoreMutation";
