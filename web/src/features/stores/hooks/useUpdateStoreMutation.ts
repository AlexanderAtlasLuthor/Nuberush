// F2.18.2A: update-store mutation (admin context).
//
// Same wire call as `features/store/hooks/useUpdateStoreMutation`
// (`PATCH /stores/{storeId}`), but the admin variant takes the
// `storeId` per-mutate (not at hook construction) so admin pages can
// reuse one hook across rows, and invalidates the admin cache
// namespace.
//
// Cache invalidation contract:
//   1. adminStoresKeys.lists()                  list rows show name +
//                                               timezone; the body may
//                                               have changed them.
//   2. adminStoresKeys.detail(variables.storeId) detail view refresh.
//
// Deliberate non-decisions:
//   - No cross-feature invalidation of `storeKeys.detail(storeId)`
//     from `@/features/store/hooks`. The two cache namespaces are
//     intentionally disjoint (see queryKeys.ts header). Own-store
//     settings refetches when its own store-bound query refetches.
//   - No optimistic update. A 422 (extra field, validation) or 403
//     is a real possibility; we wait for the server response.
//   - No frontend permission logic. Backend `require_owner_or_admin`
//     is authoritative.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateStore } from "../api";
import type { StoreProfile, StoreUpdateRequest } from "../types";
import { adminStoresKeys } from "./queryKeys";

export interface UpdateAdminStoreVariables {
  /** Store UUID. */
  storeId: string;
  /** Partial profile update. Backend rejects extra keys with 422. */
  body: StoreUpdateRequest;
}

export function useUpdateStoreMutation() {
  const queryClient = useQueryClient();

  return useMutation<StoreProfile, Error, UpdateAdminStoreVariables>({
    mutationFn: (vars) => updateStore(vars.storeId, vars.body),
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
