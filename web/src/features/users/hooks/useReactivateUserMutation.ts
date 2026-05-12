// F2.15.4: reactivate-user mutation.
//
// Cache invalidation contract: lists() (`is_active` filter changes
// row visibility) and the target user's detail key.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { reactivateUser, type ReactivateUserParams } from "../api";
import type { UserRead } from "../types";
import { usersQueryKeys } from "./queryKeys";

export function useReactivateUserMutation() {
  const queryClient = useQueryClient();

  return useMutation<UserRead, Error, ReactivateUserParams>({
    mutationFn: (vars) => reactivateUser(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: usersQueryKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: usersQueryKeys.detail(variables.userId),
      });
    },
  });
}
