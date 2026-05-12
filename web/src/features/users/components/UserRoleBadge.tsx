// F2.15.5: read-only role badge.
//
// Pure projection of `UserRole`. Maps the wire enum to a human label.
// Does NOT decide permissions, hide roles, or branch on the caller's
// own role — backend matrices in `app/core/permissions.py` are the
// single source of truth and surface 401 / 403 / 422 for the UI to
// render. This badge only displays what the wire said.

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { UserRole } from "../types";

interface UserRoleBadgeProps {
  role: UserRole;
  className?: string;
}

const ROLE_LABEL: Readonly<Record<UserRole, string>> = {
  admin: "Admin",
  owner: "Owner",
  manager: "Manager",
  staff: "Staff",
  driver: "Driver",
};

// Each role gets a distinct visual cue so a reader can scan the column
// at a glance. Colors are conservative variations of the same neutral
// palette already used elsewhere in this app — no new design tokens.
const ROLE_CLASS: Readonly<Record<UserRole, string>> = {
  admin:
    "border-transparent bg-purple-100 text-purple-900 hover:bg-purple-100",
  owner:
    "border-transparent bg-indigo-100 text-indigo-900 hover:bg-indigo-100",
  manager:
    "border-transparent bg-sky-100 text-sky-900 hover:bg-sky-100",
  staff:
    "border-transparent bg-emerald-100 text-emerald-900 hover:bg-emerald-100",
  driver:
    "border-transparent bg-amber-100 text-amber-900 hover:bg-amber-100",
};

export function UserRoleBadge({ role, className }: UserRoleBadgeProps) {
  return (
    <Badge
      variant="outline"
      className={cn(
        "uppercase tracking-wide",
        ROLE_CLASS[role],
        className,
      )}
      data-testid={`user-role-badge-${role}`}
      aria-label={`Role: ${ROLE_LABEL[role]}`}
    >
      {ROLE_LABEL[role]}
    </Badge>
  );
}
