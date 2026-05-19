// F2.15.6: row-level actions menu for the users table.
//
// Pure callback router — clicking a menu item calls the matching
// `on*` prop with the row's user. The parent owns modal state. This
// avoids three problems:
//   1. Mutation hooks subscribing for every row in the list.
//   2. Tight coupling between row UX and modal layouts.
//   3. Authorization logic creeping into the menu (which would
//      duplicate the backend matrix and rot every time the matrix
//      changes).
//
// `showAdminActions` is a UX hint, not authority. It hides the
// admin-only items (assign store) when the parent knows the caller
// cannot use them — a non-admin who sees them and clicks anyway
// still gets a 403 from the backend, which is the correct surface.

import { MoreHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

import type { UserRead } from "../types";

export interface UserActionsMenuProps {
  user: UserRead;
  onEdit?: (user: UserRead) => void;
  /**
   * Single callback for the deactivate / reactivate transition. The
   * caller decides which copy to render in the dialog based on
   * `user.is_active` — keeping it as one prop keeps this menu's
   * surface small.
   */
  onDeactivateReactivate?: (user: UserRead) => void;
  onChangeRole?: (user: UserRead) => void;
  onAssignStore?: (user: UserRead) => void;
  /** Disables the trigger and prevents any menu items from firing. */
  disabled?: boolean;
  /**
   * UX hint only. When false, the admin-only items (assign store) are
   * hidden from the menu. The backend remains authoritative for
   * non-admin callers.
   */
  showAdminActions?: boolean;
}

export function UserActionsMenu({
  user,
  onEdit,
  onDeactivateReactivate,
  onChangeRole,
  onAssignStore,
  disabled = false,
  showAdminActions = false,
}: UserActionsMenuProps) {
  const showEdit = typeof onEdit === "function";
  const showLifecycle = typeof onDeactivateReactivate === "function";
  const showRole = typeof onChangeRole === "function";
  const showAssignStore =
    showAdminActions && typeof onAssignStore === "function";

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-8 w-8 p-0"
          aria-label={`Open actions for ${user.full_name}`}
          disabled={disabled}
          data-testid="user-actions-trigger"
        >
          <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuLabel>User actions</DropdownMenuLabel>
        <DropdownMenuSeparator />
        {showEdit ? (
          <DropdownMenuItem
            onSelect={() => onEdit?.(user)}
            data-testid="user-action-edit"
          >
            Edit profile
          </DropdownMenuItem>
        ) : null}
        {showRole ? (
          <DropdownMenuItem
            onSelect={() => onChangeRole?.(user)}
            data-testid="user-action-change-role"
          >
            Change role
          </DropdownMenuItem>
        ) : null}
        {showLifecycle ? (
          <DropdownMenuItem
            onSelect={() => onDeactivateReactivate?.(user)}
            data-testid={
              user.is_active
                ? "user-action-deactivate"
                : "user-action-reactivate"
            }
          >
            {user.is_active ? "Deactivate" : "Reactivate"}
          </DropdownMenuItem>
        ) : null}
        {showAssignStore ? (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuLabel>Admin actions</DropdownMenuLabel>
            <DropdownMenuItem
              onSelect={() => onAssignStore?.(user)}
              data-testid="user-action-assign-store"
            >
              Assign store
            </DropdownMenuItem>
          </>
        ) : null}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
