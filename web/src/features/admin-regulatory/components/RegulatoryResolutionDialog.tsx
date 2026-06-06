// F2.26.6.D: shared lifecycle-action confirmation dialog.
//
// One Radix Dialog drives all five explicit admin decisions on a compliance
// alert — acknowledge, dismiss, and the three resolve verbs (no_action / hold
// / ban). Every decision requires a non-empty reason/note and an explicit
// confirm click; nothing fires on open. hold/ban additionally surface the
// product-consequence copy BEFORE the confirm button.
//
// Mutations go exclusively through the F2.26.6.B hooks, which own cache
// invalidation (alert lists + this alert's detail + its decision trail). The
// frontend never mutates Product/Inventory directly.

import { useEffect, useState } from "react";

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
import { Textarea } from "@/components/ui/textarea";

import {
  useAcknowledgeAdminRegulatoryAlert,
  useDismissAdminRegulatoryAlert,
  useResolveAdminRegulatoryAlert,
} from "../hooks";
import type {
  ComplianceAlert,
  ComplianceAlertResolutionAction,
} from "../types";

/** The five explicit lifecycle decisions an admin may take from the panel. */
export type RegulatoryLifecycleAction =
  | "acknowledge"
  | "dismiss"
  | "no_action"
  | "hold"
  | "ban";

// Required consequence copy for the product-affecting resolutions. Shown
// before the confirm button; deliberately NOT phrased as "automatically
// blocked" and never implying irreversible deletion.
export const HOLD_CONSEQUENCE_COPY =
  "This will mark the product as restricted and not allowed for sale through the audited compliance service.";
export const BAN_CONSEQUENCE_COPY =
  "This will mark the product as banned and not allowed for sale. Existing inventory quarantine rules may apply.";

interface ActionConfig {
  title: string;
  description: string;
  noteLabel: string;
  notePlaceholder: string;
  confirmLabel: string;
  pendingLabel: string;
  confirmVariant: "default" | "destructive";
  consequence?: string;
}

const ACTION_CONFIG: Record<RegulatoryLifecycleAction, ActionConfig> = {
  acknowledge: {
    title: "Acknowledge alert",
    description: "Mark this alert as seen and under review. No compliance change is applied.",
    noteLabel: "Reason",
    notePlaceholder: "Why are you acknowledging this alert?",
    confirmLabel: "Acknowledge",
    pendingLabel: "Acknowledging…",
    confirmVariant: "default",
  },
  dismiss: {
    title: "Dismiss alert",
    description: "Close this alert without a compliance change. No product change is applied.",
    noteLabel: "Reason",
    notePlaceholder: "Why is this alert being dismissed?",
    confirmLabel: "Dismiss",
    pendingLabel: "Dismissing…",
    confirmVariant: "default",
  },
  no_action: {
    title: "Resolve — no action",
    description: "Close this alert as reviewed with no compliance change to the product.",
    noteLabel: "Resolution note",
    notePlaceholder: "Record why no action is needed.",
    confirmLabel: "Resolve",
    pendingLabel: "Resolving…",
    confirmVariant: "default",
  },
  hold: {
    title: "Resolve — hold product",
    description: "Resolve this alert and place a compliance hold on the product.",
    noteLabel: "Resolution note",
    notePlaceholder: "Record the reason for the hold.",
    confirmLabel: "Confirm hold",
    pendingLabel: "Applying hold…",
    confirmVariant: "default",
    consequence: HOLD_CONSEQUENCE_COPY,
  },
  ban: {
    title: "Resolve — ban product",
    description: "Resolve this alert and ban the product.",
    noteLabel: "Resolution note",
    notePlaceholder: "Record the reason for the ban.",
    confirmLabel: "Confirm ban",
    pendingLabel: "Applying ban…",
    confirmVariant: "destructive",
    consequence: BAN_CONSEQUENCE_COPY,
  },
};

export interface RegulatoryResolutionDialogProps {
  alert: ComplianceAlert;
  /** The active action; `null` keeps the dialog closed. */
  action: RegulatoryLifecycleAction | null;
  onOpenChange: (open: boolean) => void;
}

export function RegulatoryResolutionDialog({
  alert,
  action,
  onOpenChange,
}: RegulatoryResolutionDialogProps) {
  const acknowledge = useAcknowledgeAdminRegulatoryAlert();
  const dismiss = useDismissAdminRegulatoryAlert();
  const resolve = useResolveAdminRegulatoryAlert();

  const [note, setNote] = useState("");

  const open = action !== null;
  const mutation =
    action === "acknowledge"
      ? acknowledge
      : action === "dismiss"
        ? dismiss
        : resolve;

  // Reset the note + any prior mutation status whenever the dialog (re)opens
  // or the action changes, so a fresh decision never inherits stale state.
  useEffect(() => {
    if (open) {
      setNote("");
      acknowledge.reset();
      dismiss.reset();
      resolve.reset();
    }
    // Mutation refs are stable for the component's life; intentionally keyed
    // on the dialog identity only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, action, alert.id]);

  // Close (and thereby clear) on success. The hook already invalidated the
  // alert detail + lists, so the panel behind this dialog refetches.
  useEffect(() => {
    if (open && mutation.isSuccess) {
      onOpenChange(false);
    }
  }, [open, mutation.isSuccess, onOpenChange]);

  if (action === null) {
    return <Dialog open={false} onOpenChange={onOpenChange} />;
  }

  const config = ACTION_CONFIG[action];
  const trimmed = note.trim();
  const canSubmit = trimmed.length > 0 && !mutation.isPending;

  const handleConfirm = () => {
    if (trimmed.length === 0) return;
    if (action === "acknowledge") {
      acknowledge.mutate({ alertId: alert.id, body: { reason: trimmed } });
      return;
    }
    if (action === "dismiss") {
      dismiss.mutate({ alertId: alert.id, body: { reason: trimmed } });
      return;
    }
    // action is narrowed to the resolve verbs here.
    const resolveAction: ComplianceAlertResolutionAction = action;
    resolve.mutate({
      alertId: alert.id,
      body: { action: resolveAction, resolution_note: trimmed },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent data-testid="regulatory-resolution-dialog">
        <DialogHeader>
          <DialogTitle>{config.title}</DialogTitle>
          <DialogDescription>{config.description}</DialogDescription>
        </DialogHeader>

        {config.consequence ? (
          <p
            role="note"
            className="rounded-md border border-amber-300/60 bg-amber-50 px-3 py-2 text-sm text-amber-900 dark:border-amber-500/30 dark:bg-amber-950/40 dark:text-amber-200"
            data-testid="regulatory-consequence"
          >
            {config.consequence}
          </p>
        ) : null}

        <div className="space-y-2">
          <Label htmlFor="regulatory-resolution-note">{config.noteLabel}</Label>
          <Textarea
            id="regulatory-resolution-note"
            value={note}
            onChange={(event) => setNote(event.target.value)}
            placeholder={config.notePlaceholder}
            rows={4}
            disabled={mutation.isPending}
            data-testid="regulatory-resolution-note"
          />
        </div>

        {mutation.isError ? (
          <p
            role="alert"
            aria-live="polite"
            className="text-sm text-destructive"
            data-testid="regulatory-resolution-error"
          >
            {getApiErrorMessage(mutation.error)}
          </p>
        ) : null}

        <DialogFooter>
          <Button
            type="button"
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={mutation.isPending}
            data-testid="regulatory-resolution-cancel"
          >
            Cancel
          </Button>
          <Button
            type="button"
            variant={config.confirmVariant}
            onClick={handleConfirm}
            disabled={!canSubmit}
            data-testid="regulatory-resolution-confirm"
          >
            {mutation.isPending ? config.pendingLabel : config.confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
