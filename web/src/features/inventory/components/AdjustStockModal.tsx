// F2.6.2 subfase 4: Adjust Stock modal.
//
// Mirror of ReceiveStockModal — same lifecycle effects (reset on open,
// auto-close on success), same disabled-while-pending UX, same inline
// ApiError surfacing. The only differences are the wire contract:
//
//   - `delta` is signed (positive adds, negative removes) and must be
//     non-zero. Backend rejects delta=0 with 422.
//   - `reason` is mandatory and non-empty after trim. Backend rejects
//     empty/whitespace-only with 422.
//
// reference_type / reference_id are out of scope for this subfase per
// the brief; the wire allows them as optional, but the form does not
// surface them yet. The mutation body simply omits both keys, which
// matches the wire's `?` modifier.

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

import { useAdjustStockMutation } from "../hooks";
import type { InventoryItem } from "../types";

interface AdjustStockModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: InventoryItem;
}

export function AdjustStockModal({
  open,
  onOpenChange,
  item,
}: AdjustStockModalProps) {
  // String-typed for the same reasons as Receive: lets the user clear
  // the input, type a leading "-", or correct typos without the
  // browser snapping to 0.
  const [deltaStr, setDeltaStr] = useState("");
  const [reason, setReason] = useState("");

  const mutation = useAdjustStockMutation();

  // Reset form + mutation on every (re)open so a relaunched dialog
  // (different row, retry after error) starts clean.
  useEffect(() => {
    if (open) {
      setDeltaStr("");
      setReason("");
      mutation.reset();
    }
  }, [open, mutation.reset]);

  // Auto-close on success. Cache invalidation already runs inside the
  // mutation's onSuccess (F2.6.0); we only own the dialog state.
  useEffect(() => {
    if (mutation.isSuccess) {
      onOpenChange(false);
    }
  }, [mutation.isSuccess, onOpenChange]);

  // Minimal validation, exactly what the brief asks:
  //   - delta must be a non-zero integer
  //   - reason must be non-empty after trim
  // Anything else (locking, sellability, audit log, threshold side
  // effects) is the backend's job.
  const parsedDelta = deltaStr === "" ? Number.NaN : Number(deltaStr);
  const isDeltaValid =
    Number.isInteger(parsedDelta) && parsedDelta !== 0;
  const trimmedReason = reason.trim();
  const isReasonValid = trimmedReason.length > 0;
  const canSubmit = isDeltaValid && isReasonValid && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;

    mutation.mutate({
      inventoryItemId: item.id,
      body: {
        delta: parsedDelta,
        reason: trimmedReason,
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit} noValidate>
          <DialogHeader>
            <DialogTitle>Adjust stock</DialogTitle>
            <DialogDescription>
              Apply a signed adjustment to{" "}
              <span className="font-medium">
                {item.variant.product.name}
              </span>{" "}
              <span className="font-mono text-xs">({item.variant.sku})</span>.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="adjust-delta">
                Delta <span className="text-destructive">*</span>
              </Label>
              <Input
                id="adjust-delta"
                type="number"
                step={1}
                inputMode="numeric"
                value={deltaStr}
                onChange={(e) => setDeltaStr(e.target.value)}
                disabled={mutation.isPending}
                autoFocus
                required
                aria-describedby="adjust-delta-hint"
              />
              <p
                id="adjust-delta-hint"
                className="text-xs text-muted-foreground"
              >
                Signed whole number; positive adds, negative removes. Zero is
                not allowed.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="adjust-reason">
                Reason <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="adjust-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                disabled={mutation.isPending}
                rows={2}
                required
                placeholder="Why is this adjustment needed?"
              />
            </div>

            {mutation.isError ? (
              <p
                role="alert"
                aria-live="polite"
                className="text-sm text-destructive"
                data-testid="adjust-stock-error"
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
              disabled={!canSubmit}
              data-testid="adjust-stock-submit"
            >
              {mutation.isPending ? "Adjusting…" : "Adjust"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
