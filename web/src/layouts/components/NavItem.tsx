// F2.5: single sidebar nav row.
//
// Presentational. Wraps NavLink so react-router-dom owns the active
// state — no manual `pathname === href` comparisons (those drift the
// moment a route grows nested children).

import { NavLink } from "react-router-dom";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItemProps {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Pass true for index routes so the link doesn't match every nested path. */
  exact?: boolean;
  /** Optional, surfaced as title= for desktop hover and aria-description. */
  description?: string;
  disabled?: boolean;
  badge?: string;
}

export function NavItem({
  href,
  label,
  icon: Icon,
  exact,
  description,
  disabled = false,
  badge,
}: NavItemProps) {
  return (
    <NavLink
      to={href}
      end={exact}
      title={description}
      aria-disabled={disabled || undefined}
      tabIndex={disabled ? -1 : undefined}
      onClick={(event) => {
        if (disabled) {
          event.preventDefault();
        }
      }}
      className={({ isActive }) =>
        cn(
          "flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors",
          disabled && "pointer-events-none opacity-50",
          isActive
            ? "bg-primary text-primary-foreground"
            : "text-muted-foreground hover:text-foreground hover:bg-secondary",
        )
      }
    >
      <Icon className="w-4 h-4 shrink-0" aria-hidden="true" />
      <span className="truncate">{label}</span>
      {badge ? (
        <span className="ml-auto rounded bg-secondary px-1.5 py-0.5 text-xs">
          {badge}
        </span>
      ) : null}
    </NavLink>
  );
}
