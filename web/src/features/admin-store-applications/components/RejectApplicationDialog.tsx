// F2.24.C7: reject dialog for a pending store application.
//
// Collects a required, non-blank rejection reason and submits ONLY
// `{ rejection_reason }` (no reviewer/store/user fields — the backend
// stamps the reviewer from the authenticated admin and forbids extras).
//
// Outcome handling:
//   - success → auto-close (the detail query invalidates; the page then
//               reflects the rejected status + reason)
//   - 409     → friendly "no longer pending" conflict copy
//   - 422     → the backend validation message
//   - other   → safe generic error
//
// Pattern mirrors StoreLifecycleDialog: controlled open state, reset on
// (re)open, auto-close on success, inline accessible error.

import { useEffect, useState } from "react";

import { getApiErrorMessage, isApiError } from "@/api";
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
import { Textarea } from "@/components/ui/textarea";

import { useRejectStoreApplicationMutation } from "../hooks";
import type { StoreApplicationDetail } from "../types";

const CONFLICT_MESSAGE =
  "This application is no longer pending review. Refresh to see the latest status.";
const GENERIC_MESSAGE =
  "Something went wrong while rejecting this application. Please try again.";

function rejectErrorMessage(error: unknown): string {
  if (isApiError(error)) {
    if (error.status === 409) return CONFLICT_MESSAGE;
    if (error.status === 422) return getApiErrorMessage(error);
  }
  return GENERIC_MESSAGE;
}

export interface RejectApplicationDialogProps {
  application: StoreApplicationDetail | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function RejectApplicationDialog({
  application,
  open,
  onOpenChange,
}: RejectApplicationDialogProps) {
  const [reason, setReason] = useState("");
  const reject = useRejectStoreApplicationMutation();

  // Auto-close once the rejection lands; the page reflects the new state
  // via cache invalidation.
  useEffect(() => {
    if (reject.isSuccess && open) {
      onOpenChange(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reject.isSuccess]);

  // Reset the field + stale mutation state whenever the dialog (re)opens
  // for a row.
  useEffect(() => {
    if (open) {
      setReason("");
      reject.reset();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, application?.id]);

  const trimmed = reason.trim();
  const canSubmit = trimmed.length > 0 && !reject.isPending && application !== null;

  const handleConfirm = () => {
    if (!canSubmit || application === null) return;
    reject.mutate({
      applicationId: application.id,
      body: { rejection_reason: trimmed },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="sm:max-w-md"
        data-testid="reject-application-dialog"
      >
        <DialogHeader>
          <DialogTitle>Reject application</DialogTitle>
          <DialogDescription>
            Provide a reason for rejecting this merchant application. The
            reason is recorded with the application.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-2">
          <Label htmlFor="reject-application-reason">Rejection reason</Label>
          <Textarea
            id="reject-application-reason"
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            placeholder="Explain why this application is being rejected"
            rows={4}
            disabled={reject.isPending}
            data-testid="reject-application-reason"
          />
        </div>

        {reject.isError ? (
          <p
            role="alert"
            aria-live="polite"
            className="text-sm text-destructive"
            data-testid="reject-application-error"
          >
            {rejectErrorMessage(reject.error)}
          </p>
        ) : null}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={reject.isPending}
            data-testid="reject-application-cancel"
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={handleConfirm}
            disabled={!canSubmit}
            data-testid="reject-application-confirm"
          >
            {reject.isPending ? "Rejecting…" : "Reject application"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
