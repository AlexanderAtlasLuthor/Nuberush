// F2.8.2: create-product mutation.
//
// Mutation variables match the api-layer params shape exactly so the
// mutationFn is a pass-through. Callers invoke as:
//
//   const m = useCreateProductMutation();
//   m.mutate({ body: { name, category, ... } });
//
// Cache invalidation contract (per F2.8.2 brief §5):
//
//   1. productsKeys.lists()                store-surface list queries.
//   2. productsKeys.detail(data.id)        defensive: in case a detail
//                                          page for the new id was
//                                          prefetched or speculatively
//                                          rendered.
//   3. adminProductsQueryKeys.lists()      admin-products list mounted
//                                          at /app/admin/products is a
//                                          separate cache namespace; a
//                                          new product makes both views
//                                          stale, so we invalidate both
//                                          here rather than ask every
//                                          create call site to remember.
//
// We do NOT setQueryData with the response on purpose: invalidation is
// the conservative default and matches the inventory/orders pattern.
// `data.id` is server-generated and only available from the response,
// not from variables.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { adminProductsQueryKeys } from "@/features/admin-products/hooks";
import { createProduct } from "../api";
import type { CreateProductParams } from "../api";
import type { Product } from "../types";
import { productsKeys } from "./queryKeys";

export function useCreateProductMutation() {
  const queryClient = useQueryClient();

  return useMutation<Product, Error, CreateProductParams>({
    mutationFn: (vars) => createProduct(vars),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: productsKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: productsKeys.detail(data.id),
      });
      queryClient.invalidateQueries({
        queryKey: adminProductsQueryKeys.lists(),
      });
    },
  });
}
