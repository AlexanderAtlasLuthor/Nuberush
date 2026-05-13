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
  /** Optional. Fired after a successful navigation click — used to close the mobile drawer. */
  onNavigate?: () => void;
}

export function NavItem({
  href,
  label,
  icon: Icon,
  exact,
  description,
  disabled = false,
  badge,
  onNavigate,
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
          return;
        }
        onNavigate?.();
      }}
      className={({ isActive }) =>
        cn(
          "group relative w-full flex items-center gap-3 px-2.5 py-2 rounded-md text-[13px] font-medium transition-colors",
          disabled && "pointer-events-none opacity-50",
          isActive
            ? "bg-primary/15 text-primary"
            : "text-muted-foreground hover:text-foreground hover:bg-secondary/60",
        )
      }
    >
      {({ isActive }) => (
        <>
          <Icon className="w-4 h-4 shrink-0" aria-hidden="true" />
          <span className="truncate flex-1">{label}</span>
          {badge ? (
            <span
              className={cn(
                "inline-flex items-center justify-center min-w-[18px] h-[18px] rounded-full px-1 text-[10px] font-medium tabular-nums",
                isActive
                  ? "bg-primary/20 text-primary"
                  : "bg-secondary text-foreground",
              )}
            >
              {badge}
            </span>
          ) : null}
          {isActive ? (
            <span
              className="w-1 h-4 rounded-full bg-primary shrink-0"
              aria-hidden="true"
            />
          ) : null}
        </>
      )}
    </NavLink>
  );
}
