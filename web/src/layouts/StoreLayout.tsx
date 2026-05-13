import type { ReactNode } from "react";
import { useStoreContext } from "@/auth";
import { AppShell, type WorkspaceConfig } from "./AppShell";
import { STORE_NAV_ITEMS } from "./navigation";

// Store accounts only ever see the Store surface. The switcher therefore
// exposes exactly one workspace — there is no Admin entry to click, no
// /app/admin href surfaced, and no Platform/Global label. RBAC stays
// authoritative at the route and backend layers; this is purely the
// honest visual representation of what this surface can reach.
const STORE_AVAILABLE_WORKSPACES: ReadonlyArray<WorkspaceConfig> = [
  { id: "store", label: "Store", href: "/app/store" },
];

function useStoreScopeLabel(): string {
  const { currentStoreId, hasStoreContext } = useStoreContext();

  if (hasStoreContext && currentStoreId !== null) {
    return `Store scope | Store: ${currentStoreId}`;
  }

  return "Store scope | No store selected";
}

export function StoreLayout({ children }: { children: ReactNode }) {
  return (
    <AppShell
      surfaceLabel="Store Operations"
      scopeLabel={useStoreScopeLabel()}
      navItems={STORE_NAV_ITEMS}
      availableWorkspaces={STORE_AVAILABLE_WORKSPACES}
      currentWorkspace="store"
    >
      {children}
    </AppShell>
  );
}
