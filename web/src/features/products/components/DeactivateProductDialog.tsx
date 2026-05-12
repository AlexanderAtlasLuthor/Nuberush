// F2.8.6: Deactivate Product confirmation dialog.
//
// Soft delete only — calls `deleteProduct` with `hard: false` (the
// backend interprets this as "set is_active = false while preserving
// FK history"). The label is intentionally "Deactivate", never
// "Delete", because the wire effect is reversible.
//
// Hard delete UI is deliberately NOT exposed at this subphase. If a
// future operator needs hard delete, that gates on a separate flow
// and a separate confirmation; conflating the two here would create a
// cliff for accidental data loss.
//
// Mirrors the F2.8.5 modal pattern verbatim:
//   - conditionally mounted by the parent (no idle hook subscription)
//   - useEffect-based auto-close on mutation.isSuccess
//   - inline error via getApiErrorMessage
//   - submit disabled while pending
//   - no manual refetch / no setQueryData

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

import { useDeleteProductMutation } from "../hooks";
import type { Product } from "../types";

interface DeactivateProductDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  product: Product;
}

export function DeactivateProductDialog({
  open,
  onOpenChange,
  product,
}: DeactivateProductDialogProps) {
  const mutation = useDeleteProductMutation();

  useEffect(() => {
    if (mutation.isSuccess && open) {
      onOpenChange(false);
    }
  }, [mutation.isSuccess, open, onOpenChange]);

  const handleDeactivate = () => {
    if (mutation.isPending) return;
    mutation.mutate({ productId: product.id, hard: false });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Deactivate product</DialogTitle>
          <DialogDescription>
            Mark{" "}
            <span className="font-medium">{product.name}</span> as inactive.
            The product stays in the database; it disappears from sellable
            catalogue queries until reactivated. Variants and historical
            orders are preserved.
          </DialogDescription>
        </DialogHeader>

        {mutation.isError ? (
          <p
            role="alert"
            aria-live="polite"
            className="text-sm text-destructive"
            data-testid="deactivate-product-error"
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
            data-testid="deactivate-product-submit"
          >
            {mutation.isPending ? "Deactivating…" : "Deactivate"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
