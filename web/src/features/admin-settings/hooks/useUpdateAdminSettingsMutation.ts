// Admin settings update mutation hook (F2.27.10).
//
// Backs the editable form on `/app/admin/settings`. TanStack mutation over
// `PATCH /admin/settings`:
//   - Calls `patchAdminSettings(payload)` from the api layer.
//   - On success invalidates `adminSettingsKeys.snapshot()` so the read query
//     refetches the persisted values (the PATCH response already carries the
//     fresh snapshot, but invalidation keeps every cached reader consistent).
//   - Surfaces error to the caller via `mutation.error` / `isError`.
//
// Hard rules baked in (mirroring the read hook):
//   - No useAuth, no useStoreContext, no role-based gating. Admin gating is
//     enforced by the backend; a non-admin caller receives ApiError(403).
//   - No store_id, no tenancy.
//   - No optimistic update, no manual setQueryData.

import {
  useMutation,
  useQueryClient,
  type UseMutationResult,
} from "@tanstack/react-query";

import { patchAdminSettings } from "../api";
import type {
  AdminSettingsResponse,
  AdminSettingsUpdateRequest,
} from "../types";
import { adminSettingsKeys } from "./queryKeys";

export function useUpdateAdminSettingsMutation(): UseMutationResult<
  AdminSettingsResponse,
  unknown,
  AdminSettingsUpdateRequest
> {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: AdminSettingsUpdateRequest) =>
      patchAdminSettings(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: adminSettingsKeys.snapshot(),
      });
    },
  });
}
