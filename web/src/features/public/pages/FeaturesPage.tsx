import { Link } from "react-router-dom";
import { PublicPageHeader } from "../components/PublicPageHeader";
import { PublicSection } from "../components/PublicSection";
import { PublicCtaBand } from "../components/PublicCtaBand";
import {
  FEATURES_PAGE_COPY,
  FEATURES_PAGE_CTA_BAND,
  FEATURES_PAGE_GROUPS,
} from "../content/publicCopy";

// F2.21.3 — real /features page. Six capability groups containing the
// eight contract-locked capabilities (Store workspace, Product
// oversight, Inventory visibility, Order operations, Compliance
// visibility, Audit trail, Admin console, Operations alerts).
// Replaces the F2.21.1 shell. No unbuilt-feature promises, no fake
// stats / testimonials / logos.

export function FeaturesPage() {
  return (
    <>
      <PublicPageHeader
        eyebrow={FEATURES_PAGE_COPY.eyebrow}
        title={FEATURES_PAGE_COPY.headline}
        description={FEATURES_PAGE_COPY.subhead}
        actions={
          <>
            <Link
              to={FEATURES_PAGE_COPY.primaryCta.to}
              className="inline-flex items-center justify-center h-10 px-5 rounded-md text-sm font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {FEATURES_PAGE_COPY.primaryCta.label}
            </Link>
            <Link
              to={FEATURES_PAGE_COPY.secondaryCta.to}
              className="inline-flex items-center justify-center h-10 px-5 rounded-md text-sm font-medium border border-border text-foreground hover:bg-accent hover:text-accent-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {FEATURES_PAGE_COPY.secondaryCta.label}
            </Link>
          </>
        }
      />

      <section className="w-full bg-background py-12 md:py-16">
        <div className="container space-y-10">
          {FEATURES_PAGE_GROUPS.map((group) => {
            const Icon = group.icon;
            return (
              <article
                key={group.title}
                className="rounded-2xl border border-border bg-card/40 p-6 md:p-8"
              >
                <header className="flex items-start gap-4 md:items-center">
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary shrink-0">
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <div>
                    <h2 className="text-xl md:text-2xl font-semibold tracking-tight text-foreground">
                      {group.title}
                    </h2>
                    <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
                      {group.description}
                    </p>
                  </div>
                </header>

                <ul className="mt-6 grid gap-4 md:grid-cols-2">
                  {group.capabilities.map((cap) => (
                    <li
                      key={cap.title}
                      className="rounded-xl border border-border bg-card p-5"
                    >
                      <p className="text-sm font-semibold text-foreground">
                        {cap.title}
                      </p>
                      <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                        {cap.body}
                      </p>
                    </li>
                  ))}
                </ul>
              </article>
            );
          })}
        </div>
      </section>

      <PublicCtaBand
        title={FEATURES_PAGE_CTA_BAND.title}
        description={FEATURES_PAGE_CTA_BAND.description}
        primary={FEATURES_PAGE_CTA_BAND.primary}
        secondary={FEATURES_PAGE_CTA_BAND.secondary}
      />
    </>
  );
}

export default FeaturesPage;
