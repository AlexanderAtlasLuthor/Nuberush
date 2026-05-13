import { Link } from "react-router-dom";
import { PublicPageHeader } from "../components/PublicPageHeader";
import { PublicSection } from "../components/PublicSection";
import { PublicLegalNotice } from "../components/PublicLegalNotice";
import {
  LEGAL_CONTACT_EMAIL,
  LEGAL_CONTACT_MAILTO,
  LEGAL_DOCUMENT_STATUS,
  LEGAL_HUB_DOCUMENTS,
  LEGAL_LAST_UPDATED,
} from "../content/legalDrafts";

// F2.21.5 — real /legal hub. Links into the five draft documents,
// shows the locked draft notice, includes shared metadata, and
// surfaces the business contact email.

export function LegalHubPage() {
  return (
    <>
      <PublicPageHeader
        eyebrow="Legal"
        title="Legal documents."
        description="Index of NubeRush legal and trust documents. Every document below is an operational draft pending review by qualified legal counsel — it is not currently binding and is not legal advice."
      />

      <PublicSection>
        <PublicLegalNotice />

        <dl className="mt-6 grid gap-3 sm:grid-cols-2 rounded-xl border border-border bg-card p-5 text-sm">
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Status
            </dt>
            <dd className="mt-1 text-foreground">{LEGAL_DOCUMENT_STATUS}</dd>
          </div>
          <div>
            <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Last updated
            </dt>
            <dd className="mt-1 text-foreground">{LEGAL_LAST_UPDATED}</dd>
          </div>
        </dl>

        <ul className="mt-8 grid gap-4 md:grid-cols-2">
          {LEGAL_HUB_DOCUMENTS.map((doc) => (
            <li key={doc.slug}>
              <Link
                to={doc.href}
                className="block rounded-xl border border-border bg-card p-5 hover:border-primary/40 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
              >
                <p className="text-sm font-semibold text-foreground">
                  {doc.title}
                </p>
                <p className="mt-2 text-sm text-muted-foreground leading-relaxed">
                  {doc.description}
                </p>
              </Link>
            </li>
          ))}
        </ul>

        <div className="mt-10 rounded-xl border border-border bg-card/40 p-5 text-sm">
          <p className="font-semibold text-foreground">Contact</p>
          <p className="mt-2 text-muted-foreground leading-relaxed">
            For questions about any of the documents on this page, reach the
            NubeRush team at{" "}
            <a
              href={LEGAL_CONTACT_MAILTO}
              className="text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background rounded-sm"
            >
              {LEGAL_CONTACT_EMAIL}
            </a>
            .
          </p>
        </div>
      </PublicSection>
    </>
  );
}

export default LegalHubPage;
