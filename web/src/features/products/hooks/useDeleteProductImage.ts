// F2.26.3.C: clear-primary-image mutation.
//
// Wraps the F2.26.3.A backend endpoint `DELETE /products/{id}/images`
// (admin-only). The backend returns the updated `Product` with
// `primary_image === null`; this hook returns it so the caller can read
// the cleared state if needed.
//
// Cache invalidation mirrors `useProductImageUpload` exactly so every
// list/detail surface showing this product re-fetches the now-null
// `primary_image` through FastAPI — keeping the admin panel, the admin
// list thumbnail and the store list/detail thumbnail consistent.

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { adminProductsQueryKeys } from "@/features/admin-products/hooks";

import { deleteProductImage } from "../storage";
import type { Product } from "../types";
import { productsKeys } from "./queryKeys";

export function useDeleteProductImage(productId: string) {
  const queryClient = useQueryClient();

  return useMutation<Product, Error, void>({
    mutationFn: () => deleteProductImage({ productId }),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: productsKeys.detail(productId),
      });
      queryClient.invalidateQueries({
        queryKey: productsKeys.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: adminProductsQueryKeys.lists(),
      });
    },
  });
}
