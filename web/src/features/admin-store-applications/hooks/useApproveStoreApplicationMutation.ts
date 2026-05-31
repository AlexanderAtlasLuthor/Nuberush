// F2.24.C7: approve store-application mutation hook.
//
// Wraps `approveStoreApplication`. On success, seeds the detail cache
// with the review response (so the page reflects the approved status and
// provisioned ids immediately) and invalidates every list page so the
// row's status updates. The component owns the confirm UX; this hook
// owns cache coherence.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { UseMutationResult } from "@tanstack/react-query";

import { approveStoreApplication } from "../api";
import type { ApproveStoreApplicationParams } from "../api";
import { adminStoreApplicationsKeys } from "./queryKeys";
import type { StoreApplicationReviewResponse } from "../types";

export function useApproveStoreApplicationMutation(): UseMutationResult<
  StoreApplicationReviewResponse,
  unknown,
  ApproveStoreApplicationParams
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: ApproveStoreApplicationParams) =>
      approveStoreApplication(params),
    onSuccess: (result, variables) => {
      queryClient.invalidateQueries({
        queryKey: adminStoreApplicationsKeys.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: adminStoreApplicationsKeys.detail(variables.applicationId),
      });
      void result;
    },
  });
}
