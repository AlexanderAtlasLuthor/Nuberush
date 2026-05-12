// F2.16.5: visual badge for the audit event source.
//
// Pure presentational component. Takes the wire-shape `AuditSource`
// value and renders a human label inside a styled `Badge`. No
// hooks, no derived data beyond the source-to-label map locked
// below, no fake variants.
//
// Locked labels (matches the F2.16 prompt):
//   - inventory          → "Inventory"
//   - order              → "Order"
//   - product_compliance → "Compliance"
//
// Variant choice keeps the three sources visually distinct without
// inventing a "severity" or "status" semantic that doesn't exist
// on the wire.

import { Badge } from "@/components/ui/badge";

import type { AuditSource } from "../types";

const SOURCE_LABEL: Record<AuditSource, string> = {
  inventory: "Inventory",
  order: "Order",
  product_compliance: "Compliance",
};

const SOURCE_VARIANT: Record<
  AuditSource,
  "default" | "secondary" | "outline"
> = {
  inventory: "secondary",
  order: "default",
  product_compliance: "outline",
};

export interface AuditEventBadgeProps {
  source: AuditSource;
  className?: string;
}

export function AuditEventBadge({
  source,
  className,
}: AuditEventBadgeProps) {
  return (
    <Badge
      variant={SOURCE_VARIANT[source]}
      className={className}
      data-testid={`audit-event-badge-${source}`}
      data-source={source}
      aria-label={`Audit source: ${SOURCE_LABEL[source]}`}
    >
      {SOURCE_LABEL[source]}
    </Badge>
  );
}
