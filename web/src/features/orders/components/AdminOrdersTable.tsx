// F2.18.5: presentational table for the admin global orders feed.
//
// Pure presentational component. The parent supplies the rows and
// the loading / error state; this component only renders. No
// fetching, no API calls, no permission logic.
//
// Read-only: NO action column, NO mutation buttons, NO row menu.
// Per the F2.18 contract lock (§9.3) the Admin Orders UI must not
// render mutation controls (no create / cancel / return /
// status-transition).
//
// Columns deliberately match the wire contract: backend `OrderRead`
// carries id, store_id, status, total_amount (Decimal-as-string),
// created_at, updated_at, items (array — length is the item count).
// Nothing else is rendered; inventing columns would lie to the UI.

import { ClipboardList } from "lucide-react";

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

import type { OrderRead } from "../types";

interface AdminOrdersTableProps {
  orders: OrderRead[];
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

export function AdminOrdersTable({
  orders,
  isLoading = false,
  error,
  onRetry,
  emptyTitle = "No orders found",
  emptyDescription = "No orders match the current filters across the platform.",
}: AdminOrdersTableProps) {
  if (isLoading) {
    return <LoadingState message="Loading orders…" />;
  }

  if (error) {
    return (
      <ErrorState
        title="Could not load orders"
        message={
          readErrorMessage(error) ??
          "An unexpected error occurred while loading orders."
        }
        onRetry={onRetry}
      />
    );
  }

  if (orders.length === 0) {
    return (
      <EmptyState
        icon={ClipboardList}
        title={emptyTitle}
        message={emptyDescription}
      />
    );
  }

  return (
    <div
      className="rounded-md border border-border"
      data-testid="admin-orders-table"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Order</TableHead>
            <TableHead>Store</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="text-right">Items</TableHead>
            <TableHead className="text-right">Total</TableHead>
            <TableHead>Created</TableHead>
            <TableHead>Updated</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {orders.map((order) => (
            <TableRow key={order.id} data-testid="admin-orders-row">
              <TableCell
                className="font-mono text-xs"
                data-testid="admin-orders-row-id"
                title={order.id}
              >
                {shortId(order.id)}
              </TableCell>
              <TableCell
                className="font-mono text-xs text-muted-foreground"
                data-testid="admin-orders-row-store"
                title={order.store_id}
              >
                {shortId(order.store_id)}
              </TableCell>
              <TableCell
                className="text-xs uppercase tracking-wide text-muted-foreground"
                data-testid="admin-orders-row-status"
              >
                {order.status}
              </TableCell>
              <TableCell
                className="text-right tabular-nums"
                data-testid="admin-orders-row-items"
              >
                {order.items.length}
              </TableCell>
              <TableCell
                className="text-right tabular-nums"
                data-testid="admin-orders-row-total"
              >
                {order.total_amount}
              </TableCell>
              <TableCell
                className="font-mono text-xs text-muted-foreground"
                data-testid="admin-orders-row-created"
                title={order.created_at}
              >
                {order.created_at}
              </TableCell>
              <TableCell
                className="font-mono text-xs text-muted-foreground"
                data-testid="admin-orders-row-updated"
                title={order.updated_at}
              >
                {order.updated_at}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
