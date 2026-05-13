import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";

import { ForStoresPage } from "../pages/ForStoresPage";
import { HowItWorksPage } from "../pages/HowItWorksPage";
import { FeaturesPage } from "../pages/FeaturesPage";

function renderPage(node: ReactNode) {
  return render(<MemoryRouter>{node}</MemoryRouter>);
}

function expectLinkTo(label: RegExp, href: string) {
  const matches = screen.getAllByRole("link", { name: label });
  expect(matches.length).toBeGreaterThan(0);
  expect(matches.some((el) => el.getAttribute("href") === href)).toBe(true);
}

// ───────────────────────────────────────────────────────────────────
// /for-stores
// ───────────────────────────────────────────────────────────────────

describe("ForStoresPage (F2.21.3)", () => {
  it("renders exactly one h1 with the merchant-specific headline", () => {
    renderPage(<ForStoresPage />);
    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent(
      /operational clarity before chaos starts/i,
    );
  });

  it.each([
    "Why stores use NubeRush",
    "Product operations",
    "Inventory visibility",
    "Order oversight",
    "Compliance-aware workflows",
    "Admin/platform support",
    "Audit / traceability",
  ])("renders required section %s", (title) => {
    renderPage(<ForStoresPage />);
    expect(screen.getAllByText(title).length).toBeGreaterThan(0);
  });

  it("primary CTA points to /request-demo", () => {
    renderPage(<ForStoresPage />);
    expectLinkTo(/^request demo$/i, "/request-demo");
  });

  it("secondary CTA points to /how-it-works", () => {
    renderPage(<ForStoresPage />);
    expectLinkTo(/^see how it works$/i, "/how-it-works");
  });

  it("CTA band offers a contact link", () => {
    renderPage(<ForStoresPage />);
    expectLinkTo(/^contact us$/i, "/contact");
  });
});

// ───────────────────────────────────────────────────────────────────
// /how-it-works
// ───────────────────────────────────────────────────────────────────

describe("HowItWorksPage (F2.21.3)", () => {
  it("renders exactly one h1 with the process headline", () => {
    renderPage(<HowItWorksPage />);
    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent(
      /from request to operating on the platform/i,
    );
  });

  it.each([
    "Request a demo",
    "Confirm store fit and operating needs",
    "Set up store workspace",
    "Organize product catalog",
    "Connect inventory visibility",
    "Track order operations",
    "Monitor compliance visibility",
    "Use admin oversight and audit history",
  ])("renders required step %s", (title) => {
    renderPage(<HowItWorksPage />);
    expect(screen.getAllByText(title).length).toBeGreaterThan(0);
  });

  it("states that self-serve signup is not available yet", () => {
    renderPage(<HowItWorksPage />);
    expect(
      screen.getAllByText(/self-serve signup is not available yet/i).length,
    ).toBeGreaterThan(0);
  });

  it("keeps legal/compliance responsibility with the merchant", () => {
    renderPage(<HowItWorksPage />);
    expect(
      screen.getAllByText(
        /merchants remain responsible for their own legal and compliance obligations/i,
      ).length,
    ).toBeGreaterThan(0);
  });

  it("primary CTA points to /request-demo", () => {
    renderPage(<HowItWorksPage />);
    expectLinkTo(/^request demo$/i, "/request-demo");
  });

  it("For stores link points to /for-stores", () => {
    renderPage(<HowItWorksPage />);
    expectLinkTo(/^for stores$/i, "/for-stores");
  });

  it("does not promise instant approval or automatic onboarding", () => {
    renderPage(<HowItWorksPage />);
    expect(screen.queryByText(/instant approval/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/approved in minutes/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/automatic onboarding/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/sign up in minutes/i),
    ).not.toBeInTheDocument();
  });
});

// ───────────────────────────────────────────────────────────────────
// /features
// ───────────────────────────────────────────────────────────────────

describe("FeaturesPage (F2.21.3)", () => {
  it("renders exactly one h1 with the capabilities headline", () => {
    renderPage(<FeaturesPage />);
    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent(
      /capabilities for stores that need operational visibility/i,
    );
  });

  it.each([
    "Store operations",
    "Product & inventory",
    "Orders",
    "Compliance visibility",
    "Admin oversight",
    "Audit & visibility",
  ])("renders required feature group %s", (title) => {
    renderPage(<FeaturesPage />);
    expect(screen.getAllByText(title).length).toBeGreaterThan(0);
  });

  it.each([
    "Store workspace",
    "Product oversight",
    "Inventory visibility",
    "Order operations",
    "Compliance visibility",
    "Audit trail",
    "Admin console",
    "Operations alerts",
  ])("renders required capability %s", (title) => {
    renderPage(<FeaturesPage />);
    expect(screen.getAllByText(title).length).toBeGreaterThan(0);
  });

  it("primary CTA points to /request-demo", () => {
    renderPage(<FeaturesPage />);
    expectLinkTo(/^request demo$/i, "/request-demo");
  });

  it("secondary CTA points to /how-it-works", () => {
    renderPage(<FeaturesPage />);
    expectLinkTo(/^see how it works$/i, "/how-it-works");
  });
});

// ───────────────────────────────────────────────────────────────────
// Cross-page truthfulness guard
// ───────────────────────────────────────────────────────────────────

const PAGES: ReadonlyArray<{ name: string; node: ReactNode }> = [
  { name: "ForStoresPage", node: <ForStoresPage /> },
  { name: "HowItWorksPage", node: <HowItWorksPage /> },
  { name: "FeaturesPage", node: <FeaturesPage /> },
];

describe.each(PAGES)("$name truthfulness guard (F2.21.3)", ({ node }) => {
  it("renders no form, no submit button, no textbox", () => {
    const { container } = renderPage(node);
    expect(container.querySelector("form")).toBeNull();
    expect(
      screen.queryByRole("button", { name: /submit/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it.each([
    /guaranteed compliance/i,
    /legally approved/i,
    /certified compliant/i,
    /regulator approved/i,
    /approved by government/i,
    /guaranteed delivery/i,
    /instant approval/i,
    /automatic legal verification/i,
    /approved in minutes/i,
  ])("never claims %s", (banned) => {
    renderPage(node);
    expect(screen.queryByText(banned)).not.toBeInTheDocument();
  });

  it.each([
    /trusted by [0-9]/i,
    /10,000\+? stores/i,
    /\$[0-9]+ ?(?:m|b)illion/i,
    /99\.[0-9]+%/i,
    /featured in/i,
    /as seen on/i,
    /customer logos/i,
  ])("renders no fake stats or testimonial markers (%s)", (pattern) => {
    renderPage(node);
    expect(screen.queryByText(pattern)).not.toBeInTheDocument();
  });

  it.each([
    /facebook/i,
    /twitter/i,
    /instagram/i,
    /linkedin/i,
    /tiktok/i,
    /youtube/i,
    /partner logos/i,
  ])("renders no fake social link / logo (%s)", (pattern) => {
    renderPage(node);
    expect(screen.queryByText(pattern)).not.toBeInTheDocument();
  });

  it("does not promise checkout, driver dispatch, or payment processing", () => {
    renderPage(node);
    expect(screen.queryByText(/customer checkout/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/driver dispatch/i)).not.toBeInTheDocument();
    expect(
      screen.queryByText(/payment processing/i),
    ).not.toBeInTheDocument();
  });

  it("does not promise self-serve signup as available", () => {
    renderPage(node);
    // Permitted: the explicit disclaimer phrase
    // "self-serve signup is not available yet". Banned: any positive
    // self-serve signup claim such as "sign up online", "create your
    // account in minutes", or "self-serve onboarding available".
    expect(
      screen.queryByText(/self-serve onboarding available/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/sign up online today/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/create your account in minutes/i),
    ).not.toBeInTheDocument();
  });

  it("does not leak admin/store internal nav labels", () => {
    renderPage(node);
    const leaked = [
      "Admin Dashboard",
      "Store Dashboard",
      "Platform Admin",
      "Store Operations",
      "Internal Operations",
    ];
    for (const label of leaked) {
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    }
  });
});
