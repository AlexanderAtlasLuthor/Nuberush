import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { PublicSection } from "../components/PublicSection";
import { PublicCtaBand } from "../components/PublicCtaBand";
import { PublicHero } from "../components/PublicHero";
import { PublicTrustBand } from "../components/PublicTrustBand";
import { PublicFeatureGrid } from "../components/PublicFeatureGrid";
import { PublicFaq } from "../components/PublicFaq";
import {
  CTA_BAND_COPY,
  FAQ_ITEMS,
  FAQ_SECTION,
  FEATURES,
  FEATURES_SECTION,
  HERO_COPY,
  HOW_IT_WORKS_SECTION,
  HOW_IT_WORKS_STEPS,
  OPERATIONS_PREVIEW_AREAS,
  OPERATIONS_PREVIEW_SECTION,
  PROBLEMS,
  PROBLEM_SECTION,
  REGULATED_COMMERCE_COPY,
  SOLUTION_PILLARS,
  SOLUTION_SECTION,
  TRUST_POINTS,
} from "../content/publicCopy";

// F2.21.2 homepage. Ten sections in the order locked by F2.21 contract
// §6: Hero / Trust band / Problem / Solution / Feature grid /
// How-it-works preview / Built for regulated local commerce /
// Merchant operations preview / Contact-demo CTA / FAQ.
//
// Copy lives in content/publicCopy.ts so HomePage stays declarative
// and copy can be audited in one place. No fake stats, fake
// testimonials, fake partner logos, guaranteed-compliance claims, or
// references to features the platform does not ship.

export function HomePage() {
  return (
    <>
      <PublicHero
        eyebrow={HERO_COPY.eyebrow}
        headline={HERO_COPY.headline}
        subhead={HERO_COPY.subhead}
        primary={HERO_COPY.primaryCta}
        secondary={HERO_COPY.secondaryCta}
      />

      <PublicTrustBand points={TRUST_POINTS} />

      <PublicSection
        eyebrow={PROBLEM_SECTION.eyebrow}
        title={PROBLEM_SECTION.title}
        description={PROBLEM_SECTION.description}
      >
        <ul className="grid gap-4 md:grid-cols-2">
          {PROBLEMS.map((problem) => (
            <li
              key={problem.title}
              className="rounded-xl border border-border bg-card p-5"
            >
              <p className="text-sm font-semibold text-foreground">
                {problem.title}
              </p>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                {problem.body}
              </p>
            </li>
          ))}
        </ul>
      </PublicSection>

      <PublicSection
        eyebrow={SOLUTION_SECTION.eyebrow}
        title={SOLUTION_SECTION.title}
        description={SOLUTION_SECTION.description}
        tone="muted"
      >
        <ul className="grid gap-4 md:grid-cols-3">
          {SOLUTION_PILLARS.map((pillar) => {
            const Icon = pillar.icon;
            return (
              <li
                key={pillar.title}
                className="rounded-xl border border-border bg-card p-5"
              >
                <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <p className="mt-4 text-sm font-semibold text-foreground">
                  {pillar.title}
                </p>
                <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
                  {pillar.body}
                </p>
              </li>
            );
          })}
        </ul>
      </PublicSection>

      <PublicSection
        eyebrow={FEATURES_SECTION.eyebrow}
        title={FEATURES_SECTION.title}
        description={FEATURES_SECTION.description}
      >
        <PublicFeatureGrid features={FEATURES} />
      </PublicSection>

      <PublicSection
        eyebrow={HOW_IT_WORKS_SECTION.eyebrow}
        title={HOW_IT_WORKS_SECTION.title}
        description={HOW_IT_WORKS_SECTION.description}
        tone="muted"
      >
        <ol className="space-y-4">
          {HOW_IT_WORKS_STEPS.map((step) => (
            <li
              key={step.step}
              className="rounded-xl border border-border bg-card p-5 flex items-start gap-4"
            >
              <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary text-sm font-semibold">
                {step.step}
              </span>
              <div>
                <p className="text-sm font-semibold text-foreground">
                  {step.title}
                </p>
                <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
                  {step.body}
                </p>
              </div>
            </li>
          ))}
        </ol>
        <div className="mt-6">
          <Link
            to="/how-it-works"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm"
          >
            Learn how it works
            <ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Link>
        </div>
      </PublicSection>

      <PublicSection
        eyebrow="Regulated local commerce"
        title={REGULATED_COMMERCE_COPY.title}
        description={REGULATED_COMMERCE_COPY.body}
      >
        <ul className="space-y-3">
          {REGULATED_COMMERCE_COPY.highlights.map((highlight) => (
            <li
              key={highlight}
              className="rounded-lg border border-border bg-card/60 px-4 py-3 text-sm text-foreground/90 leading-relaxed"
            >
              {highlight}
            </li>
          ))}
        </ul>
      </PublicSection>

      <PublicSection
        eyebrow={OPERATIONS_PREVIEW_SECTION.eyebrow}
        title={OPERATIONS_PREVIEW_SECTION.title}
        description={OPERATIONS_PREVIEW_SECTION.description}
        tone="muted"
      >
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {OPERATIONS_PREVIEW_AREAS.map((area) => {
            const Icon = area.icon;
            return (
              <li
                key={area.title}
                className="rounded-xl border border-border bg-card p-5"
              >
                <div className="flex items-center gap-3">
                  <span className="inline-flex h-9 w-9 items-center justify-center rounded-lg bg-primary/10 text-primary">
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <p className="text-sm font-semibold text-foreground">
                    {area.title}
                  </p>
                </div>
                <p className="mt-3 text-sm text-muted-foreground leading-relaxed">
                  {area.body}
                </p>
              </li>
            );
          })}
        </ul>
      </PublicSection>

      <PublicCtaBand
        title={CTA_BAND_COPY.title}
        description={CTA_BAND_COPY.description}
        primary={CTA_BAND_COPY.primary}
        secondary={CTA_BAND_COPY.secondary}
      />

      <PublicSection
        eyebrow={FAQ_SECTION.eyebrow}
        title={FAQ_SECTION.title}
        description={FAQ_SECTION.description}
      >
        <PublicFaq items={FAQ_ITEMS} />
      </PublicSection>
    </>
  );
}

export default HomePage;
