// F2.18.2B: admin global audit feed read hook.
//
// Cache key: ["audit", "admin-feed", filters] — see queryKeys.ts.
// Read-only: the feed is built by the backend aggregator from
// append-only log rows; the frontend never merges, sorts, or
// invalidates per-feature. A consumer that wants fresh data calls
// `refetch()` from the returned `UseQueryResult`.
//
// Hard rules baked in (mirroring useStoreAuditQuery):
//   - No useAuth, no currentUser inspection, no role-based gating.
//     Backend authorises every read via `require_admin` and the API
//     surfaces 401/403/404 through the centralized `apiRequest`
//     error path.
//   - No useQueryClient — read-only hook.
//   - No optimistic update, no manual setQueryData.
//   - No transformation: `AuditListResponse` is returned exactly as
//     the backend produced it. No client-side sort, no relabelling,
//     no merging with other audit hooks.
//   - No fallback to the store-scoped feed when the admin feed errors.
//
// No store context is required. Unlike `useStoreAuditQuery`, this
// hook is always enabled — the admin feed has no path UUID, and
// `store_id` (when set) lives inside the filters object as an
// OPTIONAL scope filter.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { getAdminAudit } from "../api";
import type { AdminAuditFilters, AuditListResponse } from "../types";
import { auditKeys } from "./queryKeys";

export function useAdminAuditQuery(
  filters: AdminAuditFilters = {},
): UseQueryResult<AuditListResponse> {
  return useQuery({
    queryKey: auditKeys.adminFeed(filters),
    queryFn: ({ signal }) => getAdminAudit(filters, signal),
  });
}
