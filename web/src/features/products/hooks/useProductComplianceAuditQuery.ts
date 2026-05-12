// F2.8.2: compliance audit log hook.
//
// Cache key: ["products", "complianceAudit", productId] — see
// queryKeys.ts. The compliance-update mutation invalidates this key so
// the audit panel refreshes immediately after the row that produced it.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";
import { getProductComplianceAudit } from "../api";
import type { ProductComplianceAuditLog } from "../types";
import { productsKeys } from "./queryKeys";

export function useProductComplianceAuditQuery(
  productId: string,
): UseQueryResult<ProductComplianceAuditLog[]> {
  return useQuery({
    queryKey: productsKeys.complianceAudit(productId),
    queryFn: ({ signal }) =>
      getProductComplianceAudit({ productId }, signal),
    enabled: productId.length > 0,
  });
}
