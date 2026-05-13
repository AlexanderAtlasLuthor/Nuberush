// F2.20.4: admin-compliance summary read hook.
//
// Backs the future `/app/admin/compliance` overview surface (F2.20.6).
// Stays a pure read hook over `GET /admin/compliance`:
//
//   - Calls `getAdminComplianceSummary(signal)` from the api layer.
//   - Mounts the result under `adminComplianceQueryKeys.summary()`
//     so any future invalidation (e.g. after a compliance change)
//     hits the right cache slot.
//   - Always `enabled`. Admin gating is enforced by the backend; the
//     hook never inspects auth / role on the client side. A non-admin
//     caller will receive ApiError(403) from the server and the hook
//     surfaces that via `result.error` exactly like any other read
//     hook.
//
// Hard rules baked in (F2.20.4):
//   - No useAuth.
//   - No useStoreContext.
//   - No client-side role gating.
//   - No fake / placeholder KPI values.
//   - No client-side summary derivation. The backend is the source
//     of truth for every count.
//   - Read-only.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getAdminComplianceSummary } from "../api";
import type { AdminComplianceSummary } from "../types";
import { adminComplianceQueryKeys } from "./queryKeys";

export function useAdminComplianceSummaryQuery(): UseQueryResult<AdminComplianceSummary> {
  return useQuery({
    queryKey: adminComplianceQueryKeys.summary(),
    queryFn: ({ signal }) => getAdminComplianceSummary(signal),
  });
}
