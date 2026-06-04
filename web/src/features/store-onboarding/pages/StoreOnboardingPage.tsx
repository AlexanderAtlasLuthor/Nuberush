// F2.25.6: Store onboarding landing page.
//
// A simple, static getting-started checklist for newly approved store
// owners. It renders under the existing /app/store subtree (ProtectedRoute
// → StoreGate → StoreShell), so it inherits auth + store gating + layout.
// No data fetching, no backend calls, no auth tokens — every item links to
// a route that already exists.

import { Link } from "react-router-dom";
import {
  ArrowRight,
  ClipboardList,
  Boxes,
  LifeBuoy,
  Package,
  ShoppingCart,
  Store,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

type ChecklistItem = {
  title: string;
  description: string;
  to: string;
  icon: LucideIcon;
};

const CHECKLIST: ChecklistItem[] = [
  {
    title: "Complete store profile",
    description: "Set your store name, timezone, and basic details.",
    to: "/app/store/settings",
    icon: Store,
  },
  {
    title: "Add first products",
    description: "Create the products you plan to sell.",
    to: "/app/store/products",
    icon: Package,
  },
  {
    title: "Set inventory thresholds",
    description: "Track stock and get low-inventory signals.",
    to: "/app/store/inventory",
    icon: Boxes,
  },
  {
    title: "Review orders dashboard",
    description: "See how incoming orders will appear.",
    to: "/app/store/orders",
    icon: ShoppingCart,
  },
  {
    title: "Contact NubeRush support",
    description: "Questions about setup? We're here to help.",
    to: "/support",
    icon: LifeBuoy,
  },
];

function PageHeader() {
  return (
    <header className="space-y-2">
      <div className="flex items-center gap-2">
        <ClipboardList
          className="h-5 w-5 text-muted-foreground"
          aria-hidden="true"
        />
        <h1 className="text-xl font-semibold">
          Getting started with your store
        </h1>
      </div>
      <p className="text-sm text-muted-foreground">
        Work through these steps to get your store ready for operations.
      </p>
    </header>
  );
}

export default function StoreOnboardingPage() {
  return (
    <div className="p-6 md:p-8 space-y-6 max-w-3xl">
      <PageHeader />

      <ol className="space-y-3">
        {CHECKLIST.map((item, index) => {
          const Icon = item.icon;
          return (
            <li key={item.to}>
              <Link
                to={item.to}
                className="group flex items-center gap-4 rounded-lg border border-border bg-card p-4 transition-colors hover:bg-accent"
              >
                <span
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-muted text-sm font-semibold text-muted-foreground"
                  aria-hidden="true"
                >
                  {index + 1}
                </span>
                <Icon
                  className="h-5 w-5 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">{item.title}</span>
                  <span className="block text-sm text-muted-foreground">
                    {item.description}
                  </span>
                </span>
                <ArrowRight
                  className="h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
                  aria-hidden="true"
                />
              </Link>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
