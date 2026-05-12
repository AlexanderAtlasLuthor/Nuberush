import type { ReactNode } from "react";
import { useStoreContext } from "@/auth";
import { AppShell } from "./AppShell";
import { STORE_NAV_ITEMS } from "./navigation";

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
    >
      {children}
    </AppShell>
  );
}
