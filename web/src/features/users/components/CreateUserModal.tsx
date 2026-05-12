// F2.9.3: CreateUserModal.
//
// Thin wrapper that hosts CreateUserForm inside the project's standard
// Dialog. Mirrors the open/onOpenChange contract used by the products
// modal pattern (features/products/components/ProductFormModal.tsx).
//
// Auto-close behaviour:
//   When the form fires `onCreated(user)` we both surface that to the
//   parent (optional `onCreated` prop) and call `onOpenChange(false)`.
//   Closing unmounts the form, which mount/unmount-resets every input
//   so the next open is clean — same UX as ProductFormModal.
//
// Hard rules:
//   - No routing.
//   - No table/list behaviour.
//   - No permission logic. The form already enforces a role-blind
//     pipeline; the modal adds nothing.

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type { UserRead } from "../types";
import { CreateUserForm } from "./CreateUserForm";

export interface CreateUserModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called once with the created user on a successful submit. */
  onCreated?: (user: UserRead) => void;
}

export function CreateUserModal({
  open,
  onOpenChange,
  onCreated,
}: CreateUserModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg" data-testid="create-user-modal">
        <DialogHeader>
          <DialogTitle>Create user</DialogTitle>
          <DialogDescription>
            The backend authorises the request, validates the role and
            store assignment, and decides whether the email is unique.
            This form only collects the input.
          </DialogDescription>
        </DialogHeader>
        <CreateUserForm
          onCancel={() => onOpenChange(false)}
          onCreated={(user) => {
            onCreated?.(user);
            onOpenChange(false);
          }}
        />
      </DialogContent>
    </Dialog>
  );
}
