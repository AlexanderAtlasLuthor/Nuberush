import { Link } from "react-router-dom";
import { PublicPageHeader } from "../components/PublicPageHeader";
import { PublicSection } from "../components/PublicSection";
import { PublicCtaBand } from "../components/PublicCtaBand";
import {
  FOR_STORES_COPY,
  FOR_STORES_CTA_BAND,
  FOR_STORES_SECTIONS,
  FOR_STORES_SECTION_HEADING,
} from "../content/publicCopy";

// F2.21.3 — real /for-stores merchant education page. Replaces the
// F2.21.1 shell. Copy lives in publicCopy.ts so this page stays
// declarative. No fake stats, testimonials, partner logos, or
// guaranteed-compliance claims.

export function ForStoresPage() {
  return (
    <>
      <PublicPageHeader
        eyebrow={FOR_STORES_COPY.eyebrow}
        title={FOR_STORES_COPY.headline}
        description={FOR_STORES_COPY.subhead}
        actions={
          <>
            <Link
              to={FOR_STORES_COPY.primaryCta.to}
              className="inline-flex items-center justify-center h-10 px-5 rounded-md text-sm font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {FOR_STORES_COPY.primaryCta.label}
            </Link>
            <Link
              to={FOR_STORES_COPY.secondaryCta.to}
              className="inline-flex items-center justify-center h-10 px-5 rounded-md text-sm font-medium border border-border text-foreground hover:bg-accent hover:text-accent-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {FOR_STORES_COPY.secondaryCta.label}
            </Link>
          </>
        }
      />

      <PublicSection
        eyebrow={FOR_STORES_SECTION_HEADING.eyebrow}
        title={FOR_STORES_SECTION_HEADING.title}
        description={FOR_STORES_SECTION_HEADING.description}
      >
        <ul className="grid gap-5 md:grid-cols-2">
          {FOR_STORES_SECTIONS.map((section) => {
            const Icon = section.icon;
            return (
              <li
                key={section.title}
                className="rounded-xl border border-border bg-card p-6"
              >
                <div className="flex items-center gap-3">
                  <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary shrink-0">
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <p className="text-base font-semibold text-foreground">
                    {section.title}
                  </p>
                </div>
                <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
                  {section.body}
                </p>
                <ul className="mt-4 space-y-2 text-sm text-foreground/90 leading-relaxed list-disc pl-5">
                  {section.bullets.map((bullet) => (
                    <li key={bullet}>{bullet}</li>
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
