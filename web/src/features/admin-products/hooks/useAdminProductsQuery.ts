// F2.20.3: paginated/filterable admin-products list hook.
//
// Backs the future `/app/admin/products` surface (F2.20.5). Stays a
// pure read hook over `GET /admin/products`:
//
//   - Calls `getAdminProducts(filters, signal)` from the api layer.
//   - Mounts the result under
//     `adminProductsQueryKeys.list(filters)` so any future
//     invalidation (e.g. after a compliance change in F2.20.6) hits
//     the right cache slot.
//   - Always `enabled`. Admin gating is enforced by the backend; the
//     hook never inspects auth / role on the client side. A non-admin
//     caller will receive ApiError(403) from the server and the
//     hook surfaces that via `result.error` exactly like any other
//     read hook.
//
// Hard rules baked in (F2.20.3):
//   - No useAuth.
//   - No useStoreContext.
//   - No client-side role gating.
//   - No fake / placeholder rows.
//   - Read-only.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getAdminProducts } from "../api";
import type {
  AdminProductsFilters,
  AdminProductsListResponse,
} from "../types";
import { adminProductsQueryKeys } from "./queryKeys";

export function useAdminProductsQuery(
  filters?: AdminProductsFilters,
): UseQueryResult<AdminProductsListResponse> {
  return useQuery({
    queryKey: adminProductsQueryKeys.list(filters),
    queryFn: ({ signal }) => getAdminProducts(filters, signal),
  });
}
