// Admin settings read hook.
//
// Backs `/app/admin/settings`. Pure read hook over `GET /admin/settings`:
//   - Calls `getAdminSettings(signal)` from the api layer.
//   - Mounts the result under `adminSettingsKeys.snapshot()`.
//   - Always `enabled`. Admin gating is enforced by the backend; the
//     hook never inspects auth / role on the client side. A non-admin
//     caller will receive ApiError(403) from the server and the hook
//     surfaces that via `result.error`.
//
// Hard rules baked in:
//   - No useAuth, no useStoreContext, no role-based gating.
//   - No useQueryClient — read-only hook.
//   - No transformation: the backend response is returned verbatim.
//   - No fallback / placeholder / initial data — if the backend is
//     unreachable the consumer sees the error, not invented values.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getAdminSettings } from "../api";
import type { AdminSettingsResponse } from "../types";
import { adminSettingsKeys } from "./queryKeys";

export function useAdminSettingsQuery(): UseQueryResult<AdminSettingsResponse> {
  return useQuery({
    queryKey: adminSettingsKeys.snapshot(),
    queryFn: ({ signal }) => getAdminSettings(signal),
  });
}
