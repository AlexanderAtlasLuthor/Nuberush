// F2.8.3: read-only active/inactive badge.
//
// Reflects the `is_active` boolean column verbatim. Not the same as the
// "sellable" rule — sellability is a server-side composite the backend
// owns; this component is a single-flag projection only.

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface ProductStatusBadgeProps {
  isActive: boolean;
  className?: string;
}

export function ProductStatusBadge({
  isActive,
  className,
}: ProductStatusBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "uppercase tracking-wide",
        isActive
          ? "border-transparent bg-emerald-100 text-emerald-900 hover:bg-emerald-100"
          : "border-transparent bg-neutral-200 text-neutral-700 hover:bg-neutral-200",
        className,
      )}
      data-testid={
        isActive ? "product-status-active" : "product-status-inactive"
      }
    >
      {isActive ? "Active" : "Inactive"}
    </Badge>
  );
}
