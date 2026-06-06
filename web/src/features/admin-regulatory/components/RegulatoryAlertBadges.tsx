// F2.26.6.C: humanized badges for regulatory compliance alerts.
//
// Three small presentational badges that map the backend enum values to
// admin-facing copy + a Badge variant. Local to admin-regulatory (the label
// set is feature-specific). Each badge falls back to the raw value defensively
// so an unrecognized enum never renders blank.
//
// Read-only: badges carry no action, no mutation, no selection.

import { Badge } from "@/components/ui/badge";

import type {
  ComplianceAlertSeverity,
  ComplianceAlertStatus,
  ComplianceRecommendedAction,
} from "../types";

type BadgeVariant = "default" | "secondary" | "destructive" | "outline";

// --------------------------------------------------------------------- //
// Severity
// --------------------------------------------------------------------- //

const SEVERITY_LABEL: Record<ComplianceAlertSeverity, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  critical: "Critical",
};

const SEVERITY_VARIANT: Record<ComplianceAlertSeverity, BadgeVariant> = {
  low: "secondary",
  medium: "default",
  high: "destructive",
  critical: "destructive",
};

export function RegulatorySeverityBadge({
  severity,
}: {
  severity: ComplianceAlertSeverity;
}) {
  const label = SEVERITY_LABEL[severity] ?? severity;
  const variant = SEVERITY_VARIANT[severity] ?? "secondary";
  return (
    <Badge
      variant={variant}
      data-testid={`regulatory-severity-${severity}`}
      aria-label={`Severity: ${label}`}
    >
      {label}
    </Badge>
  );
}

// --------------------------------------------------------------------- //
// Status
// --------------------------------------------------------------------- //

const STATUS_LABEL: Record<ComplianceAlertStatus, string> = {
  open: "Open",
  acknowledged: "Acknowledged",
  actioned: "Actioned",
  dismissed: "Dismissed",
};

const STATUS_VARIANT: Record<ComplianceAlertStatus, BadgeVariant> = {
  open: "default",
  acknowledged: "secondary",
  actioned: "secondary",
  dismissed: "outline",
};

export function RegulatoryStatusBadge({
  status,
}: {
  status: ComplianceAlertStatus;
}) {
  const label = STATUS_LABEL[status] ?? status;
  const variant = STATUS_VARIANT[status] ?? "secondary";
  return (
    <Badge
      variant={variant}
      data-testid={`regulatory-status-${status}`}
      aria-label={`Status: ${label}`}
    >
      {label}
    </Badge>
  );
}

// --------------------------------------------------------------------- //
// Recommended action (advisory only)
// --------------------------------------------------------------------- //

const RECOMMENDED_ACTION_LABEL: Record<ComplianceRecommendedAction, string> = {
  none: "No action recommended",
  hold: "Hold recommended",
  ban: "Ban recommended",
};

const RECOMMENDED_ACTION_VARIANT: Record<
  ComplianceRecommendedAction,
  BadgeVariant
> = {
  none: "outline",
  hold: "default",
  ban: "destructive",
};

export function RegulatoryRecommendedActionBadge({
  recommendedAction,
}: {
  recommendedAction: ComplianceRecommendedAction;
}) {
  const label =
    RECOMMENDED_ACTION_LABEL[recommendedAction] ?? recommendedAction;
  const variant = RECOMMENDED_ACTION_VARIANT[recommendedAction] ?? "outline";
  return (
    <Badge
      variant={variant}
      data-testid={`regulatory-recommended-action-${recommendedAction}`}
      aria-label={`Recommended action: ${label}`}
    >
      {label}
    </Badge>
  );
}
