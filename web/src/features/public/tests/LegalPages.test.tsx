import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";

import { LegalHubPage } from "../legal/LegalHubPage";
import { TermsPage } from "../legal/TermsPage";
import { PrivacyPage } from "../legal/PrivacyPage";
import { MerchantAgreementPage } from "../legal/MerchantAgreementPage";
import { AcceptableUsePage } from "../legal/AcceptableUsePage";
import { CookiesPage } from "../legal/CookiesPage";
import {
  LEGAL_DOCUMENT_STATUS,
  LEGAL_EFFECTIVE_DATE,
  LEGAL_LAST_UPDATED,
} from "../content/legalDrafts";

function renderPage(node: ReactNode) {
  return render(<MemoryRouter>{node}</MemoryRouter>);
}

function expectInternalLinkTo(label: RegExp, href: string) {
  const matches = screen.getAllByRole("link", { name: label });
  expect(matches.length).toBeGreaterThan(0);
  expect(matches.some((el) => el.getAttribute("href") === href)).toBe(true);
}

// ───────────────────────────────────────────────────────────────────
// /legal hub
// ───────────────────────────────────────────────────────────────────

describe("LegalHubPage (F2.21.5)", () => {
  it("renders exactly one h1", () => {
    renderPage(<LegalHubPage />);
    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent(/legal documents/i);
  });

  it("renders the locked draft notice", () => {
    renderPage(<LegalHubPage />);
    expect(
      screen.getByText(
        /this document is provided as an operational draft for review and approval by qualified legal counsel before public launch/i,
      ),
    ).toBeInTheDocument();
  });

  it.each([
    ["/legal/terms", "Terms of Service"],
    ["/legal/privacy", "Privacy Policy"],
    ["/legal/merchant-agreement", "Merchant Agreement"],
    ["/legal/acceptable-use", "Acceptable Use Policy"],
    ["/legal/cookies", "Cookie Policy"],
  ])("links to %s with title %s", (href, title) => {
    renderPage(<LegalHubPage />);
    const link = screen.getByRole("link", {
      name: new RegExp(title, "i"),
    });
    expect(link).toHaveAttribute("href", href);
  });

  it("exposes the business contact email as a mailto link", () => {
    renderPage(<LegalHubPage />);
    const matches = screen.getAllByRole("link", {
      name: /team@fuenmayorindustries\.com/i,
    });
    expect(matches.length).toBeGreaterThan(0);
    expect(
      matches.some(
        (el) =>
          el.getAttribute("href") === "mailto:team@fuenmayorindustries.com",
      ),
    ).toBe(true);
  });
});

// ───────────────────────────────────────────────────────────────────
// Per-document shared expectations
// ───────────────────────────────────────────────────────────────────

const LEGAL_DOCUMENTS: ReadonlyArray<{
  name: string;
  node: ReactNode;
  title: RegExp;
}> = [
  { name: "TermsPage", node: <TermsPage />, title: /^terms of service$/i },
  { name: "PrivacyPage", node: <PrivacyPage />, title: /^privacy policy$/i },
  {
    name: "MerchantAgreementPage",
    node: <MerchantAgreementPage />,
    title: /^merchant agreement$/i,
  },
  {
    name: "AcceptableUsePage",
    node: <AcceptableUsePage />,
    title: /^acceptable use policy$/i,
  },
  {
    name: "CookiesPage",
    node: <CookiesPage />,
    title: /^cookie policy$/i,
  },
];

describe.each(LEGAL_DOCUMENTS)("$name (F2.21.5)", ({ node, title }) => {
  it("renders exactly one h1 with the document title", () => {
    renderPage(node);
    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent(title);
  });

  it("renders the locked draft notice", () => {
    renderPage(node);
    expect(
      screen.getByText(
        /this document is provided as an operational draft for review and approval by qualified legal counsel before public launch/i,
      ),
    ).toBeInTheDocument();
  });

  it("renders document status and metadata", () => {
    renderPage(node);
    expect(screen.getByText(LEGAL_DOCUMENT_STATUS)).toBeInTheDocument();
    expect(screen.getByText(LEGAL_EFFECTIVE_DATE)).toBeInTheDocument();
    expect(screen.getByText(LEGAL_LAST_UPDATED)).toBeInTheDocument();
  });

  it("renders back-link to /legal hub", () => {
    renderPage(node);
    expectInternalLinkTo(/back to legal hub/i, "/legal");
  });

  it("renders the business contact email as a mailto link", () => {
    renderPage(node);
    const matches = screen.getAllByRole("link", {
      name: /team@fuenmayorindustries\.com/i,
    });
    expect(matches.length).toBeGreaterThan(0);
    expect(
      matches.some(
        (el) =>
          el.getAttribute("href") === "mailto:team@fuenmayorindustries.com",
      ),
    ).toBe(true);
  });
});

// ───────────────────────────────────────────────────────────────────
// Per-document required section headings
// ───────────────────────────────────────────────────────────────────

const TERMS_HEADINGS = [
  "Website use",
  "Account access",
  "Platform availability",
  "Prohibited use",
  "Intellectual property",
  "Disclaimers",
  "Limitation of liability",
  "Contact",
] as const;

const PRIVACY_HEADINGS = [
  "Information collected",
  "How information is used",
  "Contact/demo inquiries",
  "Cookies/basic analytics",
  "Service providers",
  "Data security",
  "User choices",
  "Contact",
] as const;

const MERCHANT_AGREEMENT_HEADINGS = [
  "Merchant responsibilities",
  "Product information accuracy",
  "Age-restricted product responsibility",
  "Compliance responsibility",
  "Platform role",
  "Orders/operations",
  "Fees/pricing by separate agreement",
  "Suspension/termination",
  "Audit/logs",
  "Contact",
] as const;

const ACCEPTABLE_USE_HEADINGS = [
  "No illegal products",
  "No evasion of age/compliance controls",
  "No fraudulent activity",
  "No platform abuse",
  "No scraping/misuse",
  "Enforcement",
  "Contact",
] as const;

const COOKIES_HEADINGS = [
  "What cookies are",
  "Essential cookies",
  "Analytics cookies if added later",
  "Managing cookies",
  "Contact",
] as const;

describe("TermsPage section headings", () => {
  it.each(TERMS_HEADINGS)("renders heading %s", (heading) => {
    renderPage(<TermsPage />);
    expect(screen.getAllByText(heading).length).toBeGreaterThan(0);
  });
});

describe("PrivacyPage section headings", () => {
  it.each(PRIVACY_HEADINGS)("renders heading %s", (heading) => {
    renderPage(<PrivacyPage />);
    expect(screen.getAllByText(heading).length).toBeGreaterThan(0);
  });
});

describe("MerchantAgreementPage section headings", () => {
  it.each(MERCHANT_AGREEMENT_HEADINGS)("renders heading %s", (heading) => {
    renderPage(<MerchantAgreementPage />);
    expect(screen.getAllByText(heading).length).toBeGreaterThan(0);
  });
});

describe("AcceptableUsePage section headings", () => {
  it.each(ACCEPTABLE_USE_HEADINGS)("renders heading %s", (heading) => {
    renderPage(<AcceptableUsePage />);
    expect(screen.getAllByText(heading).length).toBeGreaterThan(0);
  });
});

describe("CookiesPage section headings", () => {
  it.each(COOKIES_HEADINGS)("renders heading %s", (heading) => {
    renderPage(<CookiesPage />);
    expect(screen.getAllByText(heading).length).toBeGreaterThan(0);
  });
});

// ───────────────────────────────────────────────────────────────────
// Cross-page banned-claim guard (positive forms only)
// ───────────────────────────────────────────────────────────────────

const ALL_LEGAL_PAGES = [
  { name: "LegalHubPage", node: <LegalHubPage /> },
  ...LEGAL_DOCUMENTS.map(({ name, node }) => ({ name, node })),
];

describe.each(ALL_LEGAL_PAGES)(
  "$name banned-claim guard (F2.21.5)",
  ({ node }) => {
    it.each([
      /final legal approval/i,
      /attorney[-\s]approved/i,
      /\blegally approved\b/i,
      /\bregulator[-\s]approved\b/i,
      /certified compliant/i,
      /automatic legal verification/i,
      /guaranteed service availability/i,
      /no data sharing ever/i,
      /law enforcement partnership/i,
      /guaranteed detection/i,
      /guaranteed tracking[-\s]free/i,
      /\babsolute security\b/i,
    ])("never makes positive claim %s", (banned) => {
      renderPage(node);
      expect(screen.queryByText(banned)).not.toBeInTheDocument();
    });

    it("never makes a positive guaranteed-compliance claim", () => {
      renderPage(node);
      // Past-participle form only appears in positive constructions.
      // Disclaimers use "does not guarantee" (infinitive) and stay safe.
      expect(
        screen.queryByText(/\bguaranteed compliance\b/i),
      ).not.toBeInTheDocument();
    });

    it("never makes a positive legal-advice claim", () => {
      renderPage(node);
      // Pattern matches direct positive constructions only. Safe
      // disclaimers like "is not legal advice" do not match.
      expect(
        screen.queryByText(
          /this (?:is|constitutes|provides) legal advice/i,
        ),
      ).not.toBeInTheDocument();
      expect(
        screen.queryByText(
          /(?:we|nuberush) (?:provide|offer|give|are providing) legal advice/i,
        ),
      ).not.toBeInTheDocument();
    });

    it.each([
      /\buber\b/i,
      /doordash/i,
      /\btoast\b/i,
      /\bsquare\b/i,
      /\bstripe\b/i,
      /\bshopify\b/i,
    ])("does not reference competitor %s", (competitor) => {
      renderPage(node);
      expect(screen.queryByText(competitor)).not.toBeInTheDocument();
    });
  },
);
