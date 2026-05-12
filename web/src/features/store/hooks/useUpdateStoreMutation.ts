// F2.14.4: update-store mutation.
//
// Bound to a specific `storeId` at construction (the F2.14 settings
// surface is single-store). The mutate variables are the
// `StoreUpdateRequest` body verbatim, so callers can do:
//
//   const m = useUpdateStoreMutation(storeId);
//   m.mutate({ name, timezone });
//
// Cache invalidation contract:
//
//   storeKeys.detail(storeId) — the `useStoreQuery(storeId)` cache slot
//   that read this profile. Refetching pulls the server-fresh
//   `updated_at` and reflects any field the server normalised (e.g.
//   trimmed name).
//
// Deliberate non-decisions:
//   - No invalidation of dashboard / products / inventory / orders
//     keys. Updating `name` / `timezone` does not affect those caches.
//   - No optimistic update. A 422 (extra field, validation) or 403 is
//     a real possibility for any payload, so we wait for the server
//     response before mutating local cache state.
//   - No setQueryData in onSuccess. invalidate triggers a refetch that
//     produces a single canonical state; setQueryData would race the
//     refetch and risk stale data on later mounts.
//   - No frontend permission logic. The backend
//     `require_owner_or_admin` is the source of truth; managers /
//     staff / drivers get 403 and the UI surfaces the server detail.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateStore } from "../api";
import type { StoreProfile, StoreUpdateRequest } from "../types";
import { storeKeys } from "./queryKeys";

export function useUpdateStoreMutation(storeId: string) {
  const queryClient = useQueryClient();

  return useMutation<StoreProfile, Error, StoreUpdateRequest>({
    mutationFn: (payload) => updateStore(storeId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: storeKeys.detail(storeId),
      });
    },
  });
}
