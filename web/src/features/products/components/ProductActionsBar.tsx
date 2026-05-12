// F2.8.6: row of admin actions for a single product.
//
// Mirrors the orders pattern (`OrderActionsBar`): mounted by the
// detail page between the header and the section panels, owns the
// open/close state for each modal it can launch.
//
// Buttons (per F2.8.6 brief §2):
//   - Edit product       → ProductFormModal in edit mode
//   - Add variant        → ProductVariantFormModal in create mode
//   - Deactivate product → DeactivateProductDialog (soft delete)
//
// The Update compliance button stays in `ProductDetailHeader` (added in
// F2.8.5) — it's not duplicated here. UX-wise both clusters live on
// the same page, just in different rows; consolidating into a single
// bar is a future polish.
//
// Hard rules:
//   - No fetch / no mutations / no permissions in this file. Every
//     button toggles a boolean; the heavy lifting lives in each modal.
//   - All modals are conditionally mounted so their mutation hooks
//     don't subscribe until the operator opens the dialog.

import { useState } from "react";
import { Layers, Pencil, PowerOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Product } from "../types";

import { DeactivateProductDialog } from "./DeactivateProductDialog";
import { ProductFormModal } from "./ProductFormModal";
import { ProductVariantFormModal } from "./ProductVariantFormModal";

interface ProductActionsBarProps {
  product: Product;
}

export function ProductActionsBar({ product }: ProductActionsBarProps) {
  const [openEdit, setOpenEdit] = useState(false);
  const [openAddVariant, setOpenAddVariant] = useState(false);
  const [openDeactivate, setOpenDeactivate] = useState(false);

  return (
    <>
      <div
        className="flex flex-wrap items-center gap-2"
        data-testid="product-actions-bar"
      >
        <Button
          variant="outline"
          size="sm"
          onClick={() => setOpenEdit(true)}
          data-testid="product-action-edit"
        >
          <Pencil className="mr-2 h-4 w-4" aria-hidden="true" />
          Edit product
        </Button>

        <Button
          variant="outline"
          size="sm"
          onClick={() => setOpenAddVariant(true)}
          data-testid="product-action-add-variant"
        >
          <Layers className="mr-2 h-4 w-4" aria-hidden="true" />
          Add variant
        </Button>

        <Button
          variant="outline"
          size="sm"
          onClick={() => setOpenDeactivate(true)}
          data-testid="product-action-deactivate"
        >
          <PowerOff className="mr-2 h-4 w-4" aria-hidden="true" />
          Deactivate
        </Button>
      </div>

      {openEdit ? (
        <ProductFormModal
          mode="edit"
          open={openEdit}
          onOpenChange={setOpenEdit}
          product={product}
        />
      ) : null}

      {openAddVariant ? (
        <ProductVariantFormModal
          mode="create"
          open={openAddVariant}
          onOpenChange={setOpenAddVariant}
          productId={product.id}
        />
      ) : null}

      {openDeactivate ? (
        <DeactivateProductDialog
          open={openDeactivate}
          onOpenChange={setOpenDeactivate}
          product={product}
        />
      ) : null}
    </>
  );
}
