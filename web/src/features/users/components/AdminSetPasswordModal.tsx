// F2.15.6: Admin-set-password modal.
//
// Direct password set, admin-only. Wraps `useAdminSetPasswordMutation`
// (F2.15.4). The wire body is `{ new_password }` only — no
// `password_hash`, no token, no email, no SMTP, no invitation flow.
// The backend hashes the password server-side; the response is a
// `UserRead` and never includes the hash.
//
// UX rules:
//   - field clears on close and on success.
//   - inline error via getApiErrorMessage.
//   - submit disabled while pending or when the input is too short.
//   - copy explicitly says "set directly" so the operator knows this
//     is not a self-service reset.

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

import { useAdminSetPasswordMutation } from "../hooks";
import type { UserRead } from "../types";

// Backend bounds (locked by F2.15.1 / F2.15.2 schemas + tests).
const PASSWORD_MIN_LENGTH = 8;
const PASSWORD_MAX_LENGTH = 128;

export interface AdminSetPasswordModalProps {
  user: UserRead | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (user: UserRead) => void;
}

export function AdminSetPasswordModal({
  user,
  open,
  onOpenChange,
  onSuccess,
}: AdminSetPasswordModalProps) {
  const [newPassword, setNewPassword] = useState("");

  const mutation = useAdminSetPasswordMutation();

  useEffect(() => {
    if (open) {
      setNewPassword("");
      mutation.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, user?.id]);

  useEffect(() => {
    if (mutation.isSuccess && mutation.data && open) {
      onSuccess?.(mutation.data);
      setNewPassword("");
      onOpenChange(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mutation.isSuccess, mutation.data]);

  const isPasswordValid =
    newPassword.length >= PASSWORD_MIN_LENGTH &&
    newPassword.length <= PASSWORD_MAX_LENGTH;
  const canSubmit =
    user !== null && isPasswordValid && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit || user === null) return;
    mutation.mutate({
      userId: user.id,
      body: { new_password: newPassword },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-md"
        data-testid="admin-set-password-modal"
      >
        <DialogHeader>
          <DialogTitle>Set a new password</DialogTitle>
          <DialogDescription>
            Set a new password directly for this user. The system
            sends nothing to the user automatically — communicate the
            new password through a separate channel.
          </DialogDescription>
        </DialogHeader>

        {user === null ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="admin-set-password-no-target"
          >
            No user selected.
          </p>
        ) : (
          <form
            onSubmit={handleSubmit}
            noValidate
            data-testid="admin-set-password-form"
          >
            <div className="space-y-4">
              <div className="space-y-1 text-sm">
                <p>
                  <span className="text-muted-foreground">Name:</span>{" "}
                  <span className="font-medium">{user.full_name}</span>
                </p>
                <p>
                  <span className="text-muted-foreground">Email:</span>{" "}
                  <span className="font-mono text-xs">{user.email}</span>
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="admin-set-password-new">
                  New password <span className="text-destructive">*</span>
                </Label>
                <Input
                  id="admin-set-password-new"
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  disabled={mutation.isPending}
                  required
                  minLength={PASSWORD_MIN_LENGTH}
                  maxLength={PASSWORD_MAX_LENGTH}
                  autoComplete="new-password"
                  data-testid="admin-set-password-input"
                />
                <p className="text-xs text-muted-foreground">
                  Minimum {PASSWORD_MIN_LENGTH} characters. The
                  backend re-validates and stores only a bcrypt hash.
                </p>
              </div>

              {mutation.isError ? (
                <p
                  role="alert"
                  aria-live="polite"
                  className="text-sm text-destructive"
                  data-testid="admin-set-password-error"
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
                data-testid="admin-set-password-cancel"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={!canSubmit}
                data-testid="admin-set-password-submit"
              >
                {mutation.isPending ? "Setting…" : "Set password"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
