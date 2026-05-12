// F2.15.4: admin-set-password mutation.
//
// The wire and cache contract is intentionally minimal: the server
// returns a UserRead (without password_hash), and we invalidate the
// user's detail/list keys for the same reason every other mutation
// does — `updated_at` and any auditable side-effect should refetch.
// We do NOT seed cache with the response because the new password is
// not part of UserRead.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  adminSetUserPassword,
  type AdminSetUserPasswordParams,
} from "../api";
import type { UserRead } from "../types";
import { usersQueryKeys } from "./queryKeys";

export function useAdminSetPasswordMutation() {
  const queryClient = useQueryClient();

  return useMutation<UserRead, Error, AdminSetUserPasswordParams>({
    mutationFn: (vars) => adminSetUserPassword(vars),
    onSuccess: (_data, variables) => {
      queryClient.invalidateQueries({ queryKey: usersQueryKeys.lists() });
      queryClient.invalidateQueries({
        queryKey: usersQueryKeys.detail(variables.userId),
      });
    },
  });
}
