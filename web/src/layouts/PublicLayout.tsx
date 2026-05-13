import type { ReactNode } from "react";
import { PublicHeader } from "@/features/public/components/PublicHeader";
import { PublicFooter } from "@/features/public/components/PublicFooter";
import { PublicPageMeta } from "@/features/public/components/PublicPageMeta";

// PublicLayout wraps every NubeRush public-website route. Intentionally
// independent of AdminLayout and StoreLayout: no auth check, no role
// context, no store context, no admin/store navigation. Rendered for
// unauthenticated and authenticated visitors alike per F2.21 contract.
//
// F2.21.7 — `PublicPageMeta` runs as a side-effect-only child so
// document.title and meta tags update on every public route change.
// It returns null, so it contributes nothing to the rendered tree
// (and never adds a heading or competes with the single h1).

export function PublicLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-background text-foreground">
      <PublicPageMeta />
      <PublicHeader />
      <main id="main-content" className="flex-1 w-full" aria-label="Main content">
        {children}
      </main>
      <PublicFooter />
    </div>
  );
}

export default PublicLayout;
