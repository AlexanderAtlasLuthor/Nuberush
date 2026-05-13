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
              className="inline-flex items-center justify-center h-10 px-5 rounded-md text-sm font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {HOW_IT_WORKS_COPY.primaryCta.label}
            </Link>
            <Link
              to={HOW_IT_WORKS_COPY.secondaryCta.to}
              className="inline-flex items-center justify-center h-10 px-5 rounded-md text-sm font-medium border border-border text-foreground hover:bg-accent hover:text-accent-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
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
        <ol className="space-y-4">
          {HOW_IT_WORKS_DETAILED_STEPS.map((step) => (
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
      </PublicSection>

      <PublicSection
        eyebrow={HOW_IT_WORKS_PRINCIPLES_SECTION.eyebrow}
        title={HOW_IT_WORKS_PRINCIPLES_SECTION.title}
        tone="muted"
      >
        <ul className="space-y-3">
          {HOW_IT_WORKS_PRINCIPLES.map((principle) => (
            <li
              key={principle}
              className="rounded-lg border border-border bg-card/60 px-4 py-3 text-sm text-foreground/90 leading-relaxed"
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
