// F2.9.2: create-user mutation.
//
// Mutation variables match the api-layer params shape exactly so the
// mutationFn is a pass-through. Callers invoke as:
//
//   const m = useCreateUserMutation();
//   m.mutate({ body: { full_name, email, password, role, store_id? } });
//
// Cache invalidation contract:
//
//   None. The users feature has NO list/detail queries — the backend
//   does not expose GET /auth/users or GET /auth/users/{id} (verified
//   in F2.9.0 backend contract report). Inventing invalidations for
//   non-existent caches would either silently no-op (best case) or
//   push future contributors to add phantom queries to "match" the
//   invalidations (worst case). When the backend grows a list endpoint
//   and a `useUsersQuery` lands here, that's the moment to add an
//   `onSuccess: invalidateQueries({ queryKey: usersQueryKeys.lists() })`.
//   Not before.
//
// Other deliberate non-decisions:
//   - No optimistic update. UserRead.id is server-generated; we have
//     nothing useful to seed before the response.
//   - No setQueryData. There is no list to splice into.
//   - No onSuccess / onError baked in. UI components own those: the
//     CreateUserForm shows toasts / closes a modal in onSuccess and
//     surfaces backend ApiError messages in onError.
//   - No transformation of backend errors. ApiError already carries
//     status + detail; the UI inspects it directly.
//   - No frontend permission logic, no role matrix, no
//     currentUser.role inspection. The backend
//     `require_manager_or_above` + `USER_CREATION_MATRIX` is the
//     single source of truth and surfaces 403 on violation. The hook
//     is permission-blind on purpose.

import { useMutation } from "@tanstack/react-query";
import { createUser } from "../api";
import type { CreateUserParams } from "../api";
import type { UserRead } from "../types";

export function useCreateUserMutation() {
  return useMutation<UserRead, Error, CreateUserParams>({
    mutationFn: (vars) => createUser(vars),
  });
}
