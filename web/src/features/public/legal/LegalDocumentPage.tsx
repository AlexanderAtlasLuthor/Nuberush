import { Link } from "react-router-dom";
import { ChevronLeft } from "lucide-react";
import { PublicPageHeader } from "../components/PublicPageHeader";
import { PublicLegalNotice } from "../components/PublicLegalNotice";
import {
  LEGAL_CONTACT_EMAIL,
  LEGAL_CONTACT_MAILTO,
  LEGAL_DOCUMENT_STATUS,
  LEGAL_EFFECTIVE_DATE,
  LEGAL_LAST_UPDATED,
  type LegalDocument,
} from "../content/legalDrafts";

interface LegalDocumentPageProps {
  document: LegalDocument;
}

// F2.21.5 — real legal document renderer. Pulls structured sections
// from legalDrafts.ts and renders a semantic <article> with metadata,
// draft notice, table of contents, sections (h2 per heading), and a
// contact line. Replaces the F2.21.1 shell wrapper.

export function LegalDocumentPage({ document }: LegalDocumentPageProps) {
  return (
    <>
      <PublicPageHeader
        eyebrow="Legal"
        title={document.title}
        description={document.description}
      />

      <section className="w-full bg-background py-12">
        <div className="container max-w-3xl">
          <p className="text-sm">
            <Link
              to="/legal"
              className="inline-flex items-center gap-1 text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              Back to Legal hub
            </Link>
          </p>

          <dl className="mt-6 grid gap-3 sm:grid-cols-3 rounded-xl border border-border bg-card p-5 text-sm">
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Status
              </dt>
              <dd className="mt-1 text-foreground">
                {LEGAL_DOCUMENT_STATUS}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Effective date
              </dt>
              <dd className="mt-1 text-foreground">
                {LEGAL_EFFECTIVE_DATE}
              </dd>
            </div>
            <div>
              <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Last updated
              </dt>
              <dd className="mt-1 text-foreground">{LEGAL_LAST_UPDATED}</dd>
            </div>
          </dl>

          <div className="mt-6">
            <PublicLegalNotice />
          </div>

          <nav
            aria-label={`${document.title} table of contents`}
            className="mt-8 rounded-xl border border-border bg-card/40 p-5"
          >
            <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Sections
            </p>
            <ol className="mt-3 grid gap-2 sm:grid-cols-2 text-sm">
              {document.sections.map((section, index) => (
                <li key={section.id}>
                  <a
                    href={`#${section.id}`}
                    className="text-foreground/90 hover:text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm"
                  >
                    {index + 1}. {section.heading}
                  </a>
                </li>
              ))}
            </ol>
          </nav>

          <article className="mt-10 space-y-10">
            {document.sections.map((section) => (
              <section key={section.id} id={section.id}>
                <h2 className="text-xl md:text-2xl font-semibold tracking-tight text-foreground">
                  {section.heading}
                </h2>
                {section.paragraphs?.map((p, idx) => (
                  <p
                    key={`${section.id}-p-${idx}`}
                    className="mt-3 text-sm text-foreground/90 leading-relaxed"
                  >
                    {p}
                  </p>
                ))}
                {section.bullets && (
                  <ul className="mt-3 space-y-2 text-sm text-foreground/90 leading-relaxed list-disc pl-5">
                    {section.bullets.map((bullet) => (
                      <li key={bullet}>{bullet}</li>
                    ))}
                  </ul>
                )}
              </section>
            ))}
          </article>

          <div className="mt-12 rounded-xl border border-border bg-card p-5 text-sm">
            <p className="font-semibold text-foreground">Contact</p>
            <p className="mt-2 text-muted-foreground leading-relaxed">
              Reach the NubeRush team at{" "}
              <a
                href={LEGAL_CONTACT_MAILTO}
                className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm"
              >
                {LEGAL_CONTACT_EMAIL}
              </a>
              .
            </p>
          </div>

          <p className="mt-8 text-sm">
            <Link
              to="/legal"
              className="inline-flex items-center gap-1 text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm"
            >
              <ChevronLeft className="h-4 w-4" aria-hidden="true" />
              Back to Legal hub
            </Link>
          </p>
        </div>
      </section>
    </>
  );
}

export default LegalDocumentPage;
