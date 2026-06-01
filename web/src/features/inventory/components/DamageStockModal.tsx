// F2.6.2 subfase 1: Damage Stock modal.
//
// Mirrors AdjustStockModal in lifecycle (reset on open, auto-close on
// success), disabled-while-pending UX, and inline ApiError surfacing.
// Only the wire contract differs:
//
//   - `quantity` is unsigned (positive integer) — the backend service
//     applies the negative sign when reducing stock. Backend rejects
//     quantity <= 0 with 422.
//   - `reason` is mandatory and non-empty after trim. Backend rejects
//     empty/whitespace-only with 422.
//
// We deliberately do NOT show "stock before/after", do NOT decide
// whether there is enough stock, and do NOT gate by status / compliance
// — that's all the backend's job. The frontend only captures input,
// posts, and surfaces whatever the server returned.

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

import { useDamageStockMutation } from "../hooks";
import type { InventoryItem } from "../types";

interface DamageStockModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: InventoryItem;
}

export function DamageStockModal({
  open,
  onOpenChange,
  item,
}: DamageStockModalProps) {
  // String-typed for the same reasons as Receive/Adjust: lets the user
  // clear and re-type without the browser snapping to 0.
  const [quantityStr, setQuantityStr] = useState("");
  const [reason, setReason] = useState("");

  const mutation = useDamageStockMutation();
  // `reset` is referentially stable (TanStack Query v5); destructure it so
  // the effect depends on the stable callback rather than the whole mutation
  // object (whose identity changes across isPending/isSuccess transitions).
  const { reset } = mutation;

  // Reset form + mutation on every (re)open so a relaunched dialog
  // (different row, retry after error) starts clean.
  useEffect(() => {
    if (open) {
      setQuantityStr("");
      setReason("");
      reset();
    }
  }, [open, reset]);

  // Auto-close on success. Cache invalidation already runs inside the
  // mutation's onSuccess; we only own the dialog state here.
  useEffect(() => {
    if (mutation.isSuccess) {
      onOpenChange(false);
    }
  }, [mutation.isSuccess, onOpenChange]);

  // UX guards mirror the backend's validators:
  //   - quantity must be a positive integer
  //   - reason must be non-empty after trim
  // Backend remains the source of truth and will 422 anything else.
  const parsedQuantity =
    quantityStr === "" ? Number.NaN : Number(quantityStr);
  const isQuantityValid =
    Number.isInteger(parsedQuantity) && parsedQuantity > 0;
  const trimmedReason = reason.trim();
  const isReasonValid = trimmedReason.length > 0;
  const canSubmit = isQuantityValid && isReasonValid && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;

    mutation.mutate({
      inventoryItemId: item.id,
      body: {
        quantity: parsedQuantity,
        reason: trimmedReason,
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit} noValidate>
          <DialogHeader>
            <DialogTitle>Record damaged stock</DialogTitle>
            <DialogDescription>
              Record lost, damaged or stolen units of{" "}
              <span className="font-medium">
                {item.variant.product.name}
              </span>{" "}
              <span className="font-mono text-xs">({item.variant.sku})</span>.
              The server reduces inventory and writes the audit log.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="damage-quantity">
                Quantity <span className="text-destructive">*</span>
              </Label>
              <Input
                id="damage-quantity"
                type="number"
                min={1}
                step={1}
                inputMode="numeric"
                value={quantityStr}
                onChange={(e) => setQuantityStr(e.target.value)}
                disabled={mutation.isPending}
                autoFocus
                required
                aria-describedby="damage-quantity-hint"
              />
              <p
                id="damage-quantity-hint"
                className="text-xs text-muted-foreground"
              >
                Positive whole number of units lost or damaged.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="damage-reason">
                Reason <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="damage-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                disabled={mutation.isPending}
                rows={2}
                required
                placeholder="Why are these units being written off?"
              />
            </div>

            {mutation.isError ? (
              <p
                role="alert"
                aria-live="polite"
                className="text-sm text-destructive"
                data-testid="damage-stock-error"
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
              data-testid="damage-stock-submit"
            >
              {mutation.isPending ? "Recording…" : "Record damage"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
