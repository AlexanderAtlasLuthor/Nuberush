// F2.8.5: Update Product Compliance modal.
//
// Mirrors the inventory modal pattern (UpdateStatusModal):
//   - Form initial values come from the current product, so the user
//     edits relative to the existing state instead of starting blank.
//   - Submit is disabled while pending and re-enabled when the mutation
//     finishes; auto-close on success closes the dialog and lets the
//     hook's invalidations refresh the parent page.
//   - Backend errors surface inline via `getApiErrorMessage`.
//
// Hard rules in force (per F2.8.5 brief §4):
//   - The frontend NEVER enforces the "banned + allowed_for_sale = true
//     is invalid" invariant. The backend owns it (Pydantic
//     `_enforce_banned_invariant` + DB CHECK constraint), and a 422
//     response is the canonical signal. We deliberately allow any
//     combination through the UI so the operator can see the backend's
//     rule reflected in the error path, never re-implemented client-side.
//   - No sellable derivation, no permission gating. The audit row that
//     fires on every successful update is written server-side.

import { useEffect, useState, type FormEvent } from "react";

import { getApiErrorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
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

import { useUpdateComplianceMutation } from "../hooks";
import type { Product, ProductComplianceStatus } from "../types";

interface UpdateProductComplianceModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  product: Product;
}

const COMPLIANCE_OPTIONS: ReadonlyArray<{
  value: ProductComplianceStatus;
  label: string;
}> = [
  { value: "allowed", label: "Allowed" },
  { value: "restricted", label: "Restricted" },
  { value: "banned", label: "Banned" },
];

export function UpdateProductComplianceModal({
  open,
  onOpenChange,
  product,
}: UpdateProductComplianceModalProps) {
  // Form state seeded from the current product. The component is
  // conditionally mounted by the parent (only when open=true), so each
  // open is a fresh mount and these initial values reflect the latest
  // product props.
  const [complianceStatus, setComplianceStatus] = useState<
    ProductComplianceStatus
  >(product.compliance_status);
  const [allowedForSale, setAllowedForSale] = useState<boolean>(
    product.allowed_for_sale,
  );
  const [reason, setReason] = useState<string>("");

  const mutation = useUpdateComplianceMutation();

  // Auto-close on successful mutation. The hook already invalidates
  // detail / lists / sellable / complianceAudit, so the parent page
  // refreshes itself once the dialog unmounts. Wrapped in useEffect to
  // avoid the cross-component setState-during-render warning React
  // raises when calling the parent's `onOpenChange` directly in the
  // render body (mirrors the inventory UpdateStatusModal pattern).
  useEffect(() => {
    if (mutation.isSuccess && open) {
      onOpenChange(false);
    }
  }, [mutation.isSuccess, open, onOpenChange]);

  const trimmedReason = reason.trim();
  const isReasonValid = trimmedReason.length > 0;
  const canSubmit = isReasonValid && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;

    mutation.mutate({
      productId: product.id,
      body: {
        compliance_status: complianceStatus,
        allowed_for_sale: allowedForSale,
        reason: trimmedReason,
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit} noValidate>
          <DialogHeader>
            <DialogTitle>Update compliance</DialogTitle>
            <DialogDescription>
              Update the compliance state of{" "}
              <span className="font-medium">{product.name}</span>. The backend
              validates the combination and writes one audit row per
              successful update; the UI does not enforce the rules.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="compliance-status">
                Compliance status <span className="text-destructive">*</span>
              </Label>
              <Select
                value={complianceStatus}
                onValueChange={(value) =>
                  setComplianceStatus(value as ProductComplianceStatus)
                }
                disabled={mutation.isPending}
              >
                <SelectTrigger
                  id="compliance-status"
                  data-testid="compliance-status-trigger"
                >
                  <SelectValue placeholder="Select a compliance status" />
                </SelectTrigger>
                <SelectContent>
                  {COMPLIANCE_OPTIONS.map((opt) => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Current:{" "}
                <span className="font-medium">{product.compliance_status}</span>.
              </p>
            </div>

            <div className="flex items-center gap-2">
              <Checkbox
                id="compliance-allowed-for-sale"
                checked={allowedForSale}
                disabled={mutation.isPending}
                onCheckedChange={(value) =>
                  setAllowedForSale(value === true)
                }
                data-testid="compliance-allowed-checkbox"
              />
              <Label
                htmlFor="compliance-allowed-for-sale"
                className="text-sm cursor-pointer"
              >
                Allowed for sale
              </Label>
            </div>

            <div className="space-y-2">
              <Label htmlFor="compliance-reason">
                Reason <span className="text-destructive">*</span>
              </Label>
              <Textarea
                id="compliance-reason"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                disabled={mutation.isPending}
                rows={3}
                required
                placeholder="Why is this compliance change being made?"
                data-testid="compliance-reason-input"
              />
              <p className="text-xs text-muted-foreground">
                Captured verbatim into the compliance audit log.
              </p>
            </div>

            {mutation.isError ? (
              <p
                role="alert"
                aria-live="polite"
                className="text-sm text-destructive"
                data-testid="compliance-error"
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
              data-testid="compliance-submit"
            >
              {mutation.isPending ? "Updating…" : "Update compliance"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
