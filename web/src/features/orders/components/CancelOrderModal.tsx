// F2.7.4 subfase 3: cancel-order modal.
//
// Self-contained Dialog driven by `useCancelOrderMutation` from
// F2.7.0. Required `reason` because backend rejects empty/whitespace
// (orders_rules §6 — manager-or-above + audit trail must explain
// the cancellation). Cache invalidation contract (orders.list +
// orders.item + orders.auditLogs + inventory.list) lives inside the
// mutation hook; this component does NOT touch queryClient.
//
// Why Dialog (not AlertDialog) here: the cancel flow needs a form
// field (Textarea for reason) — AlertDialog is for stateless
// confirmations. Mirrors the F2.6.2 AdjustStockModal pattern.
//
// Hard rules in force:
//   - Validation = `reason.trim().length > 0`. Nothing else.
//   - No status check, no permissions check, no state-machine logic.
//   - No fetch, no Zustand, no queryClient invalidation.
//   - No replication of orders_rules. Backend authorises and rejects;
//     errors surface inline via getApiErrorMessage.

import { useEffect, useState, type FormEvent } from "react";

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
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import { useCancelOrderMutation } from "../hooks";
import type { OrderRead } from "../types";

interface CancelOrderModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  order: OrderRead;
}

export function CancelOrderModal({
  open,
  onOpenChange,
  order,
}: CancelOrderModalProps) {
  const [reason, setReason] = useState("");

  const mutation = useCancelOrderMutation();

  // Reset form + mutation on every (re)open so a relaunched dialog
  // (different order, retry after error) starts clean.
  useEffect(() => {
    if (open) {
      setReason("");
      mutation.reset();
    }
  }, [open, mutation.reset]);

  // Auto-close on success. Cache invalidation runs inside the
  // mutation's onSuccess (F2.7.0); this component only owns dialog
  // state.
  useEffect(() => {
    if (mutation.isSuccess) {
      onOpenChange(false);
    }
  }, [mutation.isSuccess, onOpenChange]);

  // Block ESC / overlay click while pending so the request finishes
  // before the dialog disappears.
  const handleOpenChange = (next: boolean) => {
    if (mutation.isPending) return;
    onOpenChange(next);
  };

  // Minimal validation, exactly what the brief allows: reason must be
  // non-empty after trim. Backend (orders_rules §6) enforces the same
  // and returns 422 if violated; this is UX-only to avoid an obvious
  // round-trip.
  const trimmedReason = reason.trim();
  const isReasonValid = trimmedReason.length > 0;
  const canSubmit = isReasonValid && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;
    mutation.mutate({
      orderId: order.id,
      body: { reason: trimmedReason },
    });
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit} noValidate>
          <DialogHeader>
            <DialogTitle>Cancel order</DialogTitle>
            <DialogDescription>
              Cancel order{" "}
              <span className="font-mono text-xs">{order.id}</span>?
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="cancel-reason">
                Reason <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="cancel-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                disabled={mutation.isPending}
                rows={3}
                required
                autoFocus
                placeholder="Why is this order being canceled?"
              />
            </div>

            {mutation.isError ? (
              <p
                role="alert"
                aria-live="polite"
                className="text-sm text-destructive"
                data-testid="cancel-order-error"
              >
                {getApiErrorMessage(mutation.error)}
              </p>
            ) : null}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={mutation.isPending}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              variant="destructive"
              disabled={!canSubmit}
              data-testid="cancel-order-confirm"
            >
              {mutation.isPending ? "Canceling..." : "Confirm cancellation"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
