// F2.15.4: update-user mutation (full_name / phone).
//
// Cache invalidation contract:
//   1. usersQueryKeys.lists()                    list rows show
//                                                full_name; the body
//                                                may have changed it.
//   2. usersQueryKeys.detail(variables.userId)   detail view refresh.
//
// Deliberate non-invalidations: dashboard, products, inventory,
// orders, audit, settings, and store caches are unaffected by a
// user-profile change. Invalidating them would be busywork.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { updateUser, type UpdateUserParams } from "../api";
import type { UserRead } from "../types";
import { usersQueryKeys } from "./queryKeys";

export function useUpdateUserMutation() {
  const queryClient = useQueryClient();

  return useMutation<UserRead, Error, UpdateUserParams>({
    mutationFn: (vars) => updateUser(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: usersQueryKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: usersQueryKeys.detail(variables.userId),
      });
    },
  });
}
