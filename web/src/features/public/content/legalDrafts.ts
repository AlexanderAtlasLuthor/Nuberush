// F2.21.5 — Structured legal/trust draft content.
//
// Every document in this module is an operational DRAFT pending
// review by qualified legal counsel. The text below is original
// NubeRush copy, not adapted from any third-party policy. Future
// counsel review will refine, expand, or replace the wording before
// any public launch.

import { BUSINESS_EMAIL, BUSINESS_EMAIL_MAILTO } from "./publicCopy";

export const LEGAL_DRAFT_NOTICE =
  "Draft notice: This document is provided as an operational draft for review and approval by qualified legal counsel before public launch.";

export const LEGAL_DOCUMENT_STATUS = "Draft pending legal review";
export const LEGAL_EFFECTIVE_DATE = "Pending legal review";
export const LEGAL_LAST_UPDATED = "May 2026";

export const LEGAL_CONTACT_EMAIL = BUSINESS_EMAIL;
export const LEGAL_CONTACT_MAILTO = BUSINESS_EMAIL_MAILTO;

export type LegalDocumentSlug =
  | "terms"
  | "privacy"
  | "merchant-agreement"
  | "acceptable-use"
  | "cookies";

export interface LegalSection {
  /** Anchor-friendly id used for TOC links. */
  id: string;
  /** Section heading text. Matches what tests assert verbatim. */
  heading: string;
  paragraphs?: ReadonlyArray<string>;
  bullets?: ReadonlyArray<string>;
}

export interface LegalDocument {
  slug: LegalDocumentSlug;
  title: string;
  description: string;
  sections: ReadonlyArray<LegalSection>;
}

export interface LegalDocumentLink {
  slug: LegalDocumentSlug;
  title: string;
  href: string;
  description: string;
}

export const LEGAL_HUB_DOCUMENTS: ReadonlyArray<LegalDocumentLink> = [
  {
    slug: "terms",
    title: "Terms of Service",
    href: "/legal/terms",
    description:
      "Website use, account access, platform availability, and the basic rules for using NubeRush.",
  },
  {
    slug: "privacy",
    title: "Privacy Policy",
    href: "/legal/privacy",
    description:
      "What information NubeRush collects and how it is handled across the website and platform.",
  },
  {
    slug: "merchant-agreement",
    title: "Merchant Agreement",
    href: "/legal/merchant-agreement",
    description:
      "Responsibilities for stores operating on NubeRush, including product information, age-restricted handling, and compliance.",
  },
  {
    slug: "acceptable-use",
    title: "Acceptable Use Policy",
    href: "/legal/acceptable-use",
    description: "What is and is not permitted on the NubeRush platform.",
  },
  {
    slug: "cookies",
    title: "Cookie Policy",
    href: "/legal/cookies",
    description: "Cookies the website may use and how to manage them.",
  },
];

// ───────────────────────────────────────────────────────────────────
// Terms of Service
// ───────────────────────────────────────────────────────────────────

export const TERMS_DRAFT: LegalDocument = {
  slug: "terms",
  title: "Terms of Service",
  description:
    "Draft terms that govern use of the NubeRush public website and the NubeRush platform. These terms are pending legal review.",
  sections: [
    {
      id: "website-use",
      heading: "Website use",
      paragraphs: [
        "These draft Terms govern your use of the NubeRush public website and the NubeRush platform. By using the website, you agree to use it lawfully and in accordance with these draft Terms.",
        "Some pages on the website describe features that are under active development. Descriptions are provided in good faith and may change as the platform evolves.",
      ],
    },
    {
      id: "account-access",
      heading: "Account access",
      paragraphs: [
        "Authenticated areas of the platform — the store workspace and the admin console — are available only to users who have been onboarded by the NubeRush team. Self-serve signup is not available today.",
        "Account credentials are personal to each user. You agree not to share credentials and to notify NubeRush if you believe an account has been accessed without authorization.",
      ],
    },
    {
      id: "platform-availability",
      heading: "Platform availability",
      paragraphs: [
        "NubeRush works to keep the website and platform available, but service availability is not promised. Planned and unplanned downtime may occur as part of normal operation and maintenance.",
        "Features may be added, changed, or removed as the platform develops. The website will be updated to reflect material changes.",
      ],
    },
    {
      id: "prohibited-use",
      heading: "Prohibited use",
      paragraphs: [
        "You agree not to use the website or platform for unlawful purposes, to misuse the operational tools available to you, or to interfere with the security or normal functioning of the platform.",
      ],
      bullets: [
        "Attempting to evade authentication, age, or compliance controls.",
        "Probing, scanning, or testing the platform without authorization.",
        "Misrepresenting your identity, business, or relationship to NubeRush.",
        "Using automated means to scrape or extract content.",
      ],
    },
    {
      id: "intellectual-property",
      heading: "Intellectual property",
      paragraphs: [
        "NubeRush and its content — including text, design, code, logos, and trademarks — are owned by NubeRush or its licensors and are protected by applicable intellectual property laws.",
        "You may not copy, modify, or redistribute the website or platform without written permission, except where applicable law expressly allows.",
      ],
    },
    {
      id: "disclaimers",
      heading: "Disclaimers",
      paragraphs: [
        "The website and platform are provided on an “as is” and “as available” basis. To the extent permitted by law, NubeRush disclaims warranties of merchantability, fitness for a particular purpose, and non-infringement.",
        "Nothing on the website or platform is intended as professional or legal counsel. Users should consult their own qualified advisors for advice that applies to their specific situation.",
      ],
    },
    {
      id: "limitation-of-liability",
      heading: "Limitation of liability",
      paragraphs: [
        "To the extent permitted by applicable law, NubeRush is not liable for indirect, incidental, or consequential damages arising from your use of the website or platform.",
        "Some jurisdictions may not allow these limitations; applicable consumer-protection laws are not affected by this draft.",
      ],
    },
    {
      id: "contact",
      heading: "Contact",
      paragraphs: [
        "Questions about these draft Terms can be sent to the NubeRush team at the email address listed below.",
      ],
    },
  ],
};

// ───────────────────────────────────────────────────────────────────
// Privacy Policy
// ───────────────────────────────────────────────────────────────────

export const PRIVACY_DRAFT: LegalDocument = {
  slug: "privacy",
  title: "Privacy Policy",
  description:
    "Draft policy describing what information NubeRush collects and how it is used. Pending legal review.",
  sections: [
    {
      id: "information-collected",
      heading: "Information collected",
      paragraphs: [
        "NubeRush collects information you provide directly to us — for example by emailing the team, submitting a demo request, or using authenticated areas of the platform after being onboarded.",
      ],
      bullets: [
        "Business and contact details you share in inquiries.",
        "Account details when you are set up on the platform by the NubeRush team.",
        "Operational records created while using the store workspace or admin console.",
        "Technical information that a standard website or web application typically receives, such as basic request metadata.",
      ],
    },
    {
      id: "how-information-is-used",
      heading: "How information is used",
      paragraphs: [
        "Information is used to respond to inquiries, deliver and operate the platform, support operators, and improve the product.",
        "NubeRush does not sell personal information.",
      ],
    },
    {
      id: "contact-demo-inquiries",
      heading: "Contact/demo inquiries",
      paragraphs: [
        "When you email the team or use the Request demo page, the message and the business and contact details you include are stored so the team can respond, route, and follow up on your request.",
      ],
    },
    {
      id: "cookies-basic-analytics",
      heading: "Cookies/basic analytics",
      paragraphs: [
        "The website and platform may use cookies that support normal operation, such as session and security cookies. Analytics cookies are not part of the default website experience today; if they are added in the future, this Policy will be updated to describe what is collected.",
        "See the Cookie Policy for more detail on how cookies are used.",
      ],
    },
    {
      id: "service-providers",
      heading: "Service providers",
      paragraphs: [
        "NubeRush works with service providers — for example hosting, infrastructure, and email — that may process information on our behalf under appropriate terms. The list of service providers may change as the platform evolves.",
      ],
    },
    {
      id: "data-security",
      heading: "Data security",
      paragraphs: [
        "NubeRush takes reasonable steps to protect information against unauthorized access, alteration, and disclosure. No system is fully secure, and security cannot be unconditionally promised.",
      ],
    },
    {
      id: "user-choices",
      heading: "User choices",
      paragraphs: [
        "You can ask to update, correct, or delete information you have provided. Some information may need to be retained for legal, operational, or audit reasons; the team will explain when that applies.",
      ],
    },
    {
      id: "contact",
      heading: "Contact",
      paragraphs: [
        "For privacy questions or requests, email the NubeRush team at the address listed below.",
      ],
    },
  ],
};

// ───────────────────────────────────────────────────────────────────
// Merchant Agreement
// ───────────────────────────────────────────────────────────────────

export const MERCHANT_AGREEMENT_DRAFT: LegalDocument = {
  slug: "merchant-agreement",
  title: "Merchant Agreement",
  description:
    "Draft agreement covering responsibilities for stores operating on NubeRush. Pending legal review.",
  sections: [
    {
      id: "merchant-responsibilities",
      heading: "Merchant responsibilities",
      paragraphs: [
        "Merchants operating on NubeRush are responsible for running their store lawfully and for understanding and following the laws that apply to their business and the products they sell.",
      ],
    },
    {
      id: "product-information-accuracy",
      heading: "Product information accuracy",
      paragraphs: [
        "Merchants are responsible for the accuracy of the product information they list on the platform — including descriptions, status, compliance signals, and inventory.",
      ],
    },
    {
      id: "age-restricted-product-responsibility",
      heading: "Age-restricted product responsibility",
      paragraphs: [
        "Merchants who handle age-restricted products are responsible for following age-verification, identity-verification, and other regulatory requirements that apply to their store, jurisdiction, and product mix.",
      ],
    },
    {
      id: "compliance-responsibility",
      heading: "Compliance responsibility",
      paragraphs: [
        "NubeRush provides tools and visibility that support compliance-aware workflows. NubeRush does not guarantee compliance with any specific law and does not assume merchant legal responsibility. Compliance remains the merchant's obligation.",
      ],
    },
    {
      id: "platform-role",
      heading: "Platform role",
      paragraphs: [
        "NubeRush provides the operating platform — store workspace, admin console, products, inventory, orders, compliance visibility, audit, and operations alerts. NubeRush is not a party to merchant transactions and does not act on behalf of merchants.",
      ],
    },
    {
      id: "orders-operations",
      heading: "Orders/operations",
      paragraphs: [
        "Merchants use NubeRush to manage their own product, inventory, and order operations. Operational decisions remain with the merchant.",
      ],
    },
    {
      id: "fees-pricing-by-separate-agreement",
      heading: "Fees/pricing by separate agreement",
      paragraphs: [
        "Fees, commissions, billing, and pricing — if any — are governed by a separate written agreement with NubeRush. This public draft does not establish pricing terms or commercial obligations.",
      ],
    },
    {
      id: "suspension-termination",
      heading: "Suspension/termination",
      paragraphs: [
        "NubeRush may suspend or terminate access in response to violations of this draft, the Acceptable Use Policy, applicable law, or for operational reasons described in a separate written agreement.",
      ],
    },
    {
      id: "audit-logs",
      heading: "Audit/logs",
      paragraphs: [
        "Operational activity may be recorded in the platform's audit logs to support accountable review by merchants and platform admins.",
      ],
    },
    {
      id: "contact",
      heading: "Contact",
      paragraphs: [
        "Questions about this Merchant Agreement draft can be sent to the NubeRush team at the email address listed below.",
      ],
    },
  ],
};

// ───────────────────────────────────────────────────────────────────
// Acceptable Use Policy
// ───────────────────────────────────────────────────────────────────

export const ACCEPTABLE_USE_DRAFT: LegalDocument = {
  slug: "acceptable-use",
  title: "Acceptable Use Policy",
  description:
    "Draft policy outlining what is and is not permitted on the NubeRush platform. Pending legal review.",
  sections: [
    {
      id: "no-illegal-products",
      heading: "No illegal products",
      paragraphs: [
        "You may not use NubeRush to list, offer, or distribute products that are unlawful in the jurisdictions where they are made available.",
      ],
    },
    {
      id: "no-evasion-of-age-compliance-controls",
      heading: "No evasion of age/compliance controls",
      paragraphs: [
        "You may not attempt to bypass age-verification, compliance, or operational controls provided by the platform or required by applicable law.",
      ],
    },
    {
      id: "no-fraudulent-activity",
      heading: "No fraudulent activity",
      paragraphs: [
        "You may not use the platform to engage in fraud — including identity misrepresentation, falsified business records, or fraudulent operational activity.",
      ],
    },
    {
      id: "no-platform-abuse",
      heading: "No platform abuse",
      paragraphs: [
        "You may not abuse other users, send unsolicited communications, harass the team, or otherwise interfere with the normal use of the platform by others.",
      ],
    },
    {
      id: "no-scraping-misuse",
      heading: "No scraping/misuse",
      paragraphs: [
        "You may not scrape, harvest, or extract content from the platform by automated means without written permission, and you may not reverse-engineer or attempt to compromise the platform.",
      ],
    },
    {
      id: "enforcement",
      heading: "Enforcement",
      paragraphs: [
        "NubeRush may respond to violations of this draft policy by limiting, suspending, or terminating access. Enforcement is operational; it is not a substitute for any legal process that may apply.",
      ],
    },
    {
      id: "contact",
      heading: "Contact",
      paragraphs: [
        "Report concerns or questions about acceptable use to the NubeRush team at the email address listed below.",
      ],
    },
  ],
};

// ───────────────────────────────────────────────────────────────────
// Cookie Policy
// ───────────────────────────────────────────────────────────────────

export const COOKIES_DRAFT: LegalDocument = {
  slug: "cookies",
  title: "Cookie Policy",
  description:
    "Draft policy explaining cookies the website and platform may use. Pending legal review.",
  sections: [
    {
      id: "what-cookies-are",
      heading: "What cookies are",
      paragraphs: [
        "Cookies are small pieces of information stored by your browser when you visit a website. They are commonly used to support normal website operation, security, and analytics.",
      ],
    },
    {
      id: "essential-cookies",
      heading: "Essential cookies",
      paragraphs: [
        "The NubeRush website and platform may use essential cookies to support authentication, session continuity, and security. These cookies are typically required for the website and authenticated platform to function correctly.",
      ],
    },
    {
      id: "analytics-cookies-if-added-later",
      heading: "Analytics cookies if added later",
      paragraphs: [
        "Analytics cookies are not part of the default website experience today. If analytics cookies are added in the future, this Policy will be updated to describe what is collected, why, and any choices available.",
      ],
    },
    {
      id: "managing-cookies",
      heading: "Managing cookies",
      paragraphs: [
        "You can manage cookies through your browser settings — including blocking, allowing, and clearing cookies. Disabling essential cookies may affect site or platform functionality.",
      ],
    },
    {
      id: "contact",
      heading: "Contact",
      paragraphs: [
        "Questions about cookies can be sent to the NubeRush team at the email address listed below.",
      ],
    },
  ],
};

export const LEGAL_DOCUMENTS_BY_SLUG: Readonly<
  Record<LegalDocumentSlug, LegalDocument>
> = {
  terms: TERMS_DRAFT,
  privacy: PRIVACY_DRAFT,
  "merchant-agreement": MERCHANT_AGREEMENT_DRAFT,
  "acceptable-use": ACCEPTABLE_USE_DRAFT,
  cookies: COOKIES_DRAFT,
};
