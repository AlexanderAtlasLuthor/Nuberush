// F2.8.6: Deactivate Variant confirmation dialog.
//
// Soft delete only — calls `deleteProductVariant` with `hard: false`.
// The label is "Deactivate", never "Delete", because the wire effect
// is reversible. Hard delete UI is deliberately NOT exposed.
//
// `productId` travels through the variables (not the wire) so the hook
// can invalidate the parent product's variant list and detail cache.
// The api call still only sends `{variantId, hard}` over the wire.

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

import { useDeleteVariantMutation } from "../hooks";
import type { ProductVariant } from "../types";

interface DeactivateVariantDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  variant: ProductVariant;
}

export function DeactivateVariantDialog({
  open,
  onOpenChange,
  variant,
}: DeactivateVariantDialogProps) {
  const mutation = useDeleteVariantMutation();

  useEffect(() => {
    if (mutation.isSuccess && open) {
      onOpenChange(false);
    }
  }, [mutation.isSuccess, open, onOpenChange]);

  const handleDeactivate = () => {
    if (mutation.isPending) return;
    mutation.mutate({
      variantId: variant.id,
      productId: variant.product_id,
      hard: false,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Deactivate variant</DialogTitle>
          <DialogDescription>
            Mark variant{" "}
            <span className="font-mono text-xs">{variant.sku}</span> as
            inactive. The variant stays in the database; it disappears from
            sellable variant queries until reactivated. Inventory rows and
            historical order lines that reference this variant are preserved.
          </DialogDescription>
        </DialogHeader>

        {mutation.isError ? (
          <p
            role="alert"
            aria-live="polite"
            className="text-sm text-destructive"
            data-testid="deactivate-variant-error"
          >
            {getApiErrorMessage(mutation.error)}
          </p>
        ) : null}

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
            type="button"
            variant="destructive"
            onClick={handleDeactivate}
            disabled={mutation.isPending}
            data-testid="deactivate-variant-submit"
          >
            {mutation.isPending ? "Deactivating…" : "Deactivate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
