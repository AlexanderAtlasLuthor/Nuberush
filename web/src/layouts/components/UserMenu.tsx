// F2.5: account dropdown for the topbar.
//
// Reads the authenticated user via useAuth() and exposes a single
// destructive action: logout. Logout simply calls the existing
// AuthProvider.logout() which:
//   - clears the in-memory access-token holder
//   - sets user=null
// ProtectedRoute observes !isAuthenticated on the next render and
// Navigate-replaces to /login automatically — no manual redirect here.
//
// Display surface (read-only, never authoritative):
//   - full_name (or email fallback)
//   - email
//   - role badge (visual hint only — backend authorises every API call)

import { ChevronDown, LogOut, UserRound } from "lucide-react";
import { useAuth } from "@/auth";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0 || parts[0] === "") return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

export function UserMenu() {
  const { user, logout } = useAuth();

  // StoreGate / ProtectedRoute would normally have already routed an
  // unauthenticated visitor away from any route that mounts this. The
  // null guard here is just defence in depth for stories tests, etc.
  if (user === null) return null;

  const display = user.full_name?.trim() || user.email;
  const initials = getInitials(display);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="sm"
          className="h-9 px-2 gap-2"
          aria-label="Open account menu"
        >
          <span
            aria-hidden="true"
            className="w-7 h-7 rounded-full bg-secondary text-secondary-foreground text-xs font-semibold flex items-center justify-center"
          >
            {initials}
          </span>
          <span className="hidden sm:inline text-sm max-w-[12rem] truncate">
            {display}
          </span>
          <ChevronDown className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60">
        <DropdownMenuLabel className="font-normal">
          <div className="flex items-center gap-2 mb-1">
            <UserRound className="w-4 h-4 text-muted-foreground" aria-hidden="true" />
            <span className="text-sm font-medium truncate">{display}</span>
          </div>
          <div className="text-xs text-muted-foreground truncate" title={user.email}>
            {user.email}
          </div>
          <div className="mt-2 inline-flex items-center rounded-full border border-border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
            {user.role}
          </div>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem
          onClick={logout}
          className="text-destructive focus:text-destructive"
          data-testid="user-menu-logout"
        >
          <LogOut className="w-4 h-4 mr-2" aria-hidden="true" />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
