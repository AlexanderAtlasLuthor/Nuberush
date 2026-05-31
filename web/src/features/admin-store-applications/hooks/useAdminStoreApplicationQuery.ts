// F2.24.C7: admin store-application detail query hook.
//
// Thin wrapper over `getStoreApplication`. Disabled until an
// applicationId is present so a missing/empty route param never fires a
// request against `/admin/store-applications/undefined`.

import { useQuery } from "@tanstack/react-query";
import type { UseQueryResult } from "@tanstack/react-query";

import { getStoreApplication } from "../api";
import { adminStoreApplicationsKeys } from "./queryKeys";
import type { StoreApplicationDetail } from "../types";

export function useAdminStoreApplicationQuery(
  applicationId: string | undefined,
): UseQueryResult<StoreApplicationDetail> {
  return useQuery({
    queryKey: adminStoreApplicationsKeys.detail(applicationId ?? ""),
    queryFn: ({ signal }) => getStoreApplication(applicationId as string, signal),
    enabled: Boolean(applicationId),
  });
}
