// F2.15.4: single-user detail hook.
//
// `enabled` is gated on a truthy userId so callers can pass the
// selected row id directly — no `skip` ceremony, no extra branching.
// Cache key: ["users", "detail", userId] — see queryKeys.ts.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getUser } from "../api";
import type { UserRead } from "../types";
import { usersQueryKeys } from "./queryKeys";

export function useUserQuery(
  userId?: string,
): UseQueryResult<UserRead> {
  return useQuery({
    queryKey: usersQueryKeys.detail(userId ?? ""),
    queryFn: ({ signal }) =>
      getUser({ userId: userId as string }, signal),
    enabled: Boolean(userId),
  });
}
