import { Flame, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";
import { cn } from "@/lib/utils";
import type { WorkspaceConfig, WorkspaceId } from "../AppShell";
import type { NavItemConfig } from "../navigation";
import { NavItem } from "./NavItem";

interface AppSidebarProps {
  surfaceLabel: string;
  scopeLabel: string;
  navItems?: ReadonlyArray<NavItemConfig>;
  /** Workspaces to render in the switcher row. AppSidebar trusts whatever
   *  the host layout passes — no role inference happens here. */
  availableWorkspaces?: ReadonlyArray<WorkspaceConfig>;
  /** Marks the active workspace visually. Active state is declared by the
   *  layout, never derived from pathname or local state. */
  currentWorkspace?: WorkspaceId;
  /** Mobile drawer visibility — desktop sidebar is always rendered via md+ classes. */
  mobileOpen?: boolean;
  /** Called when a nav item is selected on mobile (to close the drawer) and when the backdrop is tapped. */
  onCloseMobile?: () => void;
}

// Visual grouping only. Backend remains the source of truth for any privileged action.
const PLATFORM_LABELS = new Set(["Audit", "Compliance", "Operations", "Settings"]);

function splitNav(items: ReadonlyArray<NavItemConfig>) {
  const main: NavItemConfig[] = [];
  const platform: NavItemConfig[] = [];
  for (const item of items) {
    if (PLATFORM_LABELS.has(item.label)) {
      platform.push(item);
    } else {
      main.push(item);
    }
  }
  return { main, platform };
}

function WorkspaceSwitcher({
  availableWorkspaces,
  currentWorkspace,
  onNavigate,
}: {
  availableWorkspaces: ReadonlyArray<WorkspaceConfig>;
  currentWorkspace: WorkspaceId | undefined;
  onNavigate?: () => void;
}) {
  if (availableWorkspaces.length === 0) return null;

  return (
    <div
      className="px-3 pt-3 pb-1"
      role="region"
      aria-label="Workspace switcher"
      data-testid="workspace-switcher"
    >
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/80 px-2 mb-1.5">
        Workspace
      </p>
      <div
        className="inline-flex w-full rounded-md bg-secondary/40 p-0.5 gap-0.5"
        role="group"
      >
        {availableWorkspaces.map((ws) => {
          const isActive = ws.id === currentWorkspace;
          return (
            <Link
              key={ws.id}
              to={ws.href}
              onClick={onNavigate}
              aria-current={isActive ? "page" : undefined}
              className={cn(
                "flex-1 text-[11px] font-medium py-1.5 px-2 rounded text-center transition-colors truncate",
                isActive
                  ? "bg-card text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground hover:bg-secondary/60",
              )}
            >
              {ws.label}
            </Link>
          );
        })}
      </div>
    </div>
  );
}

function SidebarContent({
  surfaceLabel,
  scopeLabel,
  navItems,
  availableWorkspaces,
  currentWorkspace,
  onNavigate,
}: {
  surfaceLabel: string;
  scopeLabel: string;
  navItems: ReadonlyArray<NavItemConfig>;
  availableWorkspaces: ReadonlyArray<WorkspaceConfig>;
  currentWorkspace: WorkspaceId | undefined;
  onNavigate?: () => void;
}) {
  const { main, platform } = splitNav(navItems);

  const renderItem = (item: NavItemConfig) => (
    <NavItem
      key={item.href}
      href={item.href}
      label={item.label}
      icon={item.icon}
      exact={item.exact ?? item.end}
      disabled={item.disabled}
      badge={item.badge}
      description={item.description}
      onNavigate={onNavigate}
    />
  );

  return (
    <>
      <div className="flex items-center gap-2.5 px-4 py-4 border-b border-border">
        <span
          className="inline-flex h-8 w-8 items-center justify-center rounded-lg bg-primary text-primary-foreground shrink-0"
          aria-hidden="true"
        >
          <Flame className="w-4 h-4" />
        </span>
        <span className="font-semibold text-sm tracking-tight truncate">
          NubeRush
        </span>
      </div>
      <WorkspaceSwitcher
        availableWorkspaces={availableWorkspaces}
        currentWorkspace={currentWorkspace}
        onNavigate={onNavigate}
      />
      <div
        className="px-4 py-3 border-b border-border"
        data-testid="sidebar-surface-scope"
      >
        <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
          {surfaceLabel}
        </p>
        <p className="mt-1 text-xs text-muted-foreground truncate">
          {scopeLabel}
        </p>
      </div>
      <div className="flex-1 px-3 py-3 overflow-y-auto">
        {main.length > 0 ? (
          <section aria-label="Main navigation" className="space-y-0.5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/80 px-2.5 mb-1.5">
              Main
            </p>
            {main.map(renderItem)}
          </section>
        ) : null}
        {platform.length > 0 ? (
          <section aria-label="Platform navigation" className="mt-4 space-y-0.5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground/80 px-2.5 mb-1.5">
              Platform
            </p>
            {platform.map(renderItem)}
          </section>
        ) : null}
      </div>
      <div className="px-3 py-3 border-t border-border">
        <div className="rounded-lg border border-border bg-secondary/40 p-3 text-[11px] text-muted-foreground leading-relaxed">
          <div className="flex items-center gap-1.5 text-foreground font-medium text-xs mb-1">
            <ShieldCheck
              className="w-3.5 h-3.5 text-primary"
              aria-hidden="true"
            />
            Backend authoritative
          </div>
          UI never decides RBAC, tenancy, or compliance.
        </div>
      </div>
    </>
  );
}

export function AppSidebar({
  surfaceLabel,
  scopeLabel,
  navItems = [],
  availableWorkspaces = [],
  currentWorkspace,
  mobileOpen = false,
  onCloseMobile,
}: AppSidebarProps) {
  return (
    <>
      {/* Desktop sidebar — persistent at md+. */}
      <aside
        aria-label="Primary navigation"
        className="w-60 shrink-0 border-r border-border bg-background hidden md:flex md:flex-col"
      >
        <nav className="flex flex-col h-full" aria-label="Sidebar">
          <SidebarContent
            surfaceLabel={surfaceLabel}
            scopeLabel={scopeLabel}
            navItems={navItems}
            availableWorkspaces={availableWorkspaces}
            currentWorkspace={currentWorkspace}
          />
        </nav>
      </aside>

      {/* Mobile drawer — only mounted while open so it doesn't shadow the desktop aside in tests. */}
      {mobileOpen ? (
        <div
          className="md:hidden fixed inset-0 z-50 flex"
          role="dialog"
          aria-modal="true"
          aria-label="Navigation menu"
        >
          <button
            type="button"
            aria-label="Close navigation menu"
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={onCloseMobile}
          />
          <nav
            aria-label="Mobile navigation"
            className="relative flex flex-col w-72 max-w-[85vw] h-full bg-background border-r border-border"
            data-testid="mobile-sidebar"
          >
            <SidebarContent
              surfaceLabel={surfaceLabel}
              scopeLabel={scopeLabel}
              navItems={navItems}
              availableWorkspaces={availableWorkspaces}
              currentWorkspace={currentWorkspace}
              onNavigate={onCloseMobile}
            />
          </nav>
        </div>
      ) : null}
    </>
  );
}
