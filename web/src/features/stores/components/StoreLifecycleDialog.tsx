// F2.18.3: Deactivate / Reactivate store confirmation dialog.
//
// One dialog, two transitions — copy and the mutation it fires switch
// on `store.is_active`. The backend is the source of truth for who
// can call deactivate/reactivate and whether the call is a no-op
// (already-inactive/active → 422). The dialog only collects intent.
//
// Pattern matches features/users/components/DeactivateUserDialog.tsx:
//   - useEffect-based auto-close on mutation.isSuccess.
//   - inline error via getApiErrorMessage.
//   - submit disabled while pending.
//   - destructive styling only for the deactivate flow.

import { useEffect } from "react";

import { getApiErrorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

import {
  useDeactivateStoreMutation,
  useReactivateStoreMutation,
} from "../hooks";
import type { StoreProfile } from "../types";

export interface StoreLifecycleDialogProps {
  store: StoreProfile | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (store: StoreProfile) => void;
}

export function StoreLifecycleDialog({
  store,
  open,
  onOpenChange,
  onSuccess,
}: StoreLifecycleDialogProps) {
  // Both mutations are always mounted but only one fires per click.
  // Each invalidates `adminStoresKeys.lists()` and the target
  // `adminStoresKeys.detail(storeId)` per the F2.18.2A contract, so
  // the parent does not need to refetch by hand.
  const deactivate = useDeactivateStoreMutation();
  const reactivate = useReactivateStoreMutation();

  const isActive = store?.is_active ?? false;
  const active = isActive ? deactivate : reactivate;

  useEffect(() => {
    if (active.isSuccess && active.data && open) {
      onSuccess?.(active.data);
      onOpenChange(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active.isSuccess, active.data]);

  // Reset stale error / success state when the dialog reopens for a
  // different row.
  useEffect(() => {
    if (open) {
      deactivate.reset();
      reactivate.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, store?.id]);

  const handleConfirm = () => {
    if (active.isPending || store === null) return;
    active.mutate({ storeId: store.id });
  };

  const title = isActive ? "Deactivate store" : "Reactivate store";
  const description = isActive
    ? "The store keeps its history but stops accepting operational requests until reactivated."
    : "The store returns to active service. Confirm operational readiness before continuing.";
  const confirmLabel = isActive ? "Deactivate" : "Reactivate";
  const pendingLabel = isActive ? "Deactivating…" : "Reactivating…";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-md"
        data-testid="store-lifecycle-dialog"
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        {store === null ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="store-lifecycle-no-target"
          >
            No store selected.
          </p>
        ) : (
          <div className="space-y-1 text-sm">
            <p>
              <span className="text-muted-foreground">Name:</span>{" "}
              <span
                className="font-medium"
                data-testid="store-lifecycle-name"
              >
                {store.name}
              </span>
            </p>
            <p>
              <span className="text-muted-foreground">Code:</span>{" "}
              <span
                className="font-mono text-xs"
                data-testid="store-lifecycle-code"
              >
                {store.code}
              </span>
            </p>
          </div>
        )}

        {active.isError ? (
          <p
            role="alert"
            aria-live="polite"
            className="text-sm text-destructive"
            data-testid="store-lifecycle-error"
          >
            {getApiErrorMessage(active.error)}
          </p>
        ) : null}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={active.isPending}
            data-testid="store-lifecycle-cancel"
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant={isActive ? "destructive" : "default"}
            onClick={handleConfirm}
            disabled={store === null || active.isPending}
            data-testid="store-lifecycle-confirm"
          >
            {active.isPending ? pendingLabel : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
