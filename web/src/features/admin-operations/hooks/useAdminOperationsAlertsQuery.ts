// F2.19.4: admin operations alerts read hook.
//
// Cache key: ["admin-operations", "alerts", "list", filters] —
// see queryKeys.ts. Read-only: the feed is built by the backend
// alert generators on every call; the frontend never synthesises
// alerts, never re-sorts them, and never invalidates per-feature.
// A consumer that wants fresh data calls `refetch()` from the
// returned `UseQueryResult`.
//
// Hard rules baked in (mirroring useAdminDashboardQuery,
// useAdminAuditQuery):
//   - No useAuth, no currentUser inspection, no role-based gating.
//     Backend authorises every read via `require_admin` and the API
//     surfaces 401/403 through the centralized `apiRequest` error
//     path.
//   - No useQueryClient — read-only hook.
//   - No optimistic update, no manual setQueryData.
//   - No transformation: `AdminOperationsAlertsListResponse` is
//     returned exactly as the backend produced it. No client-side
//     alert generation, no severity recomputation, no relabelling.
//   - No fallback / placeholder / initial data — if the backend is
//     unreachable the consumer sees the error, not invented alerts.
//   - No acknowledge / dismiss / resolve mutation surface — those
//     are non-goals of F2.19 (the contract forbids alert mutations).
//
// No store context is required. Filters (including `store_id`) live
// inside the filters object; the hook has no `storeId` argument.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getAdminOperationsAlerts } from "../api";
import type {
  AdminOperationsAlertsFilters,
  AdminOperationsAlertsListResponse,
} from "../types";
import { adminOperationsKeys } from "./queryKeys";

export function useAdminOperationsAlertsQuery(
  filters: AdminOperationsAlertsFilters = {},
): UseQueryResult<AdminOperationsAlertsListResponse> {
  return useQuery({
    queryKey: adminOperationsKeys.alertList(filters),
    queryFn: ({ signal }) => getAdminOperationsAlerts(filters, signal),
  });
}
