// Admin-only approve / reject panel for the product detail page.
//
// Pure presentational + mutation wiring. Surfaces the proposal state
// (proposed_by_store_id, proposed_by_user_id, reviewed_*) so the
// reviewing admin sees the full provenance, then offers two actions:
//
//   - Approve  → POST /products/{id}/approve
//   - Reject   → POST /products/{id}/reject  (requires reason)
//
// Reject requires a non-empty reason; the button stays disabled until
// the textarea has content. Both mutations share their loading /
// error state through the inline alert area — the same pattern as
// UpdateProductComplianceModal.
//
// We mount this panel unconditionally on the admin detail surface;
// the backend is the security authority for who can hit the
// underlying endpoints (admin only). A non-admin who somehow lands
// here gets ApiError(403) on click, surfaced in the alert.

import { useState, type FormEvent } from "react";

import { getApiErrorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

import { ProductApprovalBadge } from "@/features/products/components/ProductApprovalBadge";
import {
  useApproveProductMutation,
  useRejectProductMutation,
} from "@/features/products/hooks";

import type { Product } from "../types";

const EM_DASH = "—";

interface AdminProductApprovalPanelProps {
  product: Product;
}

function MetaRow({
  label,
  value,
  testId,
}: {
  label: string;
  value: string;
  testId?: string;
}) {
  return (
    <div className="grid grid-cols-[160px_1fr] gap-2 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <span
        className="font-mono break-all text-foreground"
        data-testid={testId}
      >
        {value}
      </span>
    </div>
  );
}

export function AdminProductApprovalPanel({
  product,
}: AdminProductApprovalPanelProps) {
  const approve = useApproveProductMutation();
  const reject = useRejectProductMutation();
  const [reason, setReason] = useState("");

  const handleApprove = () => {
    approve.mutate({ productId: product.id });
  };

  const handleReject = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const trimmed = reason.trim();
    if (trimmed.length === 0) return;
    reject.mutate(
      { productId: product.id, body: { reason: trimmed } },
      {
        onSuccess: () => {
          setReason("");
        },
      },
    );
  };

  const isApproving = approve.isPending;
  const isRejecting = reject.isPending;
  const isBusy = isApproving || isRejecting;

  const trimmedReason = reason.trim();
  const canSubmitReject = trimmedReason.length > 0 && !isBusy;

  const errorSource = approve.isError
    ? approve.error
    : reject.isError
      ? reject.error
      : null;

  return (
    <section
      className="rounded-md border border-border bg-card p-4 space-y-4"
      aria-label="Product approval"
      data-testid="admin-product-approval-panel"
    >
      <header className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-base font-semibold">Approval</h2>
          <p className="text-sm text-muted-foreground">
            Curate the catalog: approve a store proposal to publish it,
            or reject it with a reason that the proposing store can see.
          </p>
        </div>
        <ProductApprovalBadge status={product.approval_status} />
      </header>

      <div className="space-y-1">
        <MetaRow
          label="Proposed by store"
          value={product.proposed_by_store_id ?? EM_DASH}
          testId="admin-product-approval-proposed-store"
        />
        <MetaRow
          label="Proposed by user"
          value={product.proposed_by_user_id ?? EM_DASH}
          testId="admin-product-approval-proposed-user"
        />
        <MetaRow
          label="Reviewed by"
          value={product.reviewed_by_user_id ?? EM_DASH}
          testId="admin-product-approval-reviewed-by"
        />
        <MetaRow
          label="Reviewed at"
          value={product.reviewed_at ?? EM_DASH}
          testId="admin-product-approval-reviewed-at"
        />
        {product.rejection_reason !== null ? (
          <MetaRow
            label="Rejection reason"
            value={product.rejection_reason}
            testId="admin-product-approval-rejection-reason"
          />
        ) : null}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Button
          type="button"
          size="sm"
          onClick={handleApprove}
          disabled={isBusy || product.approval_status === "approved"}
          data-testid="admin-product-approve-button"
        >
          {isApproving ? "Approving…" : "Approve"}
        </Button>
        <span className="text-xs text-muted-foreground">
          {product.approval_status === "approved"
            ? "Already approved. Re-approving updates the reviewer and timestamp."
            : "Approving publishes this product to every store."}
        </span>
      </div>

      <form onSubmit={handleReject} className="space-y-2" noValidate>
        <Label htmlFor="admin-product-reject-reason">
          Reject reason <span className="text-destructive">*</span>
        </Label>
        <Textarea
          id="admin-product-reject-reason"
          value={reason}
          onChange={(e) => setReason(e.target.value)}
          disabled={isBusy}
          rows={3}
          placeholder="Why is this proposal being rejected?"
          data-testid="admin-product-reject-reason"
        />
        <div className="flex items-center gap-2">
          <Button
            type="submit"
            size="sm"
            variant="destructive"
            disabled={!canSubmitReject}
            data-testid="admin-product-reject-button"
          >
            {isRejecting ? "Rejecting…" : "Reject"}
          </Button>
          <span className="text-xs text-muted-foreground">
            Reason is stored on the product so the proposing store can
            see why their submission was declined.
          </span>
        </div>
      </form>

      {errorSource !== null ? (
        <p
          role="alert"
          aria-live="polite"
          className={cn("text-sm text-destructive")}
          data-testid="admin-product-approval-error"
        >
          {getApiErrorMessage(errorSource)}
        </p>
      ) : null}
    </section>
  );
}
