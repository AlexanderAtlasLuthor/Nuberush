// F2.15.5: users list table.
//
// Read-only projection of the wire `UserRead` shape. No client-side
// derivations, no fetching, no permission logic. The parent supplies
// the rows and the optional `actions` slot; this component only
// renders. Loading / error / empty states delegate to the shared
// primitives in `@/components/common` so a consistent look-and-feel
// is preserved across features.
//
// Columns deliberately match the wire contract: backend `UserRead`
// today carries id / full_name / email / role / store_id / is_active.
// `phone`, `created_at`, `updated_at` are NOT on the wire, so they
// are NOT rendered here. Inventing them would set up a silent contract
// drift with the backend.
//
// `store_id` is a UUID, not a name. Until a stores enumeration
// endpoint exists, the cell shows the raw UUID for non-null values
// and "Global" for admins (`store_id === null`). This is consistent
// with how the existing UsersPage's "Recently created" panel renders
// the same field today.

import type { ReactNode } from "react";
import { Users } from "lucide-react";

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

import type { UserRead } from "../types";
import { UserRoleBadge } from "./UserRoleBadge";
import { UserStatusBadge } from "./UserStatusBadge";

interface UsersTableProps {
  users: UserRead[];
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
   * rendered at all (no empty header, no extra cell). When present,
   * the function is invoked with the row's user and its return value
   * goes into the cell.
   */
  actions?: (user: UserRead) => ReactNode;
  emptyTitle?: string;
  emptyDescription?: string;
}

const STORE_GLOBAL_LABEL = "Global";

function readErrorMessage(error: unknown): string | undefined {
  if (error instanceof Error && error.message.length > 0) {
    return error.message;
  }
  return undefined;
}

export function UsersTable({
  users,
  isLoading = false,
  error,
  onRetry,
  actions,
  emptyTitle = "No users found",
  emptyDescription = "Try adjusting filters or create a new user.",
}: UsersTableProps) {
  if (isLoading) {
    return <LoadingState message="Loading users…" />;
  }

  if (error) {
    return (
      <ErrorState
        title="Could not load users"
        message={
          readErrorMessage(error) ??
          "An unexpected error occurred while loading users."
        }
        onRetry={onRetry}
      />
    );
  }

  if (users.length === 0) {
    return (
      <EmptyState
        icon={Users}
        title={emptyTitle}
        message={emptyDescription}
      />
    );
  }

  const showActionsColumn = typeof actions === "function";

  return (
    <div className="rounded-md border border-border" data-testid="users-table">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Name</TableHead>
            <TableHead>Email</TableHead>
            <TableHead>Role</TableHead>
            <TableHead>Store</TableHead>
            <TableHead>Status</TableHead>
            {showActionsColumn ? (
              <TableHead className="w-32 text-right">
                <span className="sr-only">Actions</span>
              </TableHead>
            ) : null}
          </TableRow>
        </TableHeader>
        <TableBody>
          {users.map((user) => (
            <TableRow key={user.id} data-testid="users-row">
              <TableCell
                className="font-medium"
                data-testid="users-row-name"
              >
                {user.full_name}
              </TableCell>
              <TableCell
                className="font-mono text-xs"
                data-testid="users-row-email"
              >
                {user.email}
              </TableCell>
              <TableCell>
                <UserRoleBadge role={user.role} />
              </TableCell>
              <TableCell
                className="font-mono text-xs text-muted-foreground"
                data-testid="users-row-store"
              >
                {user.store_id ?? STORE_GLOBAL_LABEL}
              </TableCell>
              <TableCell>
                <UserStatusBadge isActive={user.is_active} />
              </TableCell>
              {showActionsColumn ? (
                <TableCell
                  className="text-right"
                  data-testid="users-row-actions"
                >
                  {actions?.(user)}
                </TableCell>
              ) : null}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
