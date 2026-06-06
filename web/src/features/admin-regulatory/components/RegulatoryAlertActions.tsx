// F2.26.6.D: lifecycle action controls for a single compliance alert.
//
// Non-terminal alerts (open / acknowledged) expose five explicit decisions;
// each opens the shared confirmation dialog (no decision fires without an
// explicit admin click, and never on mount). Terminal alerts (actioned /
// dismissed) show explanatory copy and no actionable controls.
//
// No bulk actions, no auto-actions.

import { useState } from "react";

import { Button } from "@/components/ui/button";

import type { ComplianceAlert } from "../types";
import {
  RegulatoryResolutionDialog,
  type RegulatoryLifecycleAction,
} from "./RegulatoryResolutionDialog";

const TERMINAL_COPY: Record<"actioned" | "dismissed", string> = {
  actioned:
    "This alert has already been actioned. Its decision is final and no further lifecycle action is available.",
  dismissed:
    "This alert has already been dismissed. No further lifecycle action is available.",
};

export interface RegulatoryAlertActionsProps {
  alert: ComplianceAlert;
}

export function RegulatoryAlertActions({ alert }: RegulatoryAlertActionsProps) {
  const [activeAction, setActiveAction] =
    useState<RegulatoryLifecycleAction | null>(null);

  const isTerminal = alert.status === "actioned" || alert.status === "dismissed";

  if (isTerminal) {
    return (
      <div
        className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm text-muted-foreground"
        data-testid="regulatory-terminal-note"
      >
        {TERMINAL_COPY[alert.status]}
      </div>
    );
  }

  return (
    <div className="space-y-3" data-testid="regulatory-alert-actions">
      <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Lifecycle actions
      </p>
      <div className="flex flex-wrap gap-2">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setActiveAction("acknowledge")}
          data-testid="regulatory-action-acknowledge"
        >
          Acknowledge
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setActiveAction("dismiss")}
          data-testid="regulatory-action-dismiss"
        >
          Dismiss
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setActiveAction("no_action")}
          data-testid="regulatory-action-resolve-no_action"
        >
          Resolve — no action
        </Button>
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={() => setActiveAction("hold")}
          data-testid="regulatory-action-resolve-hold"
        >
          Resolve — hold
        </Button>
        <Button
          type="button"
          variant="destructive"
          size="sm"
          onClick={() => setActiveAction("ban")}
          data-testid="regulatory-action-resolve-ban"
        >
          Resolve — ban
        </Button>
      </div>

      <RegulatoryResolutionDialog
        alert={alert}
        action={activeAction}
        onOpenChange={(open) => {
          if (!open) setActiveAction(null);
        }}
      />
    </div>
  );
}
