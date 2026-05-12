// F2.15.6: Edit user profile modal.
//
// Wraps `useUpdateUserMutation` (F2.15.4) inside a Dialog. Only the
// two fields the backend `UserUpdateRequest` schema accepts —
// `full_name` and `phone` — are exposed. Privileged columns
// (`email`, `role`, `store_id`, `is_active`, `password_hash`) are
// NOT rendered, NOT inferable from this modal, and would surface
// as 422 from the backend if a future change tried to send them.
//
// Phone caveat: backend `UserRead` does not surface `phone` on the
// wire today (locked by F2.15.1 / F2.15.3). The modal therefore
// initialises the phone field to "" — never a guess from the user
// row. The PATCH endpoint accepts `phone`, so editing still works;
// the operator just types fresh.
//
// Mirrors the F2.8.5 / F2.8.6 modal pattern verbatim:
//   - useEffect-based auto-close on mutation.isSuccess.
//   - inline error via getApiErrorMessage.
//   - submit disabled while pending.
//   - no manual refetch / no setQueryData.
//   - no permission authority — backend enforces RBAC and surfaces
//     401 / 403 / 422 unchanged.

import { useEffect, useState, type FormEvent } from "react";

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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

import { useUpdateUserMutation } from "../hooks";
import type { UserRead, UserUpdateRequest } from "../types";

const FULL_NAME_MAX = 150;
const PHONE_MAX = 30;

export interface EditUserModalProps {
  user: UserRead | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called once with the updated user on successful submit. */
  onSuccess?: (user: UserRead) => void;
}

export function EditUserModal({
  user,
  open,
  onOpenChange,
  onSuccess,
}: EditUserModalProps) {
  const [fullName, setFullName] = useState(user?.full_name ?? "");
  // Backend `UserRead` does not expose `phone`, so we cannot pre-fill
  // a real value. The input starts blank and a `phoneTouched` flag
  // tracks whether the operator interacted with it. We only put
  // `phone` in the PATCH body when the flag is true — otherwise we
  // omit the key entirely so the backend keeps the existing value
  // (F2.15.10 hardening: stops a "save full_name only" flow from
  // silently wiping the user's phone on the server).
  const [phone, setPhone] = useState("");
  const [phoneTouched, setPhoneTouched] = useState(false);

  const mutation = useUpdateUserMutation();

  // Re-sync the editable fields when the user prop or open state changes
  // — opening the modal on a different row should reset the inputs.
  useEffect(() => {
    if (open) {
      setFullName(user?.full_name ?? "");
      setPhone("");
      setPhoneTouched(false);
      mutation.reset();
    }
    // We intentionally exclude `mutation` from the dep list to avoid
    // resetting on every render (mutation is recreated each render).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, user?.id]);

  // Hand the updated user up to the parent once per success transition
  // and auto-close. Excluded `onSuccess` from the deps to keep behavior
  // stable when the parent re-creates the callback per render.
  useEffect(() => {
    if (mutation.isSuccess && mutation.data && open) {
      onSuccess?.(mutation.data);
      onOpenChange(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mutation.isSuccess, mutation.data]);

  const trimmedName = fullName.trim();
  const trimmedPhone = phone.trim();
  const isFullNameValid = trimmedName.length > 0;
  const canSubmit =
    user !== null && isFullNameValid && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit || user === null) return;

    const body: UserUpdateRequest = { full_name: trimmedName };
    // Only include `phone` if the operator actually touched the
    // field. Sending `phone: null` unconditionally would clear the
    // existing phone every time someone "just" edits the name — see
    // F2.15.10 hardening notes. When phoneTouched is true:
    //   - empty string → explicit clear (null on the wire)
    //   - non-empty   → trimmed value
    if (phoneTouched) {
      body.phone = trimmedPhone.length > 0 ? trimmedPhone : null;
    }

    mutation.mutate({ userId: user.id, body });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="edit-user-modal">
        <DialogHeader>
          <DialogTitle>Edit user</DialogTitle>
          <DialogDescription>
            Update the user&apos;s profile. Email, role, store and
            account status are managed separately and are not editable
            here.
          </DialogDescription>
        </DialogHeader>

        {user === null ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="edit-user-no-target"
          >
            No user selected.
          </p>
        ) : (
          <form
            onSubmit={handleSubmit}
            noValidate
            data-testid="edit-user-form"
          >
            <div className="space-y-4">
              <div className="space-y-1 text-sm">
                <p>
                  <span className="text-muted-foreground">Name:</span>{" "}
                  <span className="font-medium" data-testid="edit-user-current-name">
                    {user.full_name}
                  </span>
                </p>
                <p>
                  <span className="text-muted-foreground">Email:</span>{" "}
                  <span
                    className="font-mono text-xs"
                    data-testid="edit-user-current-email"
                  >
                    {user.email}
                  </span>
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="edit-user-full-name">
                  Full name <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="edit-user-full-name"
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  disabled={mutation.isPending}
                  required
                  maxLength={FULL_NAME_MAX}
                  autoComplete="name"
                  data-testid="edit-user-full-name"
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="edit-user-phone">Phone</Label>
                <Input
                  id="edit-user-phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => {
                    setPhone(e.target.value);
                    setPhoneTouched(true);
                  }}
                  disabled={mutation.isPending}
                  maxLength={PHONE_MAX}
                  autoComplete="tel"
                  placeholder="Leave untouched to keep the current phone"
                  data-testid="edit-user-phone"
                />
                <p className="text-xs text-muted-foreground">
                  Leave the phone field untouched to keep the current
                  phone. Type a new value to update it, or clear the
                  field after typing to remove it.
                </p>
              </div>

              {mutation.isError ? (
                <p
                  role="alert"
                  aria-live="polite"
                  className="text-sm text-destructive"
                  data-testid="edit-user-error"
                >
                  {getApiErrorMessage(mutation.error)}
                </p>
              ) : null}
            </div>

            <DialogFooter className="mt-6">
              <Button
                type="button"
                variant="outline"
                onClick={() => onOpenChange(false)}
                disabled={mutation.isPending}
                data-testid="edit-user-cancel"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={!canSubmit}
                data-testid="edit-user-submit"
              >
                {mutation.isPending ? "Saving…" : "Save changes"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
