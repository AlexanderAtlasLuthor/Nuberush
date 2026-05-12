// F2.19.6: presentational badge for an alert's severity.
//
// Pure presentational — no fetching, no context. Renders one of
// the three locked `AdminOperationsAlertSeverity` values with a
// visual variant that escalates with the severity (destructive for
// high, default for medium, secondary for low).

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
  return (
    <Badge
      variant={VARIANT[severity]}
      data-testid={`alert-severity-${severity}`}
    >
      {LABEL[severity]}
    </Badge>
  );
}
