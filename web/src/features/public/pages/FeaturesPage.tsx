import { Link } from "react-router-dom";
import { PublicPageHeader } from "../components/PublicPageHeader";
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
              className="premium-action inline-flex h-10 items-center justify-center rounded-full px-5 text-sm font-semibold text-primary-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {FEATURES_PAGE_COPY.primaryCta.label}
            </Link>
            <Link
              to={FEATURES_PAGE_COPY.secondaryCta.to}
              className="inline-flex h-10 items-center justify-center rounded-full border border-foreground/12 bg-foreground/8 px-5 text-sm font-medium text-foreground backdrop-blur-xl transition-colors hover:bg-foreground/12 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {FEATURES_PAGE_COPY.secondaryCta.label}
            </Link>
          </>
        }
      />

      <section className="w-full bg-transparent py-12 md:py-16">
        <div className="container space-y-10">
          {FEATURES_PAGE_GROUPS.map((group) => {
            const Icon = group.icon;
            return (
              <article
                key={group.title}
                className="premium-glass-soft rounded-lg p-5 md:p-7"
              >
                <header className="flex items-start gap-4 md:items-center">
                  <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/20">
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <div>
                    <h2 className="text-xl md:text-2xl font-semibold tracking-tight text-foreground">
                      {group.title}
                    </h2>
                    <p className="mt-1 text-sm leading-relaxed text-foreground/62">
                      {group.description}
                    </p>
                  </div>
                </header>

                <ul className="mt-6 grid gap-4 md:grid-cols-2">
                  {group.capabilities.map((cap) => (
                    <li
                      key={cap.title}
                      className="rounded-lg border border-foreground/10 bg-background/26 p-5 backdrop-blur-xl transition-colors hover:border-primary/30"
                    >
                      <p className="text-sm font-semibold text-foreground">
                        {cap.title}
                      </p>
                      <p className="mt-2 text-sm leading-relaxed text-foreground/62">
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
