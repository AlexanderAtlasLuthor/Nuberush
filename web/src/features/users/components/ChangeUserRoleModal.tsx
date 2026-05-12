// F2.15.6: Change user role modal.
//
// Wraps `useChangeUserRoleMutation` (F2.15.4) inside a Dialog. The
// select shows every UserRole; the backend matrix
// (`USER_ROLE_UPDATE_MATRIX`) is the single source of truth for which
// transitions a given caller may perform and surfaces 403 / 422 with
// a `detail` string the modal renders verbatim.
//
// Deliberately NOT implemented:
//   - frontend role-matrix authority (no per-caller filter on options).
//   - "promote to admin clears store_id" UI hints — backend does that
//     server-side and the response carries the new state.
//   - cross-store / store-invariant checks — backend handles them.

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
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import { useChangeUserRoleMutation } from "../hooks";
import type { UserRead, UserRole } from "../types";

const ROLE_OPTIONS: ReadonlyArray<{
  readonly value: UserRole;
  readonly label: string;
}> = [
  { value: "admin", label: "Admin" },
  { value: "owner", label: "Owner" },
  { value: "manager", label: "Manager" },
  { value: "staff", label: "Staff" },
  { value: "driver", label: "Driver" },
];

export interface ChangeUserRoleModalProps {
  user: UserRead | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (user: UserRead) => void;
}

export function ChangeUserRoleModal({
  user,
  open,
  onOpenChange,
  onSuccess,
}: ChangeUserRoleModalProps) {
  const [role, setRole] = useState<UserRole>(user?.role ?? "staff");

  const mutation = useChangeUserRoleMutation();

  // Re-sync role + clear stale errors when the modal opens on a new row.
  useEffect(() => {
    if (open) {
      setRole(user?.role ?? "staff");
      mutation.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, user?.id]);

  useEffect(() => {
    if (mutation.isSuccess && mutation.data && open) {
      onSuccess?.(mutation.data);
      onOpenChange(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mutation.isSuccess, mutation.data]);

  const isUnchanged = user !== null && role === user.role;
  const canSubmit = user !== null && !isUnchanged && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit || user === null) return;
    mutation.mutate({ userId: user.id, body: { role } });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-md"
        data-testid="change-user-role-modal"
      >
        <DialogHeader>
          <DialogTitle>Change user role</DialogTitle>
          <DialogDescription>
            The backend decides whether you may assign this role and
            adjusts the store assignment automatically when promoting
            to or demoting from admin.
          </DialogDescription>
        </DialogHeader>

        {user === null ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="change-user-role-no-target"
          >
            No user selected.
          </p>
        ) : (
          <form
            onSubmit={handleSubmit}
            noValidate
            data-testid="change-user-role-form"
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
                <p>
                  <span className="text-muted-foreground">Current role:</span>{" "}
                  <span
                    className="uppercase tracking-wide"
                    data-testid="change-user-role-current"
                  >
                    {user.role}
                  </span>
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="change-user-role-select">New role</Label>
                <Select
                  value={role}
                  disabled={mutation.isPending}
                  onValueChange={(v) => setRole(v as UserRole)}
                >
                  <SelectTrigger
                    id="change-user-role-select"
                    data-testid="change-user-role-trigger"
                  >
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ROLE_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>

              {mutation.isError ? (
                <p
                  role="alert"
                  aria-live="polite"
                  className="text-sm text-destructive"
                  data-testid="change-user-role-error"
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
                data-testid="change-user-role-cancel"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={!canSubmit}
                data-testid="change-user-role-submit"
              >
                {mutation.isPending ? "Saving…" : "Change role"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
