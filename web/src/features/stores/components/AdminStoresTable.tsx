// F2.18.3: admin stores list table.
//
// Read-only projection of the wire `StoreProfile` shape. No client-side
// derivations, no fetching, no permission logic. The parent supplies
// the rows and the optional `actions` slot; this component only
// renders. Loading / error / empty states delegate to the shared
// primitives in `@/components/common` so the look-and-feel matches
// every other list page in the app.
//
// Columns deliberately match the wire contract: backend `StoreRead`
// today carries id / name / code / timezone / is_active / created_at /
// updated_at. Nothing else is rendered.
//
// Name renders as a router Link to /app/admin/stores/:storeId so the
// detail route is reachable by a single click. The Link is the only
// routing concern in this file; everything else is presentational.

import type { ReactNode } from "react";
import { Building2 } from "lucide-react";
import { Link } from "react-router-dom";

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

import type { StoreProfile } from "../types";
import { StoreStatusBadge } from "./StoreStatusBadge";

interface AdminStoresTableProps {
  stores: StoreProfile[];
  isLoading?: boolean;
  /**
   * Truthy error → render `ErrorState`. The shape is intentionally
   * `unknown` so a TanStack Query error, a thrown ApiError, or a
   * boolean flag can all flow in without per-call casts.
   */
  error?: unknown;
  onRetry?: () => void;
  /**
   * Per-row actions slot. When omitted, the Actions column is not
   * rendered at all (no empty header, no extra cell).
   */
  actions?: (store: StoreProfile) => ReactNode;
  emptyTitle?: string;
  emptyDescription?: string;
}

function readErrorMessage(error: unknown): string | undefined {
  if (error instanceof Error && error.message.length > 0) {
    return error.message;
  }
  return undefined;
}

export function AdminStoresTable({
  stores,
  isLoading = false,
  error,
  onRetry,
  actions,
  emptyTitle = "No stores found",
  emptyDescription = "Try adjusting filters or create a new store.",
}: AdminStoresTableProps) {
  if (isLoading) {
    return <LoadingState message="Loading stores…" />;
  }

  if (error) {
    return (
      <ErrorState
        title="Could not load stores"
        message={
          readErrorMessage(error) ??
          "An unexpected error occurred while loading stores."
        }
        onRetry={onRetry}
      />
    );
  }

  if (stores.length === 0) {
    return (
      <EmptyState
        icon={Building2}
        title={emptyTitle}
        message={emptyDescription}
      />
    );
  }

  const showActionsColumn = typeof actions === "function";

  return (
    <div
      className="rounded-md border border-border"
      data-testid="admin-stores-table"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Code</TableHead>
            <TableHead>Timezone</TableHead>
            <TableHead>Status</TableHead>
            {showActionsColumn ? (
              <TableHead className="w-32 text-right">
                <span className="sr-only">Actions</span>
              </TableHead>
            ) : null}
          </TableRow>
        </TableHeader>
        <TableBody>
          {stores.map((store) => (
            <TableRow key={store.id} data-testid="admin-stores-row">
              <TableCell
                className="font-medium"
                data-testid="admin-stores-row-name"
              >
                <Link
                  to={`/app/admin/stores/${store.id}`}
                  className="hover:underline"
                  data-testid="admin-stores-row-link"
                >
                  {store.name}
                </Link>
              </TableCell>
              <TableCell
                className="font-mono text-xs"
                data-testid="admin-stores-row-code"
              >
                {store.code}
              </TableCell>
              <TableCell
                className="font-mono text-xs text-muted-foreground"
                data-testid="admin-stores-row-timezone"
              >
                {store.timezone}
              </TableCell>
              <TableCell>
                <StoreStatusBadge isActive={store.is_active} />
              </TableCell>
              {showActionsColumn ? (
                <TableCell
                  className="text-right"
                  data-testid="admin-stores-row-actions"
                >
                  {actions?.(store)}
                </TableCell>
              ) : null}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
