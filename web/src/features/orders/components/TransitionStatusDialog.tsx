// F2.7.4 subfase 2: forward-status transition confirmation.
//
// Self-contained AlertDialog driven by `useTransitionOrderStatusMutation`
// from F2.7.0. Owns the lifecycle effects (reset on open, auto-close on
// success) and surfaces backend errors inline without closing the
// dialog. Backend invalidation contract is already wired inside the
// mutation hook (orders list + item + auditLogs + inventory list,
// verified by the F2.7.0 mutations test suite); this component does
// NOT touch queryClient.
//
// Why a regular <Button> for Confirm (instead of AlertDialogAction):
//   AlertDialogAction auto-closes the dialog on click. We need manual
//   control because:
//     - on success → close via useEffect (after invalidations fire)
//     - on error → STAY open (preserve context for retry)
//   AlertDialogCancel for Cancel keeps the auto-close behavior — that
//   IS the desired UX there.
//
// Hard rules in force:
//   - No reason field. The brief excludes it for forward transitions
//     and the backend treats it as optional.
//   - No queryClient invalidation in this component. The mutation
//     hook is the single source of cache invalidation.
//   - No fetch, no Zustand, no permissions check.

import { useEffect } from "react";

import { getApiErrorMessage } from "@/api";
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";

import { useTransitionOrderStatusMutation } from "../hooks";
import type { OrderRead, OrderStatus } from "../types";

interface TransitionStatusDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  order: OrderRead;
  targetStatus: OrderStatus | null;
}

export function TransitionStatusDialog({
  open,
  onOpenChange,
  order,
  targetStatus,
}: TransitionStatusDialogProps) {
  const mutation = useTransitionOrderStatusMutation();

  // Reset on every (re)open so a relaunched dialog (different target,
  // retry after error) starts clean. Without this, last session's
  // error message bleeds across opens.
  useEffect(() => {
    if (open) {
      mutation.reset();
    }
  }, [open, mutation.reset]);

  // Auto-close on success. Cache invalidation is handled by the
  // mutation's onSuccess (F2.7.0); this component only owns dialog
  // state.
  useEffect(() => {
    if (mutation.isSuccess) {
      onOpenChange(false);
    }
  }, [mutation.isSuccess, onOpenChange]);

  // Block ESC / overlay click / Cancel-button close while pending so
  // the request finishes before the dialog disappears.
  const handleOpenChange = (next: boolean) => {
    if (mutation.isPending) return;
    onOpenChange(next);
  };

  const handleConfirm = () => {
    if (targetStatus === null) return;
    mutation.mutate({
      orderId: order.id,
      body: { new_status: targetStatus },
    });
  };

  return (
    <AlertDialog open={open} onOpenChange={handleOpenChange}>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Confirm status change</AlertDialogTitle>
          <AlertDialogDescription>
            Mark order{" "}
            <span className="font-mono text-xs">{order.id}</span> as{" "}
            <span className="font-medium uppercase tracking-wide">
              {targetStatus ?? "—"}
            </span>
            ?
          </AlertDialogDescription>
        </AlertDialogHeader>

        {mutation.isError ? (
          <p
            role="alert"
            aria-live="polite"
            className="text-sm text-destructive"
            data-testid="transition-status-error"
          >
            {getApiErrorMessage(mutation.error)}
          </p>
        ) : null}

        <AlertDialogFooter>
          <AlertDialogCancel disabled={mutation.isPending}>
            Cancel
          </AlertDialogCancel>
          <Button
            onClick={handleConfirm}
            disabled={mutation.isPending || targetStatus === null}
            data-testid="transition-status-confirm"
          >
            {mutation.isPending ? "Updating..." : "Confirm"}
          </Button>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
