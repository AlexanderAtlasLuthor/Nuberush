import { Link } from "react-router-dom";
import { PublicPageHeader } from "../components/PublicPageHeader";
import { PublicSection } from "../components/PublicSection";
import {
  BUSINESS_EMAIL,
  BUSINESS_EMAIL_MAILTO,
  CONTACT_CHECKLIST_SECTION,
  CONTACT_CTA_SECTION,
  CONTACT_EMAIL_CHECKLIST,
  CONTACT_PAGE_COPY,
  CONTACT_SECTIONS,
} from "../content/publicCopy";

// F2.21.4 — real /contact page. Honest email-only contact surface.
// No form, no fake submit, no fake success state, no API. The page
// has exactly one mailto anchor that carries the email address as
// its accessible name; other mentions of the team use the same anchor
// (in the CTA section) or refer to the team without spelling out
// the address, so getByRole queries stay stable.

export function ContactPage() {
  return (
    <>
      <PublicPageHeader
        eyebrow={CONTACT_PAGE_COPY.eyebrow}
        title={CONTACT_PAGE_COPY.headline}
        description={CONTACT_PAGE_COPY.subhead}
        actions={
          <>
            <a
              href={CONTACT_PAGE_COPY.primaryCta.href}
              className="premium-action inline-flex h-10 items-center justify-center rounded-full px-5 text-sm font-semibold text-primary-foreground transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {CONTACT_PAGE_COPY.primaryCta.label}
            </a>
            <Link
              to={CONTACT_PAGE_COPY.secondaryCta.to}
              className="inline-flex h-10 items-center justify-center rounded-full border border-foreground/12 bg-foreground/8 px-5 text-sm font-medium text-foreground backdrop-blur-xl transition-colors hover:bg-foreground/12 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              {CONTACT_PAGE_COPY.secondaryCta.label}
            </Link>
          </>
        }
      />

      <PublicSection
        eyebrow="How to reach us"
        title="Ways to contact the NubeRush team."
        description="Every conversation begins with a real message you send. We don't run a public form, ticketing queue, or always-on helpdesk."
      >
        <ul className="grid gap-4 md:grid-cols-2">
          {CONTACT_SECTIONS.map((section) => (
            <li
              key={section.title}
              className="premium-glass-soft rounded-lg p-5"
            >
              <p className="text-sm font-semibold text-foreground">
                {section.title}
              </p>
              <p className="mt-2 text-sm leading-relaxed text-foreground/62">
                {section.body}
              </p>
              {section.title === "Merchant demo inquiries" && (
                <p className="mt-3 text-sm">
                  <Link
                    to="/request-demo"
                    className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm"
                  >
                    Go to Request demo →
                  </Link>
                </p>
              )}
            </li>
          ))}
        </ul>
      </PublicSection>

      <PublicSection
        eyebrow={CONTACT_CHECKLIST_SECTION.eyebrow}
        title={CONTACT_CHECKLIST_SECTION.title}
        description={CONTACT_CHECKLIST_SECTION.description}
        tone="muted"
      >
        <ul className="grid gap-2 text-sm leading-relaxed text-foreground/78 md:grid-cols-2">
          {CONTACT_EMAIL_CHECKLIST.map((item) => (
            <li key={item} className="premium-glass-soft flex gap-2 rounded-lg px-4 py-3">
              <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-primary/80" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </PublicSection>

      <PublicSection
        eyebrow={CONTACT_CTA_SECTION.eyebrow}
        title={CONTACT_CTA_SECTION.title}
        description={CONTACT_CTA_SECTION.description}
      >
        <div className="premium-glass rounded-lg p-6">
          <p className="text-sm font-semibold text-foreground">Email</p>
          <p className="mt-2 text-base">
            <a
              href={BUSINESS_EMAIL_MAILTO}
              className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm"
            >
              {BUSINESS_EMAIL}
            </a>
          </p>
          <p className="mt-4 text-sm leading-relaxed text-foreground/62">
            The team responds from this address. Response time varies by
            request.
          </p>
          <p className="mt-4 text-sm">
            <Link
              to="/request-demo"
              className="inline-flex h-9 items-center justify-center rounded-full border border-foreground/12 bg-foreground/8 px-4 text-sm font-medium text-foreground backdrop-blur-xl transition-colors hover:bg-foreground/12 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
            >
              Request demo
            </Link>
          </p>
        </div>
      </PublicSection>
    </>
  );
}

export default ContactPage;
