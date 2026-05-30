import { Link } from "react-router-dom";
import { PublicPageHeader } from "../components/PublicPageHeader";
import { PublicSection } from "../components/PublicSection";
import { PublicCtaBand } from "../components/PublicCtaBand";
import {
  HOW_IT_WORKS_COPY,
  HOW_IT_WORKS_CTA_BAND,
  HOW_IT_WORKS_DETAILED_STEPS,
  HOW_IT_WORKS_PAGE_SECTION,
  HOW_IT_WORKS_PRINCIPLES,
  HOW_IT_WORKS_PRINCIPLES_SECTION,
} from "../content/publicCopy";

// F2.21.3 — real /how-it-works page. Eight-step flow + onboarding
// principles. Replaces the F2.21.1 shell. The intro and principles
// explicitly say self-serve signup is not available yet and that
// merchants remain responsible for their own legal/compliance
// obligations.

export function HowItWorksPage() {
  return (
    <>
      <PublicPageHeader
        eyebrow={HOW_IT_WORKS_COPY.eyebrow}
        title={HOW_IT_WORKS_COPY.headline}
        description={HOW_IT_WORKS_COPY.subhead}
        actions={
          <>
            <Link
              to={HOW_IT_WORKS_COPY.primaryCta.to}
              className="premium-action inline-flex h-10 items-center justify-center rounded-full px-5 text-sm font-semibold text-primary-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {HOW_IT_WORKS_COPY.primaryCta.label}
            </Link>
            <Link
              to={HOW_IT_WORKS_COPY.secondaryCta.to}
              className="inline-flex h-10 items-center justify-center rounded-full border border-foreground/12 bg-foreground/8 px-5 text-sm font-medium text-foreground backdrop-blur-xl transition-colors hover:bg-foreground/12 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {HOW_IT_WORKS_COPY.secondaryCta.label}
            </Link>
          </>
        }
      />

      <PublicSection
        eyebrow={HOW_IT_WORKS_PAGE_SECTION.eyebrow}
        title={HOW_IT_WORKS_PAGE_SECTION.title}
        description={HOW_IT_WORKS_PAGE_SECTION.description}
      >
        <ol className="grid gap-4 md:grid-cols-2">
          {HOW_IT_WORKS_DETAILED_STEPS.map((step) => (
            <li
              key={step.step}
              className="premium-glass-soft flex items-start gap-4 rounded-lg p-5"
            >
              <span className="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-sm font-semibold text-primary ring-1 ring-primary/20">
                {step.step}
              </span>
              <div>
                <p className="text-sm font-semibold text-foreground">
                  {step.title}
                </p>
                <p className="mt-1 text-sm leading-relaxed text-foreground/62">
                  {step.body}
                </p>
              </div>
            </li>
          ))}
        </ol>
      </PublicSection>

      <PublicSection
        eyebrow={HOW_IT_WORKS_PRINCIPLES_SECTION.eyebrow}
        title={HOW_IT_WORKS_PRINCIPLES_SECTION.title}
        tone="muted"
      >
        <ul className="grid gap-3 md:grid-cols-2">
          {HOW_IT_WORKS_PRINCIPLES.map((principle) => (
            <li
              key={principle}
              className="premium-glass-soft rounded-lg px-4 py-3 text-sm leading-relaxed text-foreground/82"
            >
              {principle}
            </li>
          ))}
        </ul>
      </PublicSection>

      <PublicCtaBand
        title={HOW_IT_WORKS_CTA_BAND.title}
        description={HOW_IT_WORKS_CTA_BAND.description}
        primary={HOW_IT_WORKS_CTA_BAND.primary}
        secondary={HOW_IT_WORKS_CTA_BAND.secondary}
      />
    </>
  );
}

export default HowItWorksPage;
