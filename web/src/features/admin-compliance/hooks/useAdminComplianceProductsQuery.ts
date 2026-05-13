// F2.20.4: admin-compliance products queue read hook.
//
// Backs the future `/app/admin/compliance` queue surface (F2.20.6).
// Stays a pure read hook over `GET /admin/compliance/products`:
//
//   - Calls `getAdminComplianceProducts(filters, signal)` from the
//     api layer.
//   - Mounts the result under
//     `adminComplianceQueryKeys.productsList(filters)` so any future
//     compliance-state invalidation hits the right cache slot.
//   - Always `enabled`. Admin gating is enforced by the backend; the
//     hook never inspects auth / role on the client side.
//
// Default queue rule (F2.20.0 §7) is enforced server-side: when
// neither `compliance_status` nor `allowed_for_sale` is provided, the
// backend restricts the result to products matching the shared
// blocker predicate. The hook is filter-transparent — it never
// synthesises queue rows or applies its own predicate.
//
// Hard rules baked in (F2.20.4):
//   - No useAuth.
//   - No useStoreContext.
//   - No client-side role gating.
//   - No fake / placeholder rows.
//   - No client-side queue generation.
//   - Read-only.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getAdminComplianceProducts } from "../api";
import type {
  AdminComplianceProductsFilters,
  AdminComplianceProductsListResponse,
} from "../types";
import { adminComplianceQueryKeys } from "./queryKeys";

export function useAdminComplianceProductsQuery(
  filters?: AdminComplianceProductsFilters,
): UseQueryResult<AdminComplianceProductsListResponse> {
  return useQuery({
    queryKey: adminComplianceQueryKeys.productsList(filters),
    queryFn: ({ signal }) => getAdminComplianceProducts(filters, signal),
  });
}
