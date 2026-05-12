// F2.15.6: Deactivate / Reactivate user confirmation dialog.
//
// One dialog, two transitions — copy and the mutation it fires
// switch on `user.is_active`. The backend enforces the matrix
// (manager cannot deactivate owner / admin, last-active-admin guard,
// self-target guard, etc.) and surfaces the right status code; this
// dialog only collects intent.
//
// Pattern matches features/products/components/DeactivateProductDialog.tsx:
//   - useEffect-based auto-close on mutation.isSuccess.
//   - inline error via getApiErrorMessage.
//   - submit disabled while pending.
//   - destructive styling only for the deactivate flow; the
//     reactivate flow uses default (non-destructive) styling because
//     reversing a deactivation is not the irreversible action.

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
  useDeactivateUserMutation,
  useReactivateUserMutation,
} from "../hooks";
import type { UserRead } from "../types";

export interface DeactivateUserDialogProps {
  user: UserRead | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (user: UserRead) => void;
}

export function DeactivateUserDialog({
  user,
  open,
  onOpenChange,
  onSuccess,
}: DeactivateUserDialogProps) {
  // Both mutations are always mounted but only one fires per click.
  // Each invalidates `usersQueryKeys.lists()` + `detail(userId)` per
  // F2.15.4 contract, so the parent never needs to refetch by hand.
  const deactivate = useDeactivateUserMutation();
  const reactivate = useReactivateUserMutation();

  const isActive = user?.is_active ?? false;
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
  }, [open, user?.id]);

  const handleConfirm = () => {
    if (active.isPending || user === null) return;
    active.mutate({ userId: user.id });
  };

  const title = isActive ? "Deactivate user" : "Reactivate user";
  const description = isActive
    ? "The user keeps their record but cannot log in until reactivated."
    : "The user regains access. Make sure their store assignment is valid.";
  const confirmLabel = isActive ? "Deactivate" : "Reactivate";
  const pendingLabel = isActive ? "Deactivating…" : "Reactivating…";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-md"
        data-testid="deactivate-user-dialog"
      >
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        {user === null ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="deactivate-user-no-target"
          >
            No user selected.
          </p>
        ) : (
          <div className="space-y-1 text-sm">
            <p>
              <span className="text-muted-foreground">Name:</span>{" "}
              <span
                className="font-medium"
                data-testid="deactivate-user-name"
              >
                {user.full_name}
              </span>
            </p>
            <p>
              <span className="text-muted-foreground">Email:</span>{" "}
              <span
                className="font-mono text-xs"
                data-testid="deactivate-user-email"
              >
                {user.email}
              </span>
            </p>
          </div>
        )}

        {active.isError ? (
          <p
            role="alert"
            aria-live="polite"
            className="text-sm text-destructive"
            data-testid="deactivate-user-error"
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
            data-testid="deactivate-user-cancel"
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant={isActive ? "destructive" : "default"}
            onClick={handleConfirm}
            disabled={user === null || active.isPending}
            data-testid="deactivate-user-confirm"
          >
            {active.isPending ? pendingLabel : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
