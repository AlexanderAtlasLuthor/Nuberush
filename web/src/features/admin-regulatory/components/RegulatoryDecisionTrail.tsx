// F2.26.6.E: decision trail (regulatory decision audit history) for one alert.
//
// Read-only history rendered inside the alert detail panel. Reads the
// append-only decision log via useAdminRegulatoryAlertDecisions(alertId) and
// shows loading / error / empty / success states. No mutation, no decision
// creation here — this is purely the audit trail for decisions already made
// through the lifecycle actions.
//
// before/after status are NOT direct columns: the backend stores a JSON
// snapshot of the human-reviewable alert fields in `before` / `after`
// (F2.26.6.A `_alert_snapshot`), whose `status` key we read defensively.

import { getApiErrorMessage } from "@/api";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";

import { useAdminRegulatoryAlertDecisions } from "../hooks";
import type {
  ComplianceAlertStatus,
  RegulatoryDecisionAction,
  RegulatoryDecisionAuditLog,
} from "../types";
import { EM_DASH, formatTimestamp } from "../format";
import { RegulatoryStatusBadge } from "./RegulatoryAlertBadges";

// Stable params reference so the query key (and cache slot) doesn't churn.
const DECISION_PARAMS = { limit: 25, offset: 0 } as const;

const ACTION_LABEL: Record<RegulatoryDecisionAction, string> = {
  alert_acknowledged: "Alert acknowledged",
  alert_dismissed: "Alert dismissed",
  alert_resolved_no_action: "Resolved with no action",
  alert_resolved_hold: "Resolved with hold",
  alert_resolved_ban: "Resolved with ban",
};

/** Humanize a decision action; never leak the raw enum to the UI. */
function actionLabel(action: RegulatoryDecisionAction): string {
  return ACTION_LABEL[action] ?? "Decision recorded";
}

const KNOWN_STATUSES: readonly string[] = [
  "open",
  "acknowledged",
  "actioned",
  "dismissed",
];

/** Read a `status` value from a JSON snapshot, only if it's a known status. */
function snapshotStatus(
  snapshot: Record<string, unknown> | null,
): ComplianceAlertStatus | null {
  const value = snapshot?.status;
  return typeof value === "string" && KNOWN_STATUSES.includes(value)
    ? (value as ComplianceAlertStatus)
    : null;
}

/** Safely stringify a single metadata value — never "[object Object]". */
function formatMetadataValue(value: unknown): string {
  if (value === null || value === undefined) return EM_DASH;
  if (
    typeof value === "string" ||
    typeof value === "number" ||
    typeof value === "boolean"
  ) {
    return String(value);
  }
  try {
    const json = JSON.stringify(value);
    if (json === undefined) return "Additional metadata recorded";
    return json.length > 120 ? "Additional metadata recorded" : json;
  } catch {
    return "Additional metadata recorded";
  }
}

interface MetadataEntry {
  key: string;
  value: string;
}

function summarizeMetadata(
  metadata: Record<string, unknown> | null,
): MetadataEntry[] | null {
  if (!metadata) return null;
  const entries = Object.entries(metadata);
  if (entries.length === 0) return null;
  return entries.map(([key, value]) => ({
    key,
    value: formatMetadataValue(value),
  }));
}

function StatusValue({ status }: { status: ComplianceAlertStatus | null }) {
  if (status === null) {
    return <span className="text-muted-foreground">{EM_DASH}</span>;
  }
  return <RegulatoryStatusBadge status={status} />;
}

function DecisionRow({ decision }: { decision: RegulatoryDecisionAuditLog }) {
  const beforeStatus = snapshotStatus(decision.before);
  const afterStatus = snapshotStatus(decision.after);
  const metadata = summarizeMetadata(decision.metadata);

  return (
    <li
      className="rounded-lg border border-border bg-background p-3"
      data-testid="regulatory-decision-row"
      data-decision-id={decision.id}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span
          className="text-sm font-semibold"
          data-testid="regulatory-decision-action"
        >
          {actionLabel(decision.action)}
        </span>
        <span
          className="font-mono text-[10px] text-muted-foreground"
          data-testid="regulatory-decision-created"
        >
          {formatTimestamp(decision.created_at)}
        </span>
      </div>

      <div
        className="mt-2 flex items-center gap-2 text-xs"
        data-testid="regulatory-decision-transition"
      >
        <span data-testid="regulatory-decision-before">
          <StatusValue status={beforeStatus} />
        </span>
        <span aria-hidden="true" className="text-muted-foreground">
          →
        </span>
        <span data-testid="regulatory-decision-after">
          <StatusValue status={afterStatus} />
        </span>
      </div>

      <dl className="mt-2 space-y-1 text-xs">
        <div className="flex flex-wrap gap-1.5">
          <dt className="text-muted-foreground">Actor</dt>
          <dd
            className="font-mono break-all"
            data-testid="regulatory-decision-actor"
          >
            {decision.actor_user_id}
          </dd>
        </div>
        <div className="flex flex-wrap gap-1.5">
          <dt className="text-muted-foreground">Reason</dt>
          <dd data-testid="regulatory-decision-reason">{decision.reason}</dd>
        </div>
        <div className="flex flex-col gap-1">
          <dt className="text-muted-foreground">Metadata</dt>
          <dd data-testid="regulatory-decision-metadata">
            {metadata === null ? (
              <span className="text-muted-foreground">
                No additional metadata.
              </span>
            ) : (
              <ul className="space-y-0.5">
                {metadata.map((entry) => (
                  <li key={entry.key} className="font-mono break-all">
                    <span className="text-muted-foreground">{entry.key}:</span>{" "}
                    {entry.value}
                  </li>
                ))}
              </ul>
            )}
          </dd>
        </div>
      </dl>
    </li>
  );
}

export interface RegulatoryDecisionTrailProps {
  alertId: string;
}

export function RegulatoryDecisionTrail({
  alertId,
}: RegulatoryDecisionTrailProps) {
  const query = useAdminRegulatoryAlertDecisions(alertId, DECISION_PARAMS);
  const items = query.data?.items ?? [];

  return (
    <section
      aria-label="Decision trail"
      className="space-y-3"
      data-testid="regulatory-decision-trail"
    >
      <h3 className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Decision trail
      </h3>

      {query.isLoading ? (
        <LoadingState message="Loading decision history…" />
      ) : query.isError ? (
        <ErrorState
          title="Could not load decision history"
          message={getApiErrorMessage(query.error)}
          onRetry={() => {
            void query.refetch();
          }}
        />
      ) : items.length === 0 ? (
        <p
          className="text-sm text-muted-foreground"
          data-testid="regulatory-decision-empty"
        >
          No decisions have been recorded for this alert yet.
        </p>
      ) : (
        <ul className="space-y-2" data-testid="regulatory-decision-list">
          {items.map((decision) => (
            <DecisionRow key={decision.id} decision={decision} />
          ))}
        </ul>
      )}
    </section>
  );
}
