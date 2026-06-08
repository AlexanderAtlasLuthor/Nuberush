// F2.27.8: inventory import — preview mutation.
//
// Preview is a read-only server operation (no DB writes), but it is
// modeled as a mutation rather than a query because it is imperative
// (fires on a user-selected file, not on key changes) and takes a
// non-serializable `File` as input. Variables match the api-layer
// params shape so the mutationFn is a pass-through:
//
//   const m = useInventoryImportPreviewMutation();
//   m.mutate({ storeId, file });
//
// No cache invalidation here — preview changes nothing server-side.

import { useMutation } from "@tanstack/react-query";
import { previewInventoryImport } from "../api";
import type { InventoryImportParams } from "../api";
import type { InventoryImportPreviewResponse } from "../types";

export function useInventoryImportPreviewMutation() {
  return useMutation<
    InventoryImportPreviewResponse,
    Error,
    InventoryImportParams
  >({
    mutationFn: (vars) => previewInventoryImport(vars),
  });
}
