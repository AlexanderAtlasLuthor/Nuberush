import type { ReactNode } from "react";
import { StoreLayout } from "./StoreLayout";

// Backwards-compatible alias for older tests/imports. F2.12.2 routes now use
// AdminLayout and StoreLayout explicitly.
export function DashboardLayout({ children }: { children: ReactNode }) {
  return <StoreLayout>{children}</StoreLayout>;
}
