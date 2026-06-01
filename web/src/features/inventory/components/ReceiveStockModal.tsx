// F2.6.2 subfase 2: Receive Stock modal.
//
// Self-contained dialog driven by `useReceiveStockMutation` from F2.6.0.
// Owns its own form state via useState (per the brief's allowance) and
// nothing else: no fetch, no Zustand, no business rules. The trio of
// effects below handle modal lifecycle UX (reset on open, auto-close
// on success) — these are not business logic, just dialog plumbing.
//
// Validation policy (intentionally minimal, matching the brief):
//   - quantity must be a positive integer; the Submit button stays
//     disabled until that holds.
//   - reason / reference_type / reference_id are sent verbatim when
//     non-empty, otherwise as `null` (backend rejects whitespace-only
//     strings, so we don't ship them).
//   - Cross-field rules (e.g. reference_type and reference_id must be
//     paired) are enforced server-side; if a user fills only one, the
//     422 propagates as ApiError.message.
//
// NOT integrated with InventoryActions yet — the brief explicitly says
// that wiring lands in the next subfase.

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

import { useReceiveStockMutation } from "../hooks";
import type { InventoryItem } from "../types";

interface ReceiveStockModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: InventoryItem;
}

function nullableTrim(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function ReceiveStockModal({
  open,
  onOpenChange,
  item,
}: ReceiveStockModalProps) {
  // Form state — string-typed for the number field so the user can
  // clear the input and re-type without the browser snapping to 0.
  const [quantityStr, setQuantityStr] = useState("");
  const [reason, setReason] = useState("");
  const [referenceType, setReferenceType] = useState("");
  const [referenceId, setReferenceId] = useState("");

  const mutation = useReceiveStockMutation();
  // `reset` is referentially stable (TanStack Query v5); destructure it so
  // the effect depends on the stable callback rather than the whole mutation
  // object (whose identity changes across isPending/isSuccess transitions).
  const { reset } = mutation;

  // Reset form + mutation on every (re)open so a re-launched dialog
  // (different row, retry after error, etc.) starts clean. Without
  // this, last session's values bleed across rows.
  useEffect(() => {
    if (open) {
      setQuantityStr("");
      setReason("");
      setReferenceType("");
      setReferenceId("");
      reset();
    }
  }, [open, reset]);

  // Auto-close on success. Cache invalidation is already handled by
  // the mutation's onSuccess (F2.6.0); we only own the dialog state.
  useEffect(() => {
    if (mutation.isSuccess) {
      onOpenChange(false);
    }
  }, [mutation.isSuccess, onOpenChange]);

  // Minimal client-side validation: quantity must be a positive
  // integer. Anything else is the backend's job to reject.
  const parsedQuantity = quantityStr === "" ? Number.NaN : Number(quantityStr);
  const isQuantityValid =
    Number.isInteger(parsedQuantity) && parsedQuantity > 0;
  const canSubmit = isQuantityValid && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;

    mutation.mutate({
      inventoryItemId: item.id,
      body: {
        quantity: parsedQuantity,
        reason: nullableTrim(reason),
        reference_type: nullableTrim(referenceType),
        reference_id: nullableTrim(referenceId),
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit} noValidate>
          <DialogHeader>
            <DialogTitle>Receive stock</DialogTitle>
            <DialogDescription>
              Add inbound stock for{" "}
              <span className="font-medium">
                {item.variant.product.name}
              </span>{" "}
              <span className="font-mono text-xs">({item.variant.sku})</span>.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="receive-quantity">
                Quantity <span className="text-destructive">*</span>
              </Label>
              <Input
                id="receive-quantity"
                type="number"
                min={1}
                step={1}
                inputMode="numeric"
                value={quantityStr}
                onChange={(e) => setQuantityStr(e.target.value)}
                disabled={mutation.isPending}
                autoFocus
                required
                aria-describedby="receive-quantity-hint"
              />
              <p
                id="receive-quantity-hint"
                className="text-xs text-muted-foreground"
              >
                Must be a positive whole number.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="receive-reason">Reason</Label>
              <Textarea
                id="receive-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                disabled={mutation.isPending}
                rows={2}
                placeholder="Optional"
              />
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <Label htmlFor="receive-reference-type">Reference type</Label>
                <Input
                  id="receive-reference-type"
                  value={referenceType}
                  onChange={(e) => setReferenceType(e.target.value)}
                  disabled={mutation.isPending}
                  placeholder="Optional"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="receive-reference-id">Reference id</Label>
                <Input
                  id="receive-reference-id"
                  value={referenceId}
                  onChange={(e) => setReferenceId(e.target.value)}
                  disabled={mutation.isPending}
                  placeholder="Optional"
                />
              </div>
            </div>

            {mutation.isError ? (
              <p
                role="alert"
                aria-live="polite"
                className="text-sm text-destructive"
                data-testid="receive-stock-error"
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
              data-testid="receive-stock-submit"
            >
              {mutation.isPending ? "Receiving…" : "Receive"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
