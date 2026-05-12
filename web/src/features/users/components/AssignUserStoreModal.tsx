// F2.15.6: Assign user store modal.
//
// Admin-only flow on the wire (the backend rejects non-admin callers
// with 403). The modal exposes a raw UUID input rather than a store
// picker because no `/stores` enumeration endpoint exists yet — see
// the F2.9.0 backend contract report and F2.15.4 api.ts header for
// the catalogue of endpoints that intentionally don't ship.
//
// Empty string → null on the wire. Backend invariants enforce admin
// targets receive null and non-admin targets receive a real UUID;
// inactive store → 400; missing store → 404. The modal renders the
// `detail` string verbatim.

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

import { useAssignUserStoreMutation } from "../hooks";
import type { UserRead } from "../types";

export interface AssignUserStoreModalProps {
  user: UserRead | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSuccess?: (user: UserRead) => void;
}

export function AssignUserStoreModal({
  user,
  open,
  onOpenChange,
  onSuccess,
}: AssignUserStoreModalProps) {
  const [storeId, setStoreId] = useState(user?.store_id ?? "");

  const mutation = useAssignUserStoreMutation();

  useEffect(() => {
    if (open) {
      setStoreId(user?.store_id ?? "");
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

  const trimmed = storeId.trim();
  const canSubmit = user !== null && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit || user === null) return;
    mutation.mutate({
      userId: user.id,
      body: { store_id: trimmed.length > 0 ? trimmed : null },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-md"
        data-testid="assign-user-store-modal"
      >
        <DialogHeader>
          <DialogTitle>Assign store</DialogTitle>
          <DialogDescription>
            Enter a store UUID, or leave blank only for global admin
            users. The backend rejects mismatches between role and
            store assignment.
          </DialogDescription>
        </DialogHeader>

        {user === null ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="assign-user-store-no-target"
          >
            No user selected.
          </p>
        ) : (
          <form
            onSubmit={handleSubmit}
            noValidate
            data-testid="assign-user-store-form"
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
                  <span className="text-muted-foreground">Current store:</span>{" "}
                  <span
                    className="font-mono text-xs"
                    data-testid="assign-user-store-current"
                  >
                    {user.store_id ?? "Global"}
                  </span>
                </p>
              </div>

              <div className="space-y-2">
                <Label htmlFor="assign-user-store-id">Store ID</Label>
                <Input
                  id="assign-user-store-id"
                  type="text"
                  value={storeId}
                  onChange={(e) => setStoreId(e.target.value)}
                  disabled={mutation.isPending}
                  placeholder="Store UUID, or blank for admin"
                  data-testid="assign-user-store-input"
                />
                <p className="text-xs text-muted-foreground">
                  Empty value sends <code className="font-mono">null</code>{" "}
                  to the server.
                </p>
              </div>

              {mutation.isError ? (
                <p
                  role="alert"
                  aria-live="polite"
                  className="text-sm text-destructive"
                  data-testid="assign-user-store-error"
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
                data-testid="assign-user-store-cancel"
              >
                Cancel
              </Button>
              <Button
                type="submit"
                disabled={!canSubmit}
                data-testid="assign-user-store-submit"
              >
                {mutation.isPending ? "Assigning…" : "Assign store"}
              </Button>
            </DialogFooter>
          </form>
        )}
      </DialogContent>
    </Dialog>
  );
}
