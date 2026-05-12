// F2.15.4: assign-store mutation.
//
// Cache invalidation contract: lists() (`store_id` filter changes
// row visibility for owners/managers) and the target user's detail
// key.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { assignUserStore, type AssignUserStoreParams } from "../api";
import type { UserRead } from "../types";
import { usersQueryKeys } from "./queryKeys";

export function useAssignUserStoreMutation() {
  const queryClient = useQueryClient();

  return useMutation<UserRead, Error, AssignUserStoreParams>({
    mutationFn: (vars) => assignUserStore(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: usersQueryKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: usersQueryKeys.detail(variables.userId),
      });
    },
  });
}
