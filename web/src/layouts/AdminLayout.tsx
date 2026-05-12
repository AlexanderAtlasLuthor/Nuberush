import type { ReactNode } from "react";
import { AppShell } from "./AppShell";
import { ADMIN_NAV_ITEMS } from "./navigation";

export function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AppShell
      surfaceLabel="Platform Admin"
      scopeLabel="Global scope"
      navItems={ADMIN_NAV_ITEMS}
    >
      {children}
    </AppShell>
  );
}
