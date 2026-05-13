// F2.19.6 / Phase E: presentational badge for an alert's severity.
//
// Pure presentational — no fetching, no context. Renders one of
// the three locked `AdminOperationsAlertSeverity` values with a
// visual variant that escalates with the severity (destructive for
// high, default for medium, secondary for low).
//
// Phase E polish:
//   - Defensive fallback when the wire carries a severity the
//     frontend doesn't recognize yet (e.g. a backend addition
//     shipped before the frontend updates). The badge falls back
//     to the neutral "secondary" variant and renders the raw
//     wire string verbatim instead of crashing.
//   - `aria-label` exposes the meaning to assistive tech so the
//     short visual label ("High") still reads as "Severity: High".

import { Badge } from "@/components/ui/badge";

import type { AdminOperationsAlertSeverity } from "../types";

const LABEL: Record<AdminOperationsAlertSeverity, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
};

const VARIANT: Record<
  AdminOperationsAlertSeverity,
  "default" | "secondary" | "destructive"
> = {
  low: "secondary",
  medium: "default",
  high: "destructive",
};

export interface AlertSeverityBadgeProps {
  severity: AdminOperationsAlertSeverity;
}

export function AlertSeverityBadge({ severity }: AlertSeverityBadgeProps) {
  // Neutral fallback for unrecognized severities. The label echoes
  // the raw wire string instead of inventing a friendly name.
  const label = LABEL[severity] ?? severity;
  const variant = VARIANT[severity] ?? "secondary";

  return (
    <Badge
      variant={variant}
      data-testid={`alert-severity-${severity}`}
      aria-label={`Severity: ${label}`}
    >
      {label}
    </Badge>
  );
}
