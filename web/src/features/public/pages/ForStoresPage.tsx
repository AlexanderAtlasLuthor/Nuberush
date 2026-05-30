import { Link } from "react-router-dom";
import { PublicPageHeader } from "../components/PublicPageHeader";
import { PublicSection } from "../components/PublicSection";
import { PublicCtaBand } from "../components/PublicCtaBand";
import { useMobileCopy } from "../components/useMobileCopy";
import {
  FOR_STORES_COPY,
  FOR_STORES_CTA_BAND,
  FOR_STORES_SECTIONS,
  FOR_STORES_SECTION_HEADING,
} from "../content/publicCopy";

const MOBILE_STORE_SECTION_TITLES: Record<string, string> = {
  "Why stores use NubeRush": "Why NubeRush",
  "Product operations": "Products",
  "Inventory visibility": "Inventory",
  "Order oversight": "Orders",
  "Compliance-aware workflows": "Compliance",
  "Admin/platform support": "Admin support",
  "Audit / traceability": "Audit",
};

// F2.21.3 — real /for-stores merchant education page. Replaces the
// F2.21.1 shell. Copy lives in publicCopy.ts so this page stays
// declarative. No fake stats, testimonials, partner logos, or
// guaranteed-compliance claims.

export function ForStoresPage() {
  const isMobileCopy = useMobileCopy();

  return (
    <>
      <PublicPageHeader
        eyebrow={FOR_STORES_COPY.eyebrow}
        title={FOR_STORES_COPY.headline}
        mobileTitle="For clearer store ops."
        description={FOR_STORES_COPY.subhead}
        mobileDescription="Products, inventory, orders, compliance, and audit in one workspace."
        actions={
          <>
            <Link
              to={FOR_STORES_COPY.primaryCta.to}
              className="premium-action inline-flex h-10 items-center justify-center rounded-full px-5 text-sm font-semibold text-primary-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {FOR_STORES_COPY.primaryCta.label}
            </Link>
            <Link
              to={FOR_STORES_COPY.secondaryCta.to}
              className="inline-flex h-10 items-center justify-center rounded-full border border-foreground/12 bg-foreground/8 px-5 text-sm font-medium text-foreground backdrop-blur-xl transition-colors hover:bg-foreground/12 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {FOR_STORES_COPY.secondaryCta.label}
            </Link>
          </>
        }
      />

      <PublicSection
        eyebrow={FOR_STORES_SECTION_HEADING.eyebrow}
        title={FOR_STORES_SECTION_HEADING.title}
        mobileTitle="What stores get."
        description={FOR_STORES_SECTION_HEADING.description}
        mobileDescription="The operating areas NubeRush supports today."
      >
        <ul className="grid gap-5 md:grid-cols-2">
          {FOR_STORES_SECTIONS.map((section) => {
            const Icon = section.icon;
            return (
              <li
                key={section.title}
                className="premium-glass-soft rounded-lg p-5 md:p-6"
              >
                <div className="flex items-center gap-3">
                  <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/20">
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <p className="text-base font-semibold text-foreground">
                    {isMobileCopy
                      ? MOBILE_STORE_SECTION_TITLES[section.title] ??
                        section.title
                      : section.title}
                  </p>
                </div>
                <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-foreground/62 sm:line-clamp-none">
                  {section.body}
                </p>
                <ul className="mt-4 space-y-2 text-sm leading-relaxed text-foreground/78 sm:block">
                  {section.bullets.map((bullet) => (
                    <li key={bullet} className="flex gap-2">
                      <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/80" />
                      <span>{bullet}</span>
                    </li>
                  ))}
                </ul>
              </li>
            );
          })}
        </ul>
      </PublicSection>

      <PublicCtaBand
        title={FOR_STORES_CTA_BAND.title}
        description={FOR_STORES_CTA_BAND.description}
        primary={FOR_STORES_CTA_BAND.primary}
        secondary={FOR_STORES_CTA_BAND.secondary}
      />
    </>
  );
}

export default ForStoresPage;
