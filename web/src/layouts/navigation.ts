// F2.12.3: visual navigation configs for the two app surfaces.
//
// Navigation remains UX only. These arrays do not grant access, model
// permissions, or decide tenant boundaries. Backend/Auth remain the source
// of truth for every privileged action and data fetch.

import {
  Boxes,
  Building2,
  ClipboardList,
  FileWarning,
  LayoutDashboard,
  RadioTower,
  Settings,
  ShieldCheck,
  ShoppingBag,
  Users,
  type LucideIcon,
} from "lucide-react";

export interface NavItemConfig {
  /** Display label shown in the sidebar. */
  label: string;
  /** Absolute route under /app. Matches react-router-dom paths exactly. */
  href: string;
  /** lucide-react icon component, rendered around 16px. */
  icon: LucideIcon;
  /** Optional one-line hint surfaced to screen readers and future tooltips. */
  description?: string;
  /** Exact active matching for index/dashboard links. */
  exact?: boolean;
  /** Visually disabled item support for future UX-only affordances. */
  disabled?: boolean;
  /** Optional non-authoritative visual badge. */
  badge?: string;
  /** Backwards-compatible alias for exact. Prefer exact in new nav configs. */
  end?: boolean;
}

export const STORE_NAV_ITEMS: ReadonlyArray<NavItemConfig> = [
  {
    label: "Dashboard",
    href: "/app/store",
    icon: LayoutDashboard,
    description: "Operational overview",
    exact: true,
  },
  {
    label: "Products",
    href: "/app/store/products",
    icon: ShoppingBag,
    description: "Catalog and variants",
  },
  {
    label: "Inventory",
    href: "/app/store/inventory",
    icon: Boxes,
    description: "Stock levels per store",
  },
  {
    label: "Orders",
    href: "/app/store/orders",
    icon: ClipboardList,
    description: "Store orders",
  },
  {
    label: "Users",
    href: "/app/store/users",
    icon: Users,
    description: "Team members",
  },
  {
    label: "Audit",
    href: "/app/store/audit",
    icon: ShieldCheck,
    description: "Compliance and audit logs",
  },
  {
    label: "Settings",
    href: "/app/store/settings",
    icon: Settings,
    description: "Store and account preferences",
  },
];

export const ADMIN_NAV_ITEMS: ReadonlyArray<NavItemConfig> = [
  {
    label: "Dashboard",
    href: "/app/admin",
    icon: LayoutDashboard,
    description: "Platform overview",
    exact: true,
  },
  {
    label: "Stores",
    href: "/app/admin/stores",
    icon: Building2,
    description: "Store lifecycle",
  },
  {
    label: "Users",
    href: "/app/admin/users",
    icon: Users,
    description: "Platform user oversight",
  },
  {
    label: "Products",
    href: "/app/admin/products",
    icon: ShoppingBag,
    description: "Global product visibility",
  },
  {
    label: "Inventory",
    href: "/app/admin/inventory",
    icon: Boxes,
    description: "Global inventory visibility",
  },
  {
    label: "Orders",
    href: "/app/admin/orders",
    icon: ClipboardList,
    description: "Global order visibility",
  },
  {
    label: "Audit",
    href: "/app/admin/audit",
    icon: ShieldCheck,
    description: "Platform audit trail",
  },
  {
    label: "Compliance",
    href: "/app/admin/compliance",
    icon: FileWarning,
    description: "Platform compliance review",
  },
  {
    label: "Operations",
    href: "/app/admin/operations",
    icon: RadioTower,
    description: "Platform operations",
  },
  {
    label: "Settings",
    href: "/app/admin/settings",
    icon: Settings,
    description: "Platform settings",
  },
];

// Backwards-compatible alias during F2.12 migration.
// Prefer STORE_NAV_ITEMS or ADMIN_NAV_ITEMS in new code.
export const NAV_ITEMS = STORE_NAV_ITEMS;
