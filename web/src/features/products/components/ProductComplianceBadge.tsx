// F2.8.3: read-only badge for ProductComplianceStatus.
//
// Pure presentational mapping — wire enum → colour. NO business logic,
// NO derivations. The status string is taken verbatim from the wire and
// rendered with a colour the operator can scan at a glance.

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ProductComplianceStatus } from "../types";

interface ProductComplianceBadgeProps {
  status: ProductComplianceStatus;
  className?: string;
}

const VARIANT: Record<ProductComplianceStatus, string> = {
  allowed:
    "border-transparent bg-emerald-100 text-emerald-900 hover:bg-emerald-100",
  restricted:
    "border-transparent bg-amber-100 text-amber-900 hover:bg-amber-100",
  banned:
    "border-transparent bg-red-100 text-red-900 hover:bg-red-100",
};

export function ProductComplianceBadge({
  status,
  className,
}: ProductComplianceBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn(VARIANT[status], "uppercase tracking-wide", className)}
      data-testid={`product-compliance-${status}`}
    >
      {status}
    </Badge>
  );
}
