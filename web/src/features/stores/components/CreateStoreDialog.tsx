// F2.18.3: CreateStoreDialog.
//
// Inline form hosted in the project's standard Dialog. Submits via
// `useCreateStoreMutation` (which invalidates `adminStoresKeys.lists()`
// on success — the page does not need to refetch by hand).
//
// Pattern follows features/users/components/CreateUserModal.tsx +
// CreateUserForm.tsx, fused into one component because the body is
// tiny (3 fields) and there is no second caller.
//
// Validation policy:
//   UX-level only — non-empty trimmed name and code. The backend
//   re-validates (extra="forbid", duplicate code → 422). Errors are
//   surfaced verbatim via `getApiErrorMessage`.
//
// Auto-close behavior: when `mutation.isSuccess && data` fires, the
// dialog calls `onCreated(store)` and `onOpenChange(false)`. Closing
// unmounts the form, which resets every input — same UX as
// CreateUserModal.

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

import { useCreateStoreMutation } from "../hooks";
import type { StoreCreateRequest, StoreProfile } from "../types";

export interface CreateStoreDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Called once with the created store on a successful submit. */
  onCreated?: (store: StoreProfile) => void;
}

export function CreateStoreDialog({
  open,
  onOpenChange,
  onCreated,
}: CreateStoreDialogProps) {
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [timezone, setTimezone] = useState("");

  const mutation = useCreateStoreMutation();

  // Hand the created store up to the parent exactly once per success.
  // Effect-based propagation (rather than per-call `onSuccess`) keeps
  // the path resilient to a future caller driving the mutation via
  // mutateAsync from outside this component.
  useEffect(() => {
    if (mutation.isSuccess && mutation.data) {
      onCreated?.(mutation.data);
      onOpenChange(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mutation.isSuccess, mutation.data]);

  // Reset state when the dialog opens fresh so a previously-failed
  // submit does not leave a stale error on screen.
  useEffect(() => {
    if (open) {
      setName("");
      setCode("");
      setTimezone("");
      mutation.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  const trimmedName = name.trim();
  const trimmedCode = code.trim();
  const trimmedTimezone = timezone.trim();

  const isFormValid = trimmedName.length > 0 && trimmedCode.length > 0;
  const canSubmit = isFormValid && !mutation.isPending;

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit) return;

    const body: StoreCreateRequest = {
      name: trimmedName,
      code: trimmedCode,
    };
    if (trimmedTimezone.length > 0) {
      body.timezone = trimmedTimezone;
    }

    mutation.mutate({ body });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-lg"
        data-testid="create-store-dialog"
      >
        <DialogHeader>
          <DialogTitle>Create store</DialogTitle>
          <DialogDescription>
            The backend authorises the request, validates name / code
            uniqueness and the timezone string. This form only collects
            the input.
          </DialogDescription>
        </DialogHeader>
        <form
          onSubmit={handleSubmit}
          noValidate
          data-testid="create-store-form"
        >
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="create-store-name">
                Name <span className="text-destructive">*</span>
              </Label>
              <Input
                id="create-store-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                disabled={mutation.isPending}
                required
                data-testid="create-store-name"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="create-store-code">
                Code <span className="text-destructive">*</span>
              </Label>
              <Input
                id="create-store-code"
                value={code}
                onChange={(e) => setCode(e.target.value)}
                disabled={mutation.isPending}
                required
                data-testid="create-store-code"
              />
              <p className="text-xs text-muted-foreground">
                Short identifier. Must be unique across the platform.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="create-store-timezone">Timezone</Label>
              <Input
                id="create-store-timezone"
                value={timezone}
                onChange={(e) => setTimezone(e.target.value)}
                disabled={mutation.isPending}
                placeholder="America/New_York"
                data-testid="create-store-timezone"
              />
              <p className="text-xs text-muted-foreground">
                Optional. Defaults to America/New_York when omitted.
              </p>
            </div>

            {mutation.isError ? (
              <p
                role="alert"
                aria-live="polite"
                className="text-sm text-destructive"
                data-testid="create-store-error"
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
              data-testid="create-store-cancel"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!canSubmit}
              data-testid="create-store-submit"
            >
              {mutation.isPending ? "Creating…" : "Create store"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
