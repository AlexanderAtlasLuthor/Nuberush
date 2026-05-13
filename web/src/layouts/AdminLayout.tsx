import type { ReactNode } from "react";
import { AppShell, type WorkspaceConfig } from "./AppShell";
import { ADMIN_NAV_ITEMS } from "./navigation";

// Admin/platform accounts are the only callers of this layout (the route
// guard enforces that — see ProtectedRoute). They are free to jump to the
// Store surface, so both workspaces are exposed in the switcher.
const ADMIN_AVAILABLE_WORKSPACES: ReadonlyArray<WorkspaceConfig> = [
  { id: "admin", label: "Admin", href: "/app/admin" },
  { id: "store", label: "Store", href: "/app/store" },
];

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
