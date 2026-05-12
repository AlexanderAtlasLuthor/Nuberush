// F2.18.2A: create-store mutation (admin-only).
//
// Cache invalidation contract:
//
//   adminStoresKeys.lists() — a fresh store joins every active list
//                             slice; refetching pulls the canonical
//                             row from the backend.
//
// Deliberate non-decisions:
//   - No optimistic update. The server generates the UUID and
//     `created_at` / `updated_at`; we have nothing useful to seed
//     before the response.
//   - No setQueryData on detail keys. There is no detail query to
//     splice into for a brand-new row.
//   - No frontend permission logic. Backend `require_admin` is the
//     source of truth and surfaces 403 on violation.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { createStore, type CreateStoreParams } from "../api";
import type { StoreProfile } from "../types";
import { adminStoresKeys } from "./queryKeys";

export function useCreateStoreMutation() {
  const queryClient = useQueryClient();

  return useMutation<StoreProfile, Error, CreateStoreParams>({
    mutationFn: (vars) => createStore(vars),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: adminStoresKeys.lists(),
      });
    },
  });
}
