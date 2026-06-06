// F2.26.6.C/D: desktop table for the regulatory alerts read surface.
//
// Pure presentational, desktop-only (`hidden md:block`). Renders one row per
// alert. The "Review" button opens the detail panel for ANY alert (including
// terminal ones — they can still be reviewed) via the `onReview` callback; it
// performs no mutation itself.
//
// Missing product_id / notice_id / resolved_at render the EM_DASH placeholder.

import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import type { ComplianceAlert } from "../types";
import { EM_DASH, formatTimestamp, idOrDash } from "../format";
import {
  RegulatoryRecommendedActionBadge,
  RegulatorySeverityBadge,
  RegulatoryStatusBadge,
} from "./RegulatoryAlertBadges";

const HEAD_CLASS = "text-[10px] font-semibold uppercase tracking-wider";

export interface RegulatoryAlertsTableProps {
  alerts: ComplianceAlert[];
  onReview: (alertId: string) => void;
}

export function RegulatoryAlertsTable({
  alerts,
  onReview,
}: RegulatoryAlertsTableProps) {
  return (
    <div
      className="hidden md:block rounded-xl border border-border bg-card overflow-hidden"
      data-testid="regulatory-alerts-table"
    >
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className={HEAD_CLASS}>Severity</TableHead>
            <TableHead className={HEAD_CLASS}>Status</TableHead>
            <TableHead className={HEAD_CLASS}>Recommended action</TableHead>
            <TableHead className={HEAD_CLASS}>Product ID</TableHead>
            <TableHead className={HEAD_CLASS}>Notice ID</TableHead>
            <TableHead className={HEAD_CLASS}>Created</TableHead>
            <TableHead className={HEAD_CLASS}>Resolved</TableHead>
            <TableHead className={`text-right ${HEAD_CLASS}`}>Review</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {alerts.map((alert) => (
            <TableRow
              key={alert.id}
              data-testid="regulatory-alert-row"
              data-alert-id={alert.id}
            >
              <TableCell data-testid="regulatory-row-severity">
                <RegulatorySeverityBadge severity={alert.severity} />
              </TableCell>
              <TableCell data-testid="regulatory-row-status">
                <RegulatoryStatusBadge status={alert.status} />
              </TableCell>
              <TableCell data-testid="regulatory-row-recommended-action">
                <RegulatoryRecommendedActionBadge
                  recommendedAction={alert.recommended_action}
                />
              </TableCell>
              <TableCell
                className="font-mono text-xs break-all"
                data-testid="regulatory-row-product-id"
              >
                {alert.product_id === null ? (
                  <span className="text-muted-foreground">{EM_DASH}</span>
                ) : (
                  idOrDash(alert.product_id)
                )}
              </TableCell>
              <TableCell
                className="font-mono text-xs break-all"
                data-testid="regulatory-row-notice-id"
              >
                {idOrDash(alert.notice_id)}
              </TableCell>
              <TableCell
                className="font-mono text-xs text-muted-foreground whitespace-nowrap"
                data-testid="regulatory-row-created"
              >
                {formatTimestamp(alert.created_at)}
              </TableCell>
              <TableCell
                className="font-mono text-xs text-muted-foreground whitespace-nowrap"
                data-testid="regulatory-row-resolved"
              >
                {formatTimestamp(alert.resolved_at)}
              </TableCell>
              <TableCell className="text-right">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => onReview(alert.id)}
                  data-testid="regulatory-row-review"
                >
                  Review
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
