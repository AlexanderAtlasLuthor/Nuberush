// F2.24.C7: approve action panel for a pending store application.
//
// Self-contained confirm + submit surface. Owns the approve mutation,
// disables duplicate clicks while pending, and renders the outcome:
//   - success → success message + provisioned store/owner ids
//   - 409     → friendly "no longer pending" conflict copy
//   - other   → safe generic error
//
// The frontend NEVER supplies role/store/user/Auth fields — approval is
// entirely server-owned (see api.ts). This panel only signals intent.

import { isApiError } from "@/api";
import { Button } from "@/components/ui/button";

import { useApproveStoreApplicationMutation } from "../hooks";
import type { StoreApplicationDetail } from "../types";

const CONFLICT_MESSAGE =
  "This application is no longer pending review. Refresh to see the latest status.";
const GENERIC_MESSAGE =
  "Something went wrong while approving this application. Please try again.";

function approveErrorMessage(error: unknown): string {
  if (isApiError(error) && error.status === 409) return CONFLICT_MESSAGE;
  return GENERIC_MESSAGE;
}

export interface ApproveApplicationPanelProps {
  application: StoreApplicationDetail;
}

export function ApproveApplicationPanel({
  application,
}: ApproveApplicationPanelProps) {
  const approve = useApproveStoreApplicationMutation();

  const handleApprove = () => {
    if (approve.isPending || approve.isSuccess) return;
    approve.mutate({ applicationId: application.id });
  };

  const result = approve.data;

  return (
    <div
      className="space-y-3 rounded-lg border border-border p-4"
      data-testid="approve-application-panel"
    >
      <div>
        <h3 className="font-semibold">Approve application</h3>
        <p className="text-sm text-muted-foreground">
          Approving provisions a store and an owner account, then marks the
          application approved. This cannot be undone from here.
        </p>
      </div>

      {approve.isSuccess ? (
        <div
          className="space-y-1 text-sm"
          role="status"
          aria-live="polite"
          data-testid="approve-application-success"
        >
          <p className="font-medium text-emerald-700">
            {result?.message ?? "Application approved."}
          </p>
          {result?.provisioned_store_id ? (
            <p className="text-muted-foreground">
              Store id:{" "}
              <span
                className="font-mono"
                data-testid="approve-provisioned-store-id"
              >
                {result.provisioned_store_id}
              </span>
            </p>
          ) : null}
          {result?.provisioned_owner_user_id ? (
            <p className="text-muted-foreground">
              Owner id:{" "}
              <span
                className="font-mono"
                data-testid="approve-provisioned-owner-id"
              >
                {result.provisioned_owner_user_id}
              </span>
            </p>
          ) : null}
        </div>
      ) : null}

      {approve.isError ? (
        <p
          role="alert"
          aria-live="polite"
          className="text-sm text-destructive"
          data-testid="approve-application-error"
        >
          {approveErrorMessage(approve.error)}
        </p>
      ) : null}

      {!approve.isSuccess ? (
        <Button
          type="button"
          onClick={handleApprove}
          disabled={approve.isPending}
          data-testid="approve-application-button"
        >
          {approve.isPending ? "Approving…" : "Approve application"}
        </Button>
      ) : null}
    </div>
  );
}
