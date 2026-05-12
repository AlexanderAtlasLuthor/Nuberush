// F2.8.2: barrel for products hooks.
//
// Feature pages should import from `@/features/products/hooks` rather
// than reaching into individual files; that keeps the public surface
// in one place and lets internals change without ripple edits.

export { useProductsQuery } from "./useProductsQuery";
export { useProductQuery } from "./useProductQuery";
export { useProductVariantsQuery } from "./useProductVariantsQuery";
export { useProductSellableQuery } from "./useProductSellableQuery";
export { useProductComplianceAuditQuery } from "./useProductComplianceAuditQuery";

export { useCreateProductMutation } from "./useCreateProductMutation";
export { useUpdateProductMutation } from "./useUpdateProductMutation";
export { useDeleteProductMutation } from "./useDeleteProductMutation";
export {
  useCreateVariantMutation,
  type CreateVariantMutationVariables,
} from "./useCreateVariantMutation";
export { useUpdateVariantMutation } from "./useUpdateVariantMutation";
export {
  useDeleteVariantMutation,
  type DeleteVariantMutationVariables,
} from "./useDeleteVariantMutation";
export { useUpdateComplianceMutation } from "./useUpdateComplianceMutation";

export {
  productsKeys,
  type ProductsListQueryFilters,
  type ProductVariantsQueryParams,
} from "./queryKeys";
