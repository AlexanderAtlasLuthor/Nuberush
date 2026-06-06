// F2.26.6.C: mobile card stack for the regulatory alerts read surface.
//
// Pure presentational, small-screens-only (`md:hidden`). Same data as the
// desktop table, one card per alert. The "Review" affordance is a static,
// disabled button for this subphase — no detail panel, no mutation.

import { Button } from "@/components/ui/button";

import type { ComplianceAlert } from "../types";
import { EM_DASH, formatTimestamp, idOrDash } from "../format";
import {
  RegulatoryRecommendedActionBadge,
  RegulatorySeverityBadge,
  RegulatoryStatusBadge,
} from "./RegulatoryAlertBadges";

export interface RegulatoryAlertsMobileCardsProps {
  alerts: ComplianceAlert[];
}

export function RegulatoryAlertsMobileCards({
  alerts,
}: RegulatoryAlertsMobileCardsProps) {
  return (
    <ul
      className="md:hidden space-y-3"
      data-testid="regulatory-alerts-cards"
      aria-label="Regulatory alerts"
    >
      {alerts.map((alert) => (
        <li
          key={alert.id}
          className="rounded-xl border border-border bg-card p-4"
          data-testid="regulatory-alert-card"
          data-alert-id={alert.id}
        >
          <div className="flex items-center gap-2 flex-wrap">
            <RegulatorySeverityBadge severity={alert.severity} />
            <RegulatoryStatusBadge status={alert.status} />
            <span
              className="ml-auto text-[10px] font-mono text-muted-foreground"
              data-testid="regulatory-card-created"
            >
              {formatTimestamp(alert.created_at)}
            </span>
          </div>

          <div className="mt-2.5">
            <RegulatoryRecommendedActionBadge
              recommendedAction={alert.recommended_action}
            />
          </div>

          <dl className="mt-3 space-y-1 text-xs">
            <div className="flex items-center gap-1.5">
              <dt className="text-muted-foreground">Product ID</dt>
              <dd
                className="font-mono break-all"
                data-testid="regulatory-card-product-id"
              >
                {alert.product_id === null ? EM_DASH : idOrDash(alert.product_id)}
              </dd>
            </div>
            <div className="flex items-center gap-1.5">
              <dt className="text-muted-foreground">Notice ID</dt>
              <dd
                className="font-mono break-all"
                data-testid="regulatory-card-notice-id"
              >
                {idOrDash(alert.notice_id)}
              </dd>
            </div>
            <div className="flex items-center gap-1.5">
              <dt className="text-muted-foreground">Resolved</dt>
              <dd
                className="font-mono text-muted-foreground"
                data-testid="regulatory-card-resolved"
              >
                {formatTimestamp(alert.resolved_at)}
              </dd>
            </div>
          </dl>

          <div className="mt-3 flex justify-end">
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled
              aria-disabled="true"
              title="Alert review opens in a later update"
              data-testid="regulatory-card-review"
            >
              Review
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}
