// Read-only badge for ProductApprovalStatus.
//
// Pure presentational: wire enum → colour. Renders verbatim. The badge
// mirrors the visual language of ProductComplianceBadge (lowercase
// enum value, uppercased on display) so the two badges read at the
// same glance density.

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { ProductApprovalStatus } from "../types";

interface ProductApprovalBadgeProps {
  status: ProductApprovalStatus;
  className?: string;
}

const VARIANT: Record<ProductApprovalStatus, string> = {
  pending:
    "border-transparent bg-amber-100 text-amber-900 hover:bg-amber-100",
  approved:
    "border-transparent bg-emerald-100 text-emerald-900 hover:bg-emerald-100",
  rejected:
    "border-transparent bg-red-100 text-red-900 hover:bg-red-100",
};

export function ProductApprovalBadge({
  status,
  className,
}: ProductApprovalBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn(VARIANT[status], "uppercase tracking-wide", className)}
      data-testid={`product-approval-${status}`}
    >
      {status}
    </Badge>
  );
}
