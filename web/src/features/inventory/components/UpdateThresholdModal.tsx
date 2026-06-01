// F2.6.2 subfase 2: Update Threshold modal.
//
// Mirrors the existing movement modals (Receive / Adjust / Damage) in
// lifecycle (reset on open, auto-close on success), disabled-while-
// pending UX, and inline ApiError surfacing. Only the wire contract
// differs:
//
//   - The endpoint is PATCH /inventory/{id}/threshold (not POST).
//   - The body carries a single field `reorder_threshold` (snake_case
//     to match the wire), constrained to int >= 0 server-side.
//
// The current threshold is pre-filled from the item so the user sees
// the existing value and can edit it; this is plain UX, not business
// logic. The frontend NEVER decides whether the item is low-stock —
// that classification belongs to the backend / list filter.

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

import { useUpdateInventoryThresholdMutation } from "../hooks";
import type { InventoryItem } from "../types";

interface UpdateThresholdModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: InventoryItem;
}

export function UpdateThresholdModal({
  open,
  onOpenChange,
  item,
}: UpdateThresholdModalProps) {
  // String-typed for the same reasons as the other modals: lets the
  // user clear the input or correct typos without the browser snapping
  // to 0.
  const [thresholdStr, setThresholdStr] = useState("");

  const mutation = useUpdateInventoryThresholdMutation();
  // `reset` is referentially stable (TanStack Query v5); destructure it so
  // the effect depends on the stable callback rather than the whole mutation
  // object (whose identity changes across isPending/isSuccess transitions).
  const { reset } = mutation;

  // Reset form + mutation on every (re)open. The current threshold is
  // pre-filled from the item so the user has context to edit from.
  useEffect(() => {
    if (open) {
      setThresholdStr(String(item.reorder_threshold));
      reset();
    }
  }, [open, item.reorder_threshold, reset]);

  // Auto-close on success. Cache invalidation already runs inside the
  // mutation's onSuccess; we only own the dialog state here.
  useEffect(() => {
    if (mutation.isSuccess) {
      onOpenChange(false);
    }
  }, [mutation.isSuccess, onOpenChange]);

  // UX guard mirrors the backend's `int (ge=0)` validator. Backend is
  // still the source of truth and will 422 anything else.
  const parsedThreshold =
    thresholdStr === "" ? Number.NaN : Number(thresholdStr);
  const isThresholdValid =
    Number.isInteger(parsedThreshold) && parsedThreshold >= 0;
  const canSubmit = isThresholdValid && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;

    mutation.mutate({
      inventoryItemId: item.id,
      body: {
        reorder_threshold: parsedThreshold,
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit} noValidate>
          <DialogHeader>
            <DialogTitle>Set low-stock threshold</DialogTitle>
            <DialogDescription>
              Configure when{" "}
              <span className="font-medium">
                {item.variant.product.name}
              </span>{" "}
              <span className="font-mono text-xs">({item.variant.sku})</span>{" "}
              appears as low stock. The server applies this value and the
              list view re-evaluates membership on its next fetch.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="threshold-value">
                Threshold <span className="text-destructive">*</span>
              </Label>
              <Input
                id="threshold-value"
                type="number"
                min={0}
                step={1}
                inputMode="numeric"
                value={thresholdStr}
                onChange={(e) => setThresholdStr(e.target.value)}
                disabled={mutation.isPending}
                autoFocus
                required
                aria-describedby="threshold-value-hint"
              />
              <p
                id="threshold-value-hint"
                className="text-xs text-muted-foreground"
              >
                Whole number, zero or greater. Set 0 to disable low-stock
                alerts on this item.
              </p>
            </div>

            {mutation.isError ? (
              <p
                role="alert"
                aria-live="polite"
                className="text-sm text-destructive"
                data-testid="update-threshold-error"
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
              data-testid="update-threshold-submit"
            >
              {mutation.isPending ? "Saving…" : "Save threshold"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
