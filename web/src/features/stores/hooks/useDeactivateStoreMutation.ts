// F2.18.2A: deactivate-store mutation (admin-only; NOT idempotent).
//
// Cache invalidation contract: lists() (the `is_active` filter
// changes row visibility) and the target store's detail key.
//
// The backend is NOT idempotent — deactivating an already-inactive
// store surfaces as 422. The mutation propagates that ApiError to the
// caller unchanged; UI shows the server detail.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deactivateStore, type DeactivateStoreParams } from "../api";
import type { StoreProfile } from "../types";
import { adminStoresKeys } from "./queryKeys";

export function useDeactivateStoreMutation() {
  const queryClient = useQueryClient();

  return useMutation<StoreProfile, Error, DeactivateStoreParams>({
    mutationFn: (vars) => deactivateStore(vars),
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
