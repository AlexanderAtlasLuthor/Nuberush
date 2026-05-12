// F2.18.5: presentational table for the admin global inventory feed.
//
// Pure presentational component. The parent supplies the rows and
// the loading / error state; this component only renders. No
// fetching, no API calls, no permission logic.
//
// Read-only: NO action column, NO mutation buttons, NO row menu.
// Per the F2.18 contract lock (§9.3) the Admin Inventory UI must not
// render mutation controls (no receive / adjust / sell / etc.).
//
// Columns deliberately match the wire contract: backend
// `InventoryItemRead` (mirrored by `InventoryItem` in types.ts) carries
// id, store_id, variant_id, quantity_on_hand, quantity_reserved,
// reorder_threshold, status, last_counted_at, created_at, updated_at,
// and `variant` (with nested product). Nothing else is rendered;
// inventing columns would lie to the UI.

import { Boxes } from "lucide-react";

import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import type { InventoryItem } from "../types";

interface AdminInventoryTableProps {
  items: InventoryItem[];
  isLoading?: boolean;
  error?: unknown;
  onRetry?: () => void;
  emptyTitle?: string;
  emptyDescription?: string;
}

function readErrorMessage(error: unknown): string | undefined {
  if (error instanceof Error && error.message.length > 0) {
    return error.message;
  }
  return undefined;
}

function shortId(value: string): string {
  return value.length > 8 ? value.slice(0, 8) : value;
}

export function AdminInventoryTable({
  items,
  isLoading = false,
  error,
  onRetry,
  emptyTitle = "No inventory found",
  emptyDescription = "No inventory matches the current filters across the platform.",
}: AdminInventoryTableProps) {
  if (isLoading) {
    return <LoadingState message="Loading inventory…" />;
  }

  if (error) {
    return (
      <ErrorState
        title="Could not load inventory"
        message={
          readErrorMessage(error) ??
          "An unexpected error occurred while loading inventory."
        }
        onRetry={onRetry}
      />
    );
  }

  if (items.length === 0) {
    return (
      <EmptyState
        icon={Boxes}
        title={emptyTitle}
        message={emptyDescription}
      />
    );
  }

  return (
    <div
      className="rounded-md border border-border"
      data-testid="admin-inventory-table"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Store</TableHead>
            <TableHead>Product</TableHead>
            <TableHead>SKU</TableHead>
            <TableHead className="text-right">Stock</TableHead>
            <TableHead className="text-right">Reserved</TableHead>
            <TableHead className="text-right">Threshold</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Updated</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item) => (
            <TableRow key={item.id} data-testid="admin-inventory-row">
              <TableCell
                className="font-mono text-xs text-muted-foreground"
                data-testid="admin-inventory-row-store"
                title={item.store_id}
              >
                {shortId(item.store_id)}
              </TableCell>
              <TableCell
                className="font-medium"
                data-testid="admin-inventory-row-product"
              >
                {item.variant.product.name}
              </TableCell>
              <TableCell
                className="font-mono text-xs"
                data-testid="admin-inventory-row-sku"
              >
                {item.variant.sku}
              </TableCell>
              <TableCell
                className="text-right tabular-nums"
                data-testid="admin-inventory-row-on-hand"
              >
                {item.quantity_on_hand}
              </TableCell>
              <TableCell
                className="text-right tabular-nums"
                data-testid="admin-inventory-row-reserved"
              >
                {item.quantity_reserved}
              </TableCell>
              <TableCell
                className="text-right tabular-nums"
                data-testid="admin-inventory-row-threshold"
              >
                {item.reorder_threshold}
              </TableCell>
              <TableCell
                className="text-xs uppercase tracking-wide text-muted-foreground"
                data-testid="admin-inventory-row-status"
              >
                {item.status}
              </TableCell>
              <TableCell
                className="font-mono text-xs text-muted-foreground"
                data-testid="admin-inventory-row-updated"
                title={item.updated_at}
              >
                {item.updated_at}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
