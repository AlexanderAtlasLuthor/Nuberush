import { useState, type ReactNode } from "react";
import { AppSidebar } from "./components/AppSidebar";
import { AppTopbar } from "./components/AppTopbar";
import type { NavItemConfig } from "./navigation";
import { RealtimeInvalidationBridge } from "@/features/realtime";

export type WorkspaceId = "admin" | "store";

export interface WorkspaceConfig {
  id: WorkspaceId;
  label: string;
  href: string;
}

interface AppShellProps {
  surfaceLabel: string;
  scopeLabel: string;
  navItems?: ReadonlyArray<NavItemConfig>;
  /** Workspaces the host layout chooses to expose in the sidebar switcher.
   *  AppShell does NOT infer this from auth/RBAC — the layout component is
   *  the one that knows which surface it represents and what cross-surface
   *  jumps are safe for it (e.g. AdminLayout exposes both, StoreLayout only
   *  exposes Store). */
  availableWorkspaces?: ReadonlyArray<WorkspaceConfig>;
  /** Marks the active workspace in the switcher. */
  currentWorkspace?: WorkspaceId;
  children: ReactNode;
}

export function AppShell({
  surfaceLabel,
  scopeLabel,
  navItems = [],
  availableWorkspaces = [],
  currentWorkspace,
  children,
}: AppShellProps) {
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  return (
    <div className="min-h-screen flex bg-background text-foreground">
      {/* F2.22.5.E: zero-render bridge that opens the orders +
          inventory_items Realtime channels and invalidates the
          matching TanStack Query keys on (debounced) events.
          Active only inside authenticated workspaces — AppShell
          is composed by AdminLayout / StoreLayout (both under
          ProtectedRoute) and is NOT used by PublicLayout or the
          AuthScreen. See docs/f2.22-contract-lock.md §9.1. */}
      <RealtimeInvalidationBridge />
      <AppSidebar
        surfaceLabel={surfaceLabel}
        scopeLabel={scopeLabel}
        navItems={navItems}
        availableWorkspaces={availableWorkspaces}
        currentWorkspace={currentWorkspace}
        mobileOpen={mobileSidebarOpen}
        onCloseMobile={() => setMobileSidebarOpen(false)}
      />
      <div className="flex-1 flex flex-col min-w-0">
        <AppTopbar
          surfaceLabel={surfaceLabel}
          scopeLabel={scopeLabel}
          navItems={navItems}
          onOpenMobileSidebar={() => setMobileSidebarOpen(true)}
        />
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
