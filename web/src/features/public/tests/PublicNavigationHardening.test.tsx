import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";

import { PublicHeader } from "../components/PublicHeader";
import { PublicFooter } from "../components/PublicFooter";
import { HomePage } from "../pages/HomePage";
import { ForStoresPage } from "../pages/ForStoresPage";
import { HowItWorksPage } from "../pages/HowItWorksPage";
import { FeaturesPage } from "../pages/FeaturesPage";
import { ContactPage } from "../pages/ContactPage";
import { RequestDemoPage } from "../pages/RequestDemoPage";
import { SupportPage } from "../pages/SupportPage";
import { LegalHubPage } from "../legal/LegalHubPage";
import { TermsPage } from "../legal/TermsPage";
import { PrivacyPage } from "../legal/PrivacyPage";
import { MerchantAgreementPage } from "../legal/MerchantAgreementPage";
import { AcceptableUsePage } from "../legal/AcceptableUsePage";
import { CookiesPage } from "../legal/CookiesPage";

function renderInRouter(node: ReactNode) {
  return render(<MemoryRouter>{node}</MemoryRouter>);
}

function expectLink(label: RegExp, href: string) {
  const matches = screen.getAllByRole("link", { name: label });
  expect(matches.length).toBeGreaterThan(0);
  expect(matches.some((el) => el.getAttribute("href") === href)).toBe(true);
}

function expectAnyLinkTo(href: string) {
  const matches = screen.getAllByRole("link");
  expect(matches.some((el) => el.getAttribute("href") === href)).toBe(true);
}

// Forbidden destinations any public page/header/footer must avoid.
// Hash anchors (legal TOC) and mailto links are explicitly allowed.
const FORBIDDEN_DESTINATIONS = [
  "/signup",
  "/pricing",
  "/checkout",
  "/driver",
  "/merchant/onboarding",
  "/payments",
  "/app/admin",
  "/app/store",
] as const;

function expectNoForbiddenLinks() {
  const matches = screen.getAllByRole("link");
  for (const link of matches) {
    const href = link.getAttribute("href") ?? "";
    // Allow legal table-of-contents hash anchors and mailto links.
    if (href.startsWith("#") || href.startsWith("mailto:")) continue;
    for (const forbidden of FORBIDDEN_DESTINATIONS) {
      // Exact-match or `/forbidden/...` subpath are both forbidden;
      // `/login` is intentionally allowed in the header/footer.
      expect(href === forbidden || href.startsWith(`${forbidden}/`)).toBe(
        false,
      );
    }
  }
}

// ───────────────────────────────────────────────────────────────────
// Header hardening
// ───────────────────────────────────────────────────────────────────

describe("PublicHeader hardening (F2.21.6)", () => {
  it("brand links to /", () => {
    renderInRouter(<PublicHeader />);
    const brand = screen.getByRole("link", { name: /nuberush home/i });
    expect(brand).toHaveAttribute("href", "/");
  });

  it.each([
    [/^for stores$/i, "/for-stores"],
    [/^how it works$/i, "/how-it-works"],
    [/^features$/i, "/features"],
    [/^contact$/i, "/contact"],
    [/^support$/i, "/support"],
  ])("public nav link %s points to %s", (label, href) => {
    renderInRouter(<PublicHeader />);
    expectLink(label, href);
  });

  it("Sign in links to /login", () => {
    renderInRouter(<PublicHeader />);
    expectLink(/^sign in$/i, "/login");
  });

  it("Apply to sell links to /apply", () => {
    renderInRouter(<PublicHeader />);
    expectLink(/^apply to sell$/i, "/apply");
  });

  it("desktop and mobile navs lead to the same destinations", () => {
    renderInRouter(<PublicHeader />);
    const navs = screen.getAllByRole("navigation", {
      name: /public site navigation/i,
    });
    expect(navs.length).toBeGreaterThanOrEqual(2);

    const expectedDestinations = [
      "/for-stores",
      "/how-it-works",
      "/features",
      "/contact",
      "/support",
    ];

    for (const nav of navs) {
      const hrefs = within(nav)
        .getAllByRole("link")
        .map((el) => el.getAttribute("href") ?? "");
      for (const dest of expectedDestinations) {
        expect(hrefs).toContain(dest);
      }
    }
  });

  it.each([
    "Admin Dashboard",
    "Store Dashboard",
    "Inventory",
    "Orders",
    "Users",
    "Audit",
    "Internal Operations",
    "Pricing",
    "Sign up",
    "Checkout",
    "Driver",
    "Payments",
  ])("does not render forbidden/internal label %s", (label) => {
    renderInRouter(<PublicHeader />);
    expect(screen.queryByText(label)).not.toBeInTheDocument();
  });

  it("does not link to any forbidden destination", () => {
    renderInRouter(<PublicHeader />);
    expectNoForbiddenLinks();
  });
});

// ───────────────────────────────────────────────────────────────────
// Footer hardening
// ───────────────────────────────────────────────────────────────────

describe("PublicFooter hardening (F2.21.6)", () => {
  it.each([
    [/^home$/i, "/"],
    [/^for stores$/i, "/for-stores"],
    [/^how it works$/i, "/how-it-works"],
    [/^features$/i, "/features"],
    [/^contact$/i, "/contact"],
    [/^request demo$/i, "/request-demo"],
    [/^support$/i, "/support"],
  ])("public link %s points to %s", (label, href) => {
    renderInRouter(<PublicFooter />);
    const publicNav = screen.getByRole("navigation", { name: /public links/i });
    const link = within(publicNav).getByRole("link", { name: label });
    expect(link).toHaveAttribute("href", href);
  });

  it.each([
    [/^legal hub$/i, "/legal"],
    [/^terms$/i, "/legal/terms"],
    [/^privacy$/i, "/legal/privacy"],
    [/^merchant agreement$/i, "/legal/merchant-agreement"],
    [/^acceptable use$/i, "/legal/acceptable-use"],
    [/^cookies$/i, "/legal/cookies"],
  ])("legal link %s points to %s", (label, href) => {
    renderInRouter(<PublicFooter />);
    const legalNav = screen.getByRole("navigation", { name: /^legal$/i });
    const link = within(legalNav).getByRole("link", { name: label });
    expect(link).toHaveAttribute("href", href);
  });

  it("Sign in link points to /login", () => {
    renderInRouter(<PublicFooter />);
    const publicNav = screen.getByRole("navigation", { name: /public links/i });
    const link = within(publicNav).getByRole("link", { name: /^sign in$/i });
    expect(link).toHaveAttribute("href", "/login");
  });

  it("exposes the business email as a mailto link", () => {
    renderInRouter(<PublicFooter />);
    const email = screen.getByRole("link", {
      name: /info@nuberush\.com/i,
    });
    expect(email).toHaveAttribute(
      "href",
      "mailto:info@nuberush.com",
    );
  });

  it("renders no fake social/phone/address content", () => {
    renderInRouter(<PublicFooter />);
    const banned = [
      /facebook/i,
      /twitter/i,
      /instagram/i,
      /linkedin/i,
      /tiktok/i,
      /youtube/i,
      /x\.com/i,
      /\(\d{3}\)\s?\d{3}[-\s]?\d{4}/,
      /\d{3}-\d{3}-\d{4}/,
      /call us at/i,
      /\d{1,5}\s+\w+\s+(street|st\.|avenue|ave\.|road|rd\.|boulevard|blvd\.)/i,
    ];
    for (const pattern of banned) {
      expect(screen.queryByText(pattern)).not.toBeInTheDocument();
    }
  });

  it.each([
    "Admin Dashboard",
    "Store Dashboard",
    "Platform Admin",
    "Store Operations",
    "Internal Operations",
    "Pricing",
    "Sign up",
    "Checkout",
    "Driver",
    "Payments",
  ])("does not render forbidden/internal label %s", (label) => {
    renderInRouter(<PublicFooter />);
    expect(screen.queryByText(label)).not.toBeInTheDocument();
  });

  it("does not link to any forbidden destination", () => {
    renderInRouter(<PublicFooter />);
    expectNoForbiddenLinks();
  });
});

// ───────────────────────────────────────────────────────────────────
// Cross-page CTA consistency
// ───────────────────────────────────────────────────────────────────

interface CrossLinkExpectation {
  name: string;
  node: ReactNode;
  routes: ReadonlyArray<string>;
  mailto?: boolean;
}

const CROSS_LINK_PAGES: ReadonlyArray<CrossLinkExpectation> = [
  {
    name: "HomePage",
    node: <HomePage />,
    routes: ["/request-demo", "/how-it-works", "/contact"],
  },
  {
    name: "ForStoresPage",
    node: <ForStoresPage />,
    routes: ["/request-demo", "/how-it-works", "/contact"],
  },
  {
    name: "HowItWorksPage",
    node: <HowItWorksPage />,
    routes: ["/request-demo", "/for-stores"],
  },
  {
    name: "FeaturesPage",
    node: <FeaturesPage />,
    routes: ["/request-demo", "/how-it-works"],
  },
  {
    name: "ContactPage",
    node: <ContactPage />,
    routes: ["/request-demo"],
    mailto: true,
  },
  {
    name: "RequestDemoPage",
    node: <RequestDemoPage />,
    routes: ["/how-it-works"],
    mailto: true,
  },
  {
    name: "SupportPage",
    node: <SupportPage />,
    routes: ["/contact", "/request-demo"],
  },
];

describe.each(CROSS_LINK_PAGES)(
  "$name cross-links (F2.21.6)",
  ({ node, routes, mailto }) => {
    for (const route of routes) {
      it(`links to ${route}`, () => {
        renderInRouter(node);
        expectAnyLinkTo(route);
      });
    }

    if (mailto) {
      it("exposes the business email as a mailto link", () => {
        renderInRouter(node);
        const matches = screen.getAllByRole("link", {
          name: /info@nuberush\.com/i,
        });
        expect(matches.length).toBeGreaterThan(0);
        expect(
          matches.some(
            (el) =>
              el.getAttribute("href") ===
              "mailto:info@nuberush.com",
          ),
        ).toBe(true);
      });
    }

    it("links to neither a forbidden destination", () => {
      renderInRouter(node);
      expectNoForbiddenLinks();
    });
  },
);

it("SupportPage cross-links to either /features or /how-it-works", () => {
  renderInRouter(<SupportPage />);
  const links = screen
    .getAllByRole("link")
    .map((el) => el.getAttribute("href") ?? "");
  expect(
    links.includes("/features") || links.includes("/how-it-works"),
  ).toBe(true);
});

// ───────────────────────────────────────────────────────────────────
// Legal hub + document cross-links
// ───────────────────────────────────────────────────────────────────

describe("LegalHubPage cross-links (F2.21.6)", () => {
  const LEGAL_DOC_HREFS = [
    "/legal/terms",
    "/legal/privacy",
    "/legal/merchant-agreement",
    "/legal/acceptable-use",
    "/legal/cookies",
  ];

  it.each(LEGAL_DOC_HREFS)("links to %s", (href) => {
    renderInRouter(<LegalHubPage />);
    expectAnyLinkTo(href);
  });

  it("exposes the business email as a mailto link", () => {
    renderInRouter(<LegalHubPage />);
    const matches = screen.getAllByRole("link", {
      name: /info@nuberush\.com/i,
    });
    expect(matches.length).toBeGreaterThan(0);
    expect(
      matches.some(
        (el) =>
          el.getAttribute("href") === "mailto:info@nuberush.com",
      ),
    ).toBe(true);
  });

  it("does not link to any forbidden destination", () => {
    renderInRouter(<LegalHubPage />);
    expectNoForbiddenLinks();
  });
});

const LEGAL_DOCS: ReadonlyArray<{ name: string; node: ReactNode }> = [
  { name: "TermsPage", node: <TermsPage /> },
  { name: "PrivacyPage", node: <PrivacyPage /> },
  { name: "MerchantAgreementPage", node: <MerchantAgreementPage /> },
  { name: "AcceptableUsePage", node: <AcceptableUsePage /> },
  { name: "CookiesPage", node: <CookiesPage /> },
];

describe.each(LEGAL_DOCS)("$name cross-links (F2.21.6)", ({ node }) => {
  it("renders back-to-/legal link", () => {
    renderInRouter(node);
    const matches = screen.getAllByRole("link", { name: /back to legal hub/i });
    expect(matches.length).toBeGreaterThan(0);
    expect(matches.some((el) => el.getAttribute("href") === "/legal")).toBe(
      true,
    );
  });

  it("exposes the business email as a mailto link", () => {
    renderInRouter(node);
    const matches = screen.getAllByRole("link", {
      name: /info@nuberush\.com/i,
    });
    expect(matches.length).toBeGreaterThan(0);
    expect(
      matches.some(
        (el) =>
          el.getAttribute("href") === "mailto:info@nuberush.com",
      ),
    ).toBe(true);
  });

  it("does not link to any forbidden destination", () => {
    renderInRouter(node);
    expectNoForbiddenLinks();
  });
});
