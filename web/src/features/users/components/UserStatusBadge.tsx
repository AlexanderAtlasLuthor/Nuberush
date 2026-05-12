// F2.15.5: read-only active/inactive badge for users.
//
// Mirrors `User.is_active` verbatim. Inspired by ProductStatusBadge —
// same shape so the two read consistently when an admin scans both
// surfaces. No client-side derivation; the backend owns the column.

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface UserStatusBadgeProps {
  isActive: boolean;
  className?: string;
}

export function UserStatusBadge({
  isActive,
  className,
}: UserStatusBadgeProps) {
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
        isActive ? "user-status-active" : "user-status-inactive"
      }
    >
      {isActive ? "Active" : "Inactive"}
    </Badge>
  );
}
