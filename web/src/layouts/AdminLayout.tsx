import type { ReactNode } from "react";
import { AppShell, type WorkspaceConfig } from "./AppShell";
import { ADMIN_NAV_ITEMS } from "./navigation";

// Admin accounts navigate the platform exclusively through the sidebar
// (Stores entry included). The cross-surface workspace switcher is
// intentionally suppressed here — empty list collapses the switcher row.
const ADMIN_AVAILABLE_WORKSPACES: ReadonlyArray<WorkspaceConfig> = [];

export function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AppShell
      surfaceLabel="Platform Admin"
      scopeLabel="Global scope"
      navItems={ADMIN_NAV_ITEMS}
      availableWorkspaces={ADMIN_AVAILABLE_WORKSPACES}
      currentWorkspace="admin"
    >
      {children}
    </AppShell>
  );
}
