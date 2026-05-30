import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { PublicSection } from "../components/PublicSection";
import { PublicCtaBand } from "../components/PublicCtaBand";
import { PublicHero } from "../components/PublicHero";
import { PublicTrustBand } from "../components/PublicTrustBand";
import { PublicFeatureGrid } from "../components/PublicFeatureGrid";
import { PublicFaq } from "../components/PublicFaq";
import { useMobileCopy } from "../components/useMobileCopy";
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

const MOBILE_PROBLEM_TITLES: Record<string, string> = {
  "Product data scattered across tools": "Scattered products",
  "Inventory and orders disconnected": "Disconnected ops",
  "Compliance visibility is hard to monitor": "Compliance gaps",
  "Manual operations slow teams down": "Manual work",
  "Platform operators need centralized oversight": "Central oversight",
};

const MOBILE_SOLUTION_TITLES: Record<string, string> = {
  "Store workspace": "Store",
  "Admin console": "Admin",
  "Connected operations": "Connected ops",
};

const MOBILE_STEP_TITLES: Record<string, string> = {
  "Request a demo": "Request demo",
  "Set up store operations": "Store setup",
  "Organize products and inventory": "Products + inventory",
  "Monitor orders and compliance visibility": "Orders + compliance",
  "Use platform oversight and audit history": "Oversight + audit",
};

const MOBILE_OPERATION_TITLES: Record<string, string> = {
  "Admin oversight": "Admin",
};

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
  const isMobileCopy = useMobileCopy();

  return (
    <>
      <PublicHero
        eyebrow={HERO_COPY.eyebrow}
        headline={HERO_COPY.headline}
        mobileHeadline="Run regulated retail clearly."
        subhead={HERO_COPY.subhead}
        mobileSubhead="Products, inventory, orders, compliance, and audit in one workspace."
        primary={HERO_COPY.primaryCta}
        secondary={HERO_COPY.secondaryCta}
      />

      <PublicTrustBand points={TRUST_POINTS} />

      <PublicSection
        eyebrow={PROBLEM_SECTION.eyebrow}
        title={PROBLEM_SECTION.title}
        mobileTitle="What gets messy."
        description={PROBLEM_SECTION.description}
        mobileDescription="Scattered tools make daily operations harder."
      >
        <ul className="grid gap-4 md:grid-cols-2">
          {PROBLEMS.map((problem) => (
            <li
              key={problem.title}
              className="premium-glass-soft rounded-lg p-5"
            >
              <p className="text-sm font-semibold text-foreground">
                {isMobileCopy
                  ? MOBILE_PROBLEM_TITLES[problem.title] ?? problem.title
                  : problem.title}
              </p>
              <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-foreground/62 sm:line-clamp-none">
                {problem.body}
              </p>
            </li>
          ))}
        </ul>
      </PublicSection>

      <PublicSection
        eyebrow={SOLUTION_SECTION.eyebrow}
        title={SOLUTION_SECTION.title}
        mobileTitle="One workspace."
        description={SOLUTION_SECTION.description}
        mobileDescription="Store operations, admin oversight, and audit stay connected."
        tone="muted"
      >
        <ul className="grid gap-4 md:grid-cols-3">
          {SOLUTION_PILLARS.map((pillar) => {
            const Icon = pillar.icon;
            return (
              <li
                key={pillar.title}
                className="premium-glass-soft rounded-lg p-5 transition-transform duration-300 hover:-translate-y-1"
              >
                <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/20">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
                <p className="mt-4 text-sm font-semibold text-foreground">
                  {isMobileCopy
                    ? MOBILE_SOLUTION_TITLES[pillar.title] ?? pillar.title
                    : pillar.title}
                </p>
                <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-foreground/62 sm:line-clamp-none">
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
        mobileTitle="What ships today."
        description={FEATURES_SECTION.description}
        mobileDescription="Product, inventory, order, compliance, admin, and audit screens."
      >
        <PublicFeatureGrid features={FEATURES} />
      </PublicSection>

      <PublicSection
        eyebrow={HOW_IT_WORKS_SECTION.eyebrow}
        title={HOW_IT_WORKS_SECTION.title}
        mobileTitle="How onboarding works."
        description={HOW_IT_WORKS_SECTION.description}
        mobileDescription="Start with a demo. The team handles setup with you."
        tone="muted"
      >
        <ol className="space-y-4">
          {HOW_IT_WORKS_STEPS.map((step) => (
            <li
              key={step.step}
              className="premium-glass-soft flex items-start gap-4 rounded-lg p-5"
            >
              <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-sm font-semibold text-primary ring-1 ring-primary/20">
                {step.step}
              </span>
              <div>
                <p className="text-sm font-semibold text-foreground">
                  {isMobileCopy
                    ? MOBILE_STEP_TITLES[step.title] ?? step.title
                    : step.title}
                </p>
                <p className="mt-1 line-clamp-2 text-sm leading-relaxed text-foreground/62 sm:line-clamp-none">
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
        mobileTitle="Built for regulated retail."
        description={REGULATED_COMMERCE_COPY.body}
        mobileDescription="Compliance visibility lives beside daily operations."
      >
        <ul className="space-y-3">
          {REGULATED_COMMERCE_COPY.highlights.map((highlight) => (
            <li
              key={highlight}
              className="premium-glass-soft rounded-lg px-4 py-3 text-sm leading-relaxed text-foreground/82"
            >
              {highlight}
            </li>
          ))}
        </ul>
      </PublicSection>

      <PublicSection
        eyebrow={OPERATIONS_PREVIEW_SECTION.eyebrow}
        title={OPERATIONS_PREVIEW_SECTION.title}
        mobileTitle="Operations preview."
        description={OPERATIONS_PREVIEW_SECTION.description}
        mobileDescription="The core areas NubeRush organizes today."
        tone="muted"
      >
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {OPERATIONS_PREVIEW_AREAS.map((area) => {
            const Icon = area.icon;
            return (
              <li
                key={area.title}
                className="premium-glass-soft rounded-lg p-5 transition-transform duration-300 hover:-translate-y-1"
              >
                <div className="flex items-center gap-3">
                  <span className="inline-flex h-10 w-10 items-center justify-center rounded-lg bg-primary/10 text-primary ring-1 ring-primary/20">
                    <Icon className="h-4 w-4" aria-hidden="true" />
                  </span>
                  <p className="text-sm font-semibold text-foreground">
                    {isMobileCopy
                      ? MOBILE_OPERATION_TITLES[area.title] ?? area.title
                      : area.title}
                  </p>
                </div>
                <p className="mt-3 line-clamp-2 text-sm leading-relaxed text-foreground/62 sm:line-clamp-none">
                  {area.body}
                </p>
              </li>
            );
          })}
        </ul>
      </PublicSection>

      <PublicCtaBand
        title={CTA_BAND_COPY.title}
        mobileTitle="Talk to the team."
        description={CTA_BAND_COPY.description}
        mobileDescription="Request a demo or send a message."
        primary={CTA_BAND_COPY.primary}
        secondary={CTA_BAND_COPY.secondary}
      />

      <PublicSection
        eyebrow={FAQ_SECTION.eyebrow}
        title={FAQ_SECTION.title}
        mobileTitle="Questions."
        description={FAQ_SECTION.description}
      >
        <PublicFaq items={FAQ_ITEMS} />
      </PublicSection>
    </>
  );
}

export default HomePage;
