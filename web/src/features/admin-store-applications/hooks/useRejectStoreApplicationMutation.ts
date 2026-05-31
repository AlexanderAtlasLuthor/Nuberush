// F2.24.C7: reject store-application mutation hook.
//
// Wraps `rejectStoreApplication`. On success, invalidates the affected
// application's detail and every list page so the UI reflects the
// rejected status and reason without a manual refetch.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { UseMutationResult } from "@tanstack/react-query";

import { rejectStoreApplication } from "../api";
import type { RejectStoreApplicationParams } from "../api";
import { adminStoreApplicationsKeys } from "./queryKeys";
import type { StoreApplicationReviewResponse } from "../types";

export function useRejectStoreApplicationMutation(): UseMutationResult<
  StoreApplicationReviewResponse,
  unknown,
  RejectStoreApplicationParams
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: RejectStoreApplicationParams) =>
      rejectStoreApplication(params),
    onSuccess: (_result, variables) => {
      queryClient.invalidateQueries({
        queryKey: adminStoreApplicationsKeys.lists(),
      });
      queryClient.invalidateQueries({
        queryKey: adminStoreApplicationsKeys.detail(variables.applicationId),
      });
    },
  });
}
