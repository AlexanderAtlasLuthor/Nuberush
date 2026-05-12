// F2.15.4: deactivate-user mutation.
//
// Cache invalidation contract: lists() (`is_active` filter changes
// row visibility) and the target user's detail key.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { deactivateUser, type DeactivateUserParams } from "../api";
import type { UserRead } from "../types";
import { usersQueryKeys } from "./queryKeys";

export function useDeactivateUserMutation() {
  const queryClient = useQueryClient();

  return useMutation<UserRead, Error, DeactivateUserParams>({
    mutationFn: (vars) => deactivateUser(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: usersQueryKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: usersQueryKeys.detail(variables.userId),
      });
    },
  });
}
