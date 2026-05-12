// F2.15.4: change-role mutation.
//
// Cache invalidation contract: lists() (`role` filter and rendered
// chips both change) and the target user's detail key.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { changeUserRole, type ChangeUserRoleParams } from "../api";
import type { UserRead } from "../types";
import { usersQueryKeys } from "./queryKeys";

export function useChangeUserRoleMutation() {
  const queryClient = useQueryClient();

  return useMutation<UserRead, Error, ChangeUserRoleParams>({
    mutationFn: (vars) => changeUserRole(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: usersQueryKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: usersQueryKeys.detail(variables.userId),
      });
    },
  });
}
