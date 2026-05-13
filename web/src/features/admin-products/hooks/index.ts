// F2.20.3: public barrel for the admin-products hooks namespace.
//
// Consumers should import from this barrel (`@/features/admin-products/hooks`)
// rather than reach into the individual files, so we can refactor
// internals without ripple changes.

export { adminProductsQueryKeys } from "./queryKeys";
export { useAdminProductsQuery } from "./useAdminProductsQuery";
