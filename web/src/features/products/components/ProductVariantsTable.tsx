// F2.8.4: variants table for the product detail page.
// F2.8.6: per-row Edit / Deactivate actions wired through the variant
// form modal and the deactivate variant dialog. Each row owns its own
// modal-open state so two rows opening modals at once never collide.
//
// Self-contained read-only panel: takes a productId and owns its own
// data fetch via `useProductVariantsQuery(productId)`. Manages
// loading / error / empty / success states inside its own Card so a
// slow variants query never blocks the header / compliance render.
//
// Hard rules in force:
//   - No fetch, no Zustand, no business logic in this file.
//   - No client-side derivations: `is_active`, `price`, `sku`, `barcode`
//     are all wire fields rendered verbatim. Decimal-as-string `price`
//     is NOT coerced to a number.
//   - No display-label composition (e.g. "SKU – flavor – size") — each
//     wire field gets its own column so the operator can scan them
//     independently.
//   - Row actions are mutation-bearing modals; they conditionally mount
//     so the mutation hooks don't subscribe per row on every render.

import { useState } from "react";
import { Layers, MoreHorizontal } from "lucide-react";

import { getApiErrorMessage } from "@/api";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { useProductVariantsQuery } from "../hooks";
import type { ProductVariant } from "../types";
import { DeactivateVariantDialog } from "./DeactivateVariantDialog";
import { ProductStatusBadge } from "./ProductStatusBadge";
import { ProductVariantFormModal } from "./ProductVariantFormModal";

const EM_DASH = "—";

function nullableText(value: string | null | undefined): string {
  return value === null || value === undefined || value === ""
    ? EM_DASH
    : value;
}

interface ProductVariantsTableProps {
  productId: string;
}

export function ProductVariantsTable({ productId }: ProductVariantsTableProps) {
  const { isLoading, isError, error, data: variants, refetch } =
    useProductVariantsQuery(productId);

  return (
    <Card>
      <CardHeader>
        <CardTitle>Variants</CardTitle>
        <CardDescription>
          SKU-level variants for this product. Use the actions menu on each
          row to edit or deactivate; new variants are added via the
          actions bar above.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        {isLoading ? (
          <LoadingState message="Loading variants…" />
        ) : isError ? (
          <ErrorState
            title="Variants failed to load"
            message={getApiErrorMessage(error)}
            onRetry={() => refetch()}
          />
        ) : variants && variants.length === 0 ? (
          <EmptyState
            icon={Layers}
            title="No variants"
            message="This product has no variants yet."
          />
        ) : variants ? (
          <div className="rounded-b-md border-t border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SKU</TableHead>
                  <TableHead>Barcode</TableHead>
                  <TableHead className="text-right">Price</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="w-12 text-right">
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {variants.map((variant) => (
                  <TableRow
                    key={variant.id}
                    data-testid="product-variants-row"
                  >
                    <TableCell className="font-mono text-xs">
                      {variant.sku}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {nullableText(variant.barcode)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {variant.price}
                    </TableCell>
                    <TableCell>
                      <ProductStatusBadge isActive={variant.is_active} />
                    </TableCell>
                    <TableCell className="text-right">
                      <VariantRowActions variant={variant} />
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

// --------------------------------------------------------------------- //
// Row actions
// --------------------------------------------------------------------- //

function VariantRowActions({ variant }: { variant: ProductVariant }) {
  const [openEdit, setOpenEdit] = useState(false);
  const [openDeactivate, setOpenDeactivate] = useState(false);

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            aria-label={`Open actions for variant ${variant.sku}`}
            data-testid="variant-row-actions-trigger"
          >
            <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-40">
          <DropdownMenuItem
            onSelect={() => setOpenEdit(true)}
            data-testid="variant-row-action-edit"
          >
            Edit variant
          </DropdownMenuItem>
          <DropdownMenuItem
            onSelect={() => setOpenDeactivate(true)}
            data-testid="variant-row-action-deactivate"
          >
            Deactivate
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      {openEdit ? (
        <ProductVariantFormModal
          mode="edit"
          open={openEdit}
          onOpenChange={setOpenEdit}
          productId={variant.product_id}
          variant={variant}
        />
      ) : null}

      {openDeactivate ? (
        <DeactivateVariantDialog
          open={openDeactivate}
          onOpenChange={setOpenDeactivate}
          variant={variant}
        />
      ) : null}
    </>
  );
}
