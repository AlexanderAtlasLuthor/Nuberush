// F2.27.8: inventory import — confirm mutation.
//
// Applies the import server-side in one all-or-nothing transaction.
// Variables match the api-layer params shape:
//
//   const m = useInventoryImportConfirmMutation();
//   m.mutate({ storeId, file });
//
// On success we invalidate every paginated inventory list (the same
// `["inventory","list"]` prefix the movement mutations use): an import
// can change on-hand quantities, low-stock membership and pagination
// totals across the store, so any cached list view is stale. We don't
// touch item-detail keys — the import does not target a single known
// item id.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { confirmInventoryImport } from "../api";
import type { InventoryImportParams } from "../api";
import type { InventoryImportConfirmResponse } from "../types";
import { inventoryKeys } from "./queryKeys";

export function useInventoryImportConfirmMutation() {
  const queryClient = useQueryClient();

  return useMutation<
    InventoryImportConfirmResponse,
    Error,
    InventoryImportParams
  >({
    mutationFn: (vars) => confirmInventoryImport(vars),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: inventoryKeys.lists() });
    },
  });
}
