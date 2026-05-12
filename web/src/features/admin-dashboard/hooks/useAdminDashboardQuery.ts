// F2.19.3: admin dashboard read hook.
//
// Cache key: ["admin-dashboard", "summary"] — see queryKeys.ts.
// Read-only: the summary is built by the backend aggregator on every
// call from existing tables; the frontend never recomputes, never
// merges, and never invalidates per-feature. A consumer that wants
// fresh data calls `refetch()` from the returned `UseQueryResult`.
//
// Hard rules baked in (mirroring useAdminAuditQuery):
//   - No useAuth, no currentUser inspection, no role-based gating.
//     Backend authorises every read via `require_admin` and the API
//     surfaces 401/403 through the centralized `apiRequest` error
//     path.
//   - No useQueryClient — read-only hook.
//   - No optimistic update, no manual setQueryData.
//   - No transformation: `AdminDashboardSummary` is returned exactly
//     as the backend produced it. No client-side KPI computation,
//     no histogram densification, no relabelling.
//   - No fallback / placeholder / initial data — if the backend is
//     unreachable the consumer sees the error, not invented numbers.
//
// No store context is required. Unlike `@/features/dashboard`'s
// per-store hook, the admin dashboard has no path UUID and no
// per-store scoping — the endpoint is global / admin-only, and the
// hook is always enabled.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getAdminDashboard } from "../api";
import type { AdminDashboardSummary } from "../types";
import { adminDashboardKeys } from "./queryKeys";

export function useAdminDashboardQuery(): UseQueryResult<AdminDashboardSummary> {
  return useQuery({
    queryKey: adminDashboardKeys.summary(),
    queryFn: ({ signal }) => getAdminDashboard(signal),
  });
}
