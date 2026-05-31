import { Link } from "react-router-dom";
import { PublicPageHeader } from "../components/PublicPageHeader";
import { PublicSection } from "../components/PublicSection";
import {
  BUSINESS_EMAIL,
  BUSINESS_EMAIL_MAILTO,
  REQUEST_DEMO_ACCESS_MODEL,
  REQUEST_DEMO_ACCESS_SECTION,
  REQUEST_DEMO_CHECKLIST,
  REQUEST_DEMO_CHECKLIST_SECTION,
  REQUEST_DEMO_CTA_SECTION,
  REQUEST_DEMO_PAGE_COPY,
  REQUEST_DEMO_SECTIONS,
} from "../content/publicCopy";

// F2.24 — /request-demo repurposed as the merchant application surface.
// Explains the apply-and-review onboarding flow and funnels to the public
// /apply wizard. Still honest: no form on this page, no fake submit, no
// fake success state, no API. Exactly one mailto anchor carries the email
// address as its accessible name so existing contact-demo-honesty tests
// stay stable.

export function RequestDemoPage() {
  return (
    <>
      <PublicPageHeader
        eyebrow={REQUEST_DEMO_PAGE_COPY.eyebrow}
        title={REQUEST_DEMO_PAGE_COPY.headline}
        description={REQUEST_DEMO_PAGE_COPY.subhead}
        actions={
          <>
            <Link
              to={REQUEST_DEMO_PAGE_COPY.primaryCta.to}
              className="inline-flex items-center justify-center h-10 px-5 rounded-md text-sm font-semibold bg-primary text-primary-foreground hover:bg-primary/90 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {REQUEST_DEMO_PAGE_COPY.primaryCta.label}
            </Link>
            <Link
              to={REQUEST_DEMO_PAGE_COPY.secondaryCta.to}
              className="inline-flex items-center justify-center h-10 px-5 rounded-md text-sm font-medium border border-border text-foreground hover:bg-accent hover:text-accent-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {REQUEST_DEMO_PAGE_COPY.secondaryCta.label}
            </Link>
          </>
        }
      />

      <PublicSection
        eyebrow="Apply intent"
        title="What applying to NubeRush really means."
        description="A short, honest overview of how the application works at NubeRush — who it's for, what happens next, and what to expect."
      >
        <ul className="grid gap-4 md:grid-cols-2">
          {REQUEST_DEMO_SECTIONS.map((section) => (
            <li
              key={section.title}
              className="rounded-xl border border-border bg-card p-5"
            >
              <p className="text-sm font-semibold text-foreground">
                {section.title}
              </p>
              <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                {section.body}
              </p>
            </li>
          ))}
        </ul>
      </PublicSection>

      <PublicSection
        eyebrow={REQUEST_DEMO_CHECKLIST_SECTION.eyebrow}
        title={REQUEST_DEMO_CHECKLIST_SECTION.title}
        tone="muted"
      >
        <ul className="space-y-2 text-sm text-foreground/90 leading-relaxed list-disc pl-5">
          {REQUEST_DEMO_CHECKLIST.map((item) => (
            <li key={item}>{item}</li>
          ))}
        </ul>
      </PublicSection>

      <PublicSection
        eyebrow={REQUEST_DEMO_ACCESS_SECTION.eyebrow}
        title={REQUEST_DEMO_ACCESS_SECTION.title}
      >
        <ul className="space-y-3">
          {REQUEST_DEMO_ACCESS_MODEL.map((note) => (
            <li
              key={note}
              className="rounded-lg border border-border bg-card/60 px-4 py-3 text-sm text-foreground/90 leading-relaxed"
            >
              {note}
            </li>
          ))}
        </ul>
      </PublicSection>

      <PublicSection
        eyebrow={REQUEST_DEMO_CTA_SECTION.eyebrow}
        title={REQUEST_DEMO_CTA_SECTION.title}
        description={REQUEST_DEMO_CTA_SECTION.description}
        tone="muted"
      >
        <div className="rounded-xl border border-border bg-card p-6">
          <p className="text-sm font-semibold text-foreground">Email</p>
          <p className="mt-2 text-base">
            <a
              href={BUSINESS_EMAIL_MAILTO}
              className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm"
            >
              {BUSINESS_EMAIL}
            </a>
          </p>
          <p className="mt-4 text-sm text-muted-foreground leading-relaxed">
            The team responds from this address. Response time varies by
            request.
          </p>
          <p className="mt-4 text-sm">
            <Link
              to="/how-it-works"
              className="inline-flex items-center justify-center h-9 px-4 rounded-md text-sm font-medium border border-border text-foreground hover:bg-accent hover:text-accent-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              See how it works
            </Link>
          </p>
        </div>
      </PublicSection>
    </>
  );
}

export default RequestDemoPage;
