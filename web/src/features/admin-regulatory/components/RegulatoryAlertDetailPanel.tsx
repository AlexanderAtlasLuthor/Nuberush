// F2.26.6.D: alert detail review panel (inline region, not a modal).
//
// Reads a single alert via useAdminRegulatoryAlert(alertId) and renders
// loading / error / not-found / success states. On success it shows the full
// alert record plus the lifecycle action controls (RegulatoryAlertActions).
//
// Read scope for this subphase: the single-alert detail ONLY. It does NOT
// query the decision trail (no useAdminRegulatoryAlertDecisions) and renders
// no decision-history panel.

import type { ReactNode } from "react";
import { X } from "lucide-react";

import { getApiErrorMessage } from "@/api";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";

import { useAdminRegulatoryAlert } from "../hooks";
import type { ComplianceAlert } from "../types";
import { EM_DASH, formatTimestamp, idOrDash } from "../format";
import {
  RegulatoryRecommendedActionBadge,
  RegulatorySeverityBadge,
  RegulatoryStatusBadge,
} from "./RegulatoryAlertBadges";
import { RegulatoryAlertActions } from "./RegulatoryAlertActions";

export interface RegulatoryAlertDetailPanelProps {
  alertId: string;
  onClose: () => void;
}

function Field({
  label,
  value,
  mono = false,
  testId,
}: {
  label: string;
  value: ReactNode;
  mono?: boolean;
  testId: string;
}) {
  return (
    <div className="space-y-0.5">
      <span className="block text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span
        className={
          mono ? "block font-mono text-xs break-all" : "block text-sm"
        }
        data-testid={testId}
      >
        {value}
      </span>
    </div>
  );
}

function DetailBody({ alert }: { alert: ComplianceAlert }) {
  return (
    <div className="space-y-5" data-testid="regulatory-detail-body">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Field label="Alert ID" value={alert.id} mono testId="regulatory-detail-id" />
        <Field
          label="Product ID"
          value={alert.product_id === null ? EM_DASH : alert.product_id}
          mono
          testId="regulatory-detail-product-id"
        />
        <Field
          label="Notice ID"
          value={idOrDash(alert.notice_id)}
          mono
          testId="regulatory-detail-notice-id"
        />
        <Field
          label="Match ID"
          value={alert.match_id === null ? EM_DASH : alert.match_id}
          mono
          testId="regulatory-detail-match-id"
        />
        <Field
          label="Severity"
          value={<RegulatorySeverityBadge severity={alert.severity} />}
          testId="regulatory-detail-severity"
        />
        <Field
          label="Status"
          value={<RegulatoryStatusBadge status={alert.status} />}
          testId="regulatory-detail-status"
        />
        <Field
          label="Recommended action"
          value={
            <RegulatoryRecommendedActionBadge
              recommendedAction={alert.recommended_action}
            />
          }
          testId="regulatory-detail-recommended-action"
        />
        <Field
          label="Created"
          value={formatTimestamp(alert.created_at)}
          mono
          testId="regulatory-detail-created"
        />
        <Field
          label="Updated"
          value={formatTimestamp(alert.updated_at)}
          mono
          testId="regulatory-detail-updated"
        />
        <Field
          label="Resolved"
          value={formatTimestamp(alert.resolved_at)}
          mono
          testId="regulatory-detail-resolved"
        />
        <Field
          label="Resolved by"
          value={
            alert.resolved_by_user_id === null
              ? EM_DASH
              : alert.resolved_by_user_id
          }
          mono
          testId="regulatory-detail-resolved-by"
        />
        <Field
          label="Resolution note"
          value={
            alert.resolution_note === null || alert.resolution_note.length === 0
              ? EM_DASH
              : alert.resolution_note
          }
          testId="regulatory-detail-resolution-note"
        />
      </div>

      <RegulatoryAlertActions alert={alert} />
    </div>
  );
}

export function RegulatoryAlertDetailPanel({
  alertId,
  onClose,
}: RegulatoryAlertDetailPanelProps) {
  const query = useAdminRegulatoryAlert(alertId);

  return (
    <section
      aria-label="Alert detail"
      className="rounded-xl border border-border bg-card p-4 md:p-6"
      data-testid="regulatory-detail-panel"
    >
      <div className="flex items-start justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold tracking-tight">Alert review</h2>
          <p className="text-sm text-muted-foreground">
            Review this alert and record an explicit decision. Recommendations
            are advisory.
          </p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="sm"
          onClick={onClose}
          data-testid="regulatory-detail-close"
        >
          <X className="mr-1 h-4 w-4" aria-hidden="true" />
          Close
        </Button>
      </div>

      <div className="mt-4">
        {query.isLoading ? (
          <LoadingState message="Loading alert…" />
        ) : query.isError ? (
          <ErrorState
            title="Could not load alert"
            message={getApiErrorMessage(query.error)}
            onRetry={() => {
              void query.refetch();
            }}
          />
        ) : query.data ? (
          <DetailBody alert={query.data} />
        ) : (
          <p
            className="text-sm text-muted-foreground"
            data-testid="regulatory-detail-missing"
          >
            Alert not found.
          </p>
        )}
      </div>
    </section>
  );
}
