// F2.18.2A: reactivate-store mutation (admin-only; NOT idempotent).
//
// Cache invalidation contract: lists() and the target store's
// detail key (same as deactivate, for the same reason).
//
// The backend is NOT idempotent — reactivating an already-active
// store surfaces as 422.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { reactivateStore, type ReactivateStoreParams } from "../api";
import type { StoreProfile } from "../types";
import { adminStoresKeys } from "./queryKeys";

export function useReactivateStoreMutation() {
  const queryClient = useQueryClient();

  return useMutation<StoreProfile, Error, ReactivateStoreParams>({
    mutationFn: (vars) => reactivateStore(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({
        queryKey: adminStoresKeys.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: adminStoresKeys.detail(variables.storeId),
      });
    },
  });
}
