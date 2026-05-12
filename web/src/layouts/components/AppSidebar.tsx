import { Flame } from "lucide-react";
import type { NavItemConfig } from "../navigation";
import { NavItem } from "./NavItem";

interface AppSidebarProps {
  surfaceLabel: string;
  scopeLabel: string;
  navItems?: ReadonlyArray<NavItemConfig>;
}

export function AppSidebar({
  surfaceLabel,
  scopeLabel,
  navItems = [],
}: AppSidebarProps) {
  return (
    <aside
      aria-label="Primary navigation"
      className="w-64 shrink-0 border-r border-border bg-background hidden md:flex md:flex-col"
    >
      <div className="flex items-center gap-2 px-4 py-4 border-b border-border">
        <Flame className="w-5 h-5 text-primary" aria-hidden="true" />
        <span className="font-semibold text-sm">NubeRush</span>
      </div>
      <div
        className="px-4 py-3 border-b border-border"
        data-testid="sidebar-surface-scope"
      >
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {surfaceLabel}
        </p>
        <p className="mt-1 text-xs text-muted-foreground truncate">
          {scopeLabel}
        </p>
      </div>
      <nav className="flex-1 px-2 py-3 space-y-1 overflow-y-auto">
        {navItems.map((item) => (
          <NavItem
            key={item.href}
            href={item.href}
            label={item.label}
            icon={item.icon}
            exact={item.exact ?? item.end}
            disabled={item.disabled}
            badge={item.badge}
            description={item.description}
          />
        ))}
      </nav>
    </aside>
  );
}
