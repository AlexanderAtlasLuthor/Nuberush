import { Bell, ChevronRight, Menu, Search } from "lucide-react";
import { useLocation } from "react-router-dom";
import type { NavItemConfig } from "../navigation";
import { UserMenu } from "./UserMenu";

interface AppTopbarProps {
  surfaceLabel: string;
  scopeLabel: string;
  navItems?: ReadonlyArray<NavItemConfig>;
  /** Opens the mobile drawer. Only rendered when the parent wires it; the hamburger button hides on md+. */
  onOpenMobileSidebar?: () => void;
}

// Find the deepest nav item whose href matches the current pathname. Mirrors
// the matching that react-router-dom NavLink performs so the breadcrumb and
// the sidebar active state stay aligned.
function findActiveNavItem(
  pathname: string,
  items: ReadonlyArray<NavItemConfig>,
): NavItemConfig | null {
  let best: NavItemConfig | null = null;
  for (const item of items) {
    const exact = item.exact ?? item.end ?? false;
    const matches = exact
      ? pathname === item.href
      : pathname === item.href || pathname.startsWith(item.href + "/");
    if (matches && (best === null || item.href.length > best.href.length)) {
      best = item;
    }
  }
  return best;
}

export function AppTopbar({
  surfaceLabel,
  scopeLabel,
  navItems = [],
  onOpenMobileSidebar,
}: AppTopbarProps) {
  const { pathname } = useLocation();
  const activeItem = findActiveNavItem(pathname, navItems);

  return (
    <header
      aria-label="Topbar"
      className="h-14 border-b border-border bg-background flex items-center px-4 md:px-6 gap-3"
    >
      <button
        type="button"
        aria-label="Open navigation menu"
        data-testid="mobile-sidebar-trigger"
        onClick={onOpenMobileSidebar}
        className="md:hidden h-9 w-9 inline-flex items-center justify-center rounded-md text-foreground hover:bg-secondary transition-colors"
      >
        <Menu className="w-4 h-4" aria-hidden="true" />
      </button>

      <div className="min-w-0 flex-1 flex items-center gap-3">
        {/* Mobile compact title: prefer the matched route label, fall back to the surface. */}
        <span className="md:hidden text-sm font-semibold truncate">
          {activeItem ? activeItem.label : surfaceLabel}
        </span>

        {/* Desktop breadcrumb derived from the real navigation. */}
        <nav
          aria-label="Breadcrumb"
          className="hidden md:flex items-center gap-1.5 text-sm min-w-0"
        >
          <span className="text-muted-foreground truncate">{surfaceLabel}</span>
          {activeItem ? (
            <>
              <ChevronRight
                className="w-3.5 h-3.5 text-muted-foreground shrink-0"
                aria-hidden="true"
              />
              <span className="font-medium truncate">{activeItem.label}</span>
            </>
          ) : null}
        </nav>

        <span
          className="hidden md:inline-flex ml-auto text-xs text-muted-foreground font-mono truncate"
          aria-label="Current surface scope"
          data-testid="store-context-indicator"
        >
          {scopeLabel}
        </span>
      </div>

      {/* Visual command pill — there is no real search endpoint yet, so the button
          is intentionally inert. It exists to preserve the design system rhythm
          without misleading users. */}
      <span
        className="hidden lg:inline-flex h-8 items-center gap-2 rounded-md border border-border bg-secondary/40 px-2.5 w-64 select-none"
        aria-hidden="true"
      >
        <Search className="w-3.5 h-3.5 text-muted-foreground" />
        <span className="text-xs text-muted-foreground truncate">Search</span>
      </span>

      {/* Visual notifications placeholder — disabled because there is no backend
          feed today. No fake badge dot. */}
      <button
        type="button"
        aria-label="Notifications"
        title="Notifications are not yet available"
        disabled
        className="hidden md:inline-flex h-9 w-9 items-center justify-center rounded-md text-muted-foreground disabled:cursor-not-allowed disabled:opacity-60"
      >
        <Bell className="w-4 h-4" aria-hidden="true" />
      </button>

      {/* Mobile search placeholder lives next to the user menu to keep the touch
          target row balanced. Also intentionally inert. */}
      <button
        type="button"
        aria-label="Search"
        title="Search is not yet available"
        disabled
        className="md:hidden h-9 w-9 inline-flex items-center justify-center rounded-md text-muted-foreground disabled:cursor-not-allowed disabled:opacity-60"
      >
        <Search className="w-4 h-4" aria-hidden="true" />
      </button>

      <UserMenu />
    </header>
  );
}
