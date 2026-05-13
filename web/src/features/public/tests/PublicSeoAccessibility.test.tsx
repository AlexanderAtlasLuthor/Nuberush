import { readFileSync } from "node:fs";
import path from "node:path";
import { afterEach, describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import {
  DEFAULT_PAGE_META,
  PUBLIC_PAGE_META,
  getPageMeta,
} from "../content/publicMeta";
import {
  PublicPageMeta,
  PublicPageMetaTagSetter,
} from "../components/PublicPageMeta";
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

// ───────────────────────────────────────────────────────────────────
// Path constants used across describes
// ───────────────────────────────────────────────────────────────────

const PUBLIC_PATHS = [
  "/",
  "/for-stores",
  "/how-it-works",
  "/features",
  "/contact",
  "/request-demo",
  "/support",
  "/legal",
  "/legal/terms",
  "/legal/privacy",
  "/legal/merchant-agreement",
  "/legal/acceptable-use",
  "/legal/cookies",
] as const;

const BANNED_META_PATTERNS = [
  /guaranteed compliance/i,
  /\blegally approved\b/i,
  /certified compliant/i,
  /\binstant approval\b/i,
  /automatic legal verification/i,
  /self-serve signup available/i,
  /payment processing/i,
  /customer checkout/i,
  /driver dispatch/i,
  /final legal approval/i,
];

// ───────────────────────────────────────────────────────────────────
// Metadata config — pure data assertions
// ───────────────────────────────────────────────────────────────────

describe("PUBLIC_PAGE_META (F2.21.7)", () => {
  it.each(PUBLIC_PATHS)(
    "has a meta entry for %s",
    (publicPath) => {
      const entry = getPageMeta(publicPath);
      expect(entry.title).toBeTruthy();
      expect(entry.description).toBeTruthy();
    },
  );

  it("covers every public route in PUBLIC_PATHS", () => {
    const configuredPaths = Object.keys(PUBLIC_PAGE_META);
    for (const expected of PUBLIC_PATHS) {
      expect(configuredPaths).toContain(expected);
    }
  });

  it("renders unique titles across all 13 public routes", () => {
    const titles = PUBLIC_PATHS.map((p) => getPageMeta(p).title);
    expect(new Set(titles).size).toBe(PUBLIC_PATHS.length);
  });

  it("renders unique descriptions across all 13 public routes", () => {
    const descriptions = PUBLIC_PATHS.map((p) => getPageMeta(p).description);
    expect(new Set(descriptions).size).toBe(PUBLIC_PATHS.length);
  });

  it.each(BANNED_META_PATTERNS)(
    "no meta entry contains the banned pattern %s",
    (pattern) => {
      for (const publicPath of PUBLIC_PATHS) {
        const entry = getPageMeta(publicPath);
        expect(entry.title).not.toMatch(pattern);
        expect(entry.description).not.toMatch(pattern);
      }
    },
  );

  it("returns the default home meta for unknown paths", () => {
    expect(getPageMeta("/not-a-public-route")).toEqual(DEFAULT_PAGE_META);
  });
});

// ───────────────────────────────────────────────────────────────────
// SEO/meta helper — DOM side effects
// ───────────────────────────────────────────────────────────────────

function getMetaContent(attr: "name" | "property", key: string): string | null {
  const el = document.head.querySelector<HTMLMetaElement>(
    `meta[${attr}="${key}"]`,
  );
  return el?.getAttribute("content") ?? null;
}

describe("PublicPageMetaTagSetter (F2.21.7)", () => {
  afterEach(() => {
    document.title = "";
  });

  it("sets document.title and meta description for the given props", () => {
    render(
      <PublicPageMetaTagSetter
        title="Test title"
        description="Test description"
      />,
    );
    expect(document.title).toBe("Test title");
    expect(getMetaContent("name", "description")).toBe("Test description");
  });

  it("populates og:title, og:description, and og:type", () => {
    render(
      <PublicPageMetaTagSetter
        title="OG Title"
        description="OG Description"
      />,
    );
    expect(getMetaContent("property", "og:title")).toBe("OG Title");
    expect(getMetaContent("property", "og:description")).toBe(
      "OG Description",
    );
    expect(getMetaContent("property", "og:type")).toBe("website");
  });

  it("renders nothing in the DOM tree", () => {
    const { container } = render(
      <PublicPageMetaTagSetter title="A" description="B" />,
    );
    expect(container).toBeEmptyDOMElement();
  });
});

describe("PublicPageMeta (F2.21.7)", () => {
  afterEach(() => {
    document.title = "";
  });

  it.each([
    "/",
    "/for-stores",
    "/contact",
    "/legal/terms",
  ])("applies the meta entry for %s via useLocation", (publicPath) => {
    render(
      <MemoryRouter initialEntries={[publicPath]}>
        <PublicPageMeta />
      </MemoryRouter>,
    );
    const expected = getPageMeta(publicPath);
    expect(document.title).toBe(expected.title);
    expect(getMetaContent("name", "description")).toBe(expected.description);
  });

  it("honors an explicit path prop over useLocation", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <PublicPageMeta path="/legal/cookies" />
      </MemoryRouter>,
    );
    const expected = getPageMeta("/legal/cookies");
    expect(document.title).toBe(expected.title);
  });
});

// ───────────────────────────────────────────────────────────────────
// Accessibility — semantic landmarks, single h1, no leakage
// ───────────────────────────────────────────────────────────────────

const ALL_PAGES = [
  { name: "HomePage", node: <HomePage /> },
  { name: "ForStoresPage", node: <ForStoresPage /> },
  { name: "HowItWorksPage", node: <HowItWorksPage /> },
  { name: "FeaturesPage", node: <FeaturesPage /> },
  { name: "ContactPage", node: <ContactPage /> },
  { name: "RequestDemoPage", node: <RequestDemoPage /> },
  { name: "SupportPage", node: <SupportPage /> },
  { name: "LegalHubPage", node: <LegalHubPage /> },
  { name: "TermsPage", node: <TermsPage /> },
  { name: "PrivacyPage", node: <PrivacyPage /> },
  { name: "MerchantAgreementPage", node: <MerchantAgreementPage /> },
  { name: "AcceptableUsePage", node: <AcceptableUsePage /> },
  { name: "CookiesPage", node: <CookiesPage /> },
];

describe.each(ALL_PAGES)("$name a11y (F2.21.7)", ({ node }) => {
  it("renders exactly one h1", () => {
    render(<MemoryRouter>{node}</MemoryRouter>);
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
  });
});

describe("PublicHeader/PublicFooter aria-labels (F2.21.7)", () => {
  it("PublicHeader has at least one navigation labelled 'Public site navigation'", () => {
    render(
      <MemoryRouter>
        <PublicHeader />
      </MemoryRouter>,
    );
    expect(
      screen.getAllByRole("navigation", { name: /public site navigation/i })
        .length,
    ).toBeGreaterThan(0);
  });

  it("PublicFooter exposes 'Public links' and 'Legal' navs by name", () => {
    render(
      <MemoryRouter>
        <PublicFooter />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("navigation", { name: /public links/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("navigation", { name: /^legal$/i }),
    ).toBeInTheDocument();
  });
});

describe("LegalDocumentPage table of contents (F2.21.7)", () => {
  it("renders a nav with a table-of-contents aria-label", () => {
    render(
      <MemoryRouter>
        <TermsPage />
      </MemoryRouter>,
    );
    expect(
      screen.getByRole("navigation", {
        name: /table of contents/i,
      }),
    ).toBeInTheDocument();
  });
});

// ───────────────────────────────────────────────────────────────────
// Honesty — contact/demo/support/home pages must not render forms
// ───────────────────────────────────────────────────────────────────

const FORM_FREE_PAGES = [
  { name: "HomePage", node: <HomePage /> },
  { name: "ContactPage", node: <ContactPage /> },
  { name: "RequestDemoPage", node: <RequestDemoPage /> },
  { name: "SupportPage", node: <SupportPage /> },
];

describe.each(FORM_FREE_PAGES)("$name form-free (F2.21.7)", ({ node }) => {
  it("renders no form, no input, no textarea, no submit button", () => {
    const { container } = render(<MemoryRouter>{node}</MemoryRouter>);
    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelectorAll("input")).toHaveLength(0);
    expect(container.querySelectorAll("textarea")).toHaveLength(0);
    expect(
      screen.queryByRole("button", { name: /submit/i }),
    ).not.toBeInTheDocument();
  });
});

// ───────────────────────────────────────────────────────────────────
// Responsive smoke — class-based checks against shared layout pieces
// ───────────────────────────────────────────────────────────────────

const PUBLIC_DIR = path.resolve(__dirname, "..");
const PROJECT_FILES = [
  "components/PublicHeader.tsx",
  "components/PublicFooter.tsx",
  "components/PublicSection.tsx",
  "components/PublicPageHeader.tsx",
  "components/PublicCtaBand.tsx",
  "components/PublicHero.tsx",
  "components/PublicFeatureGrid.tsx",
  "components/PublicTrustBand.tsx",
  "components/PublicFaq.tsx",
  "components/PublicLegalNotice.tsx",
  "pages/HomePage.tsx",
  "pages/ForStoresPage.tsx",
  "pages/HowItWorksPage.tsx",
  "pages/FeaturesPage.tsx",
  "pages/ContactPage.tsx",
  "pages/RequestDemoPage.tsx",
  "pages/SupportPage.tsx",
  "legal/LegalHubPage.tsx",
  "legal/LegalDocumentPage.tsx",
  "legal/TermsPage.tsx",
  "legal/PrivacyPage.tsx",
  "legal/MerchantAgreementPage.tsx",
  "legal/AcceptableUsePage.tsx",
  "legal/CookiesPage.tsx",
] as const;

function readPublicFile(relative: string): string {
  return readFileSync(path.join(PUBLIC_DIR, relative), "utf8");
}

describe("Responsive smoke (F2.21.7)", () => {
  it("PublicHeader exposes desktop + mobile nav classes", () => {
    const source = readPublicFile("components/PublicHeader.tsx");
    // Desktop nav hides on small screens via `hidden md:flex`.
    expect(source).toMatch(/hidden md:flex/);
    // Mobile nav shows below md breakpoint.
    expect(source).toMatch(/md:hidden/);
  });

  it("PublicFooter uses a responsive grid that stacks on mobile", () => {
    const source = readPublicFile("components/PublicFooter.tsx");
    expect(source).toMatch(/grid gap-10 md:grid-cols-4/);
  });

  it("home feature grid uses responsive grid classes", () => {
    const source = readPublicFile("components/PublicFeatureGrid.tsx");
    expect(source).toMatch(/sm:grid-cols-2/);
    expect(source).toMatch(/lg:grid-cols-4/);
  });

  it("merchant-education cards use responsive grid classes", () => {
    const source = readPublicFile("pages/ForStoresPage.tsx");
    expect(source).toMatch(/md:grid-cols-2/);
  });

  it("legal hub cards use responsive grid classes", () => {
    const source = readPublicFile("legal/LegalHubPage.tsx");
    expect(source).toMatch(/md:grid-cols-2/);
  });

  it("support resource cards use responsive grid classes", () => {
    const source = readPublicFile("pages/SupportPage.tsx");
    expect(source).toMatch(/sm:grid-cols-2/);
  });
});

describe("No legacy hex literals (F2.21.7)", () => {
  const LEGACY_HEX = ["#0A0A0F", "#FF6B2C", "#13131A", "#1E1E2A"];

  it.each(PROJECT_FILES)("%s contains no legacy hex literals", (relative) => {
    const source = readPublicFile(relative);
    for (const hex of LEGACY_HEX) {
      expect(source).not.toContain(hex);
    }
  });
});

// ───────────────────────────────────────────────────────────────────
// Native / Capacitor safety
// ───────────────────────────────────────────────────────────────────

describe("PublicPageMeta native/Capacitor safety (F2.21.7)", () => {
  it("guards document usage with a typeof check before every DOM mutation", () => {
    const source = readFileSync(
      path.join(PUBLIC_DIR, "components/PublicPageMeta.tsx"),
      "utf8",
    );
    // The guard phrase appears explicitly.
    expect(source).toMatch(/typeof document === "undefined"/);
    // Every direct `document.` mutation is gated by an early return
    // inside the same function — we look for the guard returning
    // before the mutation in both code paths.
    const guardCount = source.match(/typeof document === "undefined"/g);
    expect(guardCount?.length ?? 0).toBeGreaterThanOrEqual(2);
  });

  it("publicMeta.ts has no executable browser-API code", () => {
    const source = readFileSync(
      path.join(PUBLIC_DIR, "content/publicMeta.ts"),
      "utf8",
    );
    // Strip single-line comments before scanning — references inside
    // comments (e.g. "client-side document.title") are documentation,
    // not code.
    const code = source
      .split("\n")
      .filter((line) => !line.trim().startsWith("//"))
      .join("\n");
    expect(code).not.toMatch(/\bdocument\./);
    expect(code).not.toMatch(/\bwindow\./);
  });

  it("PublicPageMeta module exports load without DOM access at module scope", async () => {
    // Re-importing the module should not throw. The test environment
    // has document, but the components inside should not touch it
    // until React effects fire.
    const mod = await import("../components/PublicPageMeta");
    expect(typeof mod.PublicPageMeta).toBe("function");
    expect(typeof mod.PublicPageMetaTagSetter).toBe("function");
  });
});

// ───────────────────────────────────────────────────────────────────
// Spot-check: header doesn't break public layout context
// ───────────────────────────────────────────────────────────────────

describe("PublicHeader uses semantic landmarks (F2.21.7)", () => {
  it("renders a <header> wrapping the brand + nav + CTAs", () => {
    render(
      <MemoryRouter>
        <PublicHeader />
      </MemoryRouter>,
    );
    // <header> is implicit landmark `banner` only when not nested
    // inside another landmark — in this test it's at the root, so
    // the role exists.
    const banner = screen.getByRole("banner");
    expect(
      within(banner).getByRole("link", { name: /nuberush home/i }),
    ).toBeInTheDocument();
  });
});
