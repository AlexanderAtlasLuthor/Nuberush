import type { ReactNode } from "react";
import { AppSidebar } from "./components/AppSidebar";
import { AppTopbar } from "./components/AppTopbar";
import type { NavItemConfig } from "./navigation";

interface AppShellProps {
  surfaceLabel: string;
  scopeLabel: string;
  navItems?: ReadonlyArray<NavItemConfig>;
  children: ReactNode;
}

export function AppShell({
  surfaceLabel,
  scopeLabel,
  navItems = [],
  children,
}: AppShellProps) {
  return (
    <div className="min-h-screen flex bg-background text-foreground">
      <AppSidebar
        surfaceLabel={surfaceLabel}
        scopeLabel={scopeLabel}
        navItems={navItems}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <AppTopbar surfaceLabel={surfaceLabel} scopeLabel={scopeLabel} />
        <main
          className="flex-1 min-w-0 overflow-y-auto"
          aria-label="Main content"
        >
          {children}
        </main>
      </div>
    </div>
  );
}
