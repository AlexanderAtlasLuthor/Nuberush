// F2.6.2 subfase 3: Update Status modal.
//
// Mirrors the other inventory modals in lifecycle (reset on open,
// auto-close on success), disabled-while-pending UX, and inline
// ApiError surfacing. Two notable differences:
//
//   - Status is a Select (radix), constrained to the MVP-settable
//     subset (available / flagged / quarantined). The 5-value
//     `InventoryStatus` wire union also contains `reserved` and `sold`,
//     but those are derived states the backend rejects on this
//     endpoint (see `_MVP_OPERATIONAL_STATUSES` in
//     backend/app/services/inventory.py). Narrowing here is UI-only;
//     we still type the request as `InventoryStatus` to match the wire.
//   - When the chosen status differs from the item's current status,
//     a small informational note surfaces. It is purely visual — it
//     does NOT block submit and does NOT encode any business rule.
//     Backend remains the source of truth for what changes are valid.

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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";

import { useUpdateInventoryStatusMutation } from "../hooks";
import type { InventoryItem, InventoryStatus } from "../types";

interface UpdateStatusModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  item: InventoryItem;
}

// MVP-settable subset, mirrored from `_MVP_OPERATIONAL_STATUSES` on the
// backend. Listed here so the dropdown shows operator-friendly labels;
// the wire values stay snake-case-bare to match `InventoryStatus`.
const STATUS_OPTIONS: ReadonlyArray<{
  value: InventoryStatus;
  label: string;
}> = [
  { value: "available", label: "Available" },
  { value: "flagged", label: "Flagged" },
  { value: "quarantined", label: "Quarantined" },
];

export function UpdateStatusModal({
  open,
  onOpenChange,
  item,
}: UpdateStatusModalProps) {
  // Pre-fill with the item's current status as a UX convenience. If the
  // current status is outside the MVP-settable subset (e.g. "reserved"
  // or "sold"), the Select shows a placeholder and the user must pick
  // an explicit MVP value before submit.
  const [statusValue, setStatusValue] = useState<InventoryStatus | "">("");
  const [reason, setReason] = useState("");

  const mutation = useUpdateInventoryStatusMutation();

  useEffect(() => {
    if (open) {
      const initial = STATUS_OPTIONS.some((o) => o.value === item.status)
        ? item.status
        : "";
      setStatusValue(initial);
      setReason("");
      mutation.reset();
    }
  }, [open, item.status, mutation.reset]);

  useEffect(() => {
    if (mutation.isSuccess) {
      onOpenChange(false);
    }
  }, [mutation.isSuccess, onOpenChange]);

  const trimmedReason = reason.trim();
  const isStatusValid = statusValue !== "";
  const isReasonValid = trimmedReason.length > 0;
  const canSubmit = isStatusValid && isReasonValid && !mutation.isPending;

  const isStatusChanged =
    isStatusValid && statusValue !== item.status;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;

    mutation.mutate({
      inventoryItemId: item.id,
      body: {
        status: statusValue as InventoryStatus,
        reason: trimmedReason,
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit} noValidate>
          <DialogHeader>
            <DialogTitle>Update inventory status</DialogTitle>
            <DialogDescription>
              Change the operational status of{" "}
              <span className="font-medium">
                {item.variant.product.name}
              </span>{" "}
              <span className="font-mono text-xs">({item.variant.sku})</span>.
              The backend validates whether the change is permitted; the UI
              does not enforce transition rules.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="status-select">
                Status <span className="text-destructive">*</span>
              </Label>
              <Select
                value={statusValue}
                onValueChange={(value) =>
                  setStatusValue(value as InventoryStatus)
                }
                disabled={mutation.isPending}
              >
                <SelectTrigger
                  id="status-select"
                  aria-describedby="status-select-hint"
                >
                  <SelectValue placeholder="Select a status" />
                </SelectTrigger>
                <SelectContent>
                  {STATUS_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p
                id="status-select-hint"
                className="text-xs text-muted-foreground"
              >
                Current status:{" "}
                <span className="font-medium">{item.status}</span>.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="status-reason">
                Reason <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="status-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                disabled={mutation.isPending}
                rows={2}
                required
                placeholder="Why is this status change needed?"
              />
            </div>

            {isStatusChanged ? (
              <p
                role="note"
                className="text-xs text-muted-foreground border-l-2 border-amber-500 pl-3"
                data-testid="update-status-warning"
              >
                Changing status may affect whether this item can be sold or
                reserved. The backend will enforce the final rules.
              </p>
            ) : null}

            {mutation.isError ? (
              <p
                role="alert"
                aria-live="polite"
                className="text-sm text-destructive"
                data-testid="update-status-error"
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
              data-testid="update-status-submit"
            >
              {mutation.isPending ? "Updating…" : "Update status"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
