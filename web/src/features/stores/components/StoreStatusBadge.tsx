// F2.18.3: read-only active/inactive badge for admin stores.
//
// Mirrors `StoreProfile.is_active` verbatim. Shape and styling kept in
// lockstep with `UserStatusBadge` so admins scanning both surfaces get
// a consistent visual cue. No client-side derivation; the backend
// owns the column.

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface StoreStatusBadgeProps {
  isActive: boolean;
  className?: string;
}

export function StoreStatusBadge({
  isActive,
  className,
}: StoreStatusBadgeProps) {
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
        isActive ? "store-status-active" : "store-status-inactive"
      }
    >
      {isActive ? "Active" : "Inactive"}
    </Badge>
  );
}
