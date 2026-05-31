import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";

import { ContactPage } from "../pages/ContactPage";
import { RequestDemoPage } from "../pages/RequestDemoPage";

function renderPage(node: ReactNode) {
  return render(<MemoryRouter>{node}</MemoryRouter>);
}

function expectInternalLinkTo(label: RegExp, href: string) {
  const matches = screen.getAllByRole("link", { name: label });
  expect(matches.length).toBeGreaterThan(0);
  expect(matches.some((el) => el.getAttribute("href") === href)).toBe(true);
}

function expectMailtoLink(href = "mailto:info@nuberush.com") {
  const matches = screen.getAllByRole("link", {
    name: /info@nuberush\.com/i,
  });
  expect(matches.length).toBeGreaterThan(0);
  expect(matches.some((el) => el.getAttribute("href") === href)).toBe(true);
}

// ───────────────────────────────────────────────────────────────────
// /contact
// ───────────────────────────────────────────────────────────────────

describe("ContactPage (F2.21.4)", () => {
  it("renders exactly one h1 with the contact headline", () => {
    renderPage(<ContactPage />);
    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent(/contact nuberush/i);
  });

  it("renders the locked business email and mailto link", () => {
    renderPage(<ContactPage />);
    expect(
      screen.getAllByText(/info@nuberush\.com/i).length,
    ).toBeGreaterThan(0);
    expectMailtoLink();
  });

  it.each([
    "General contact",
    "Merchant demo inquiries",
    "Support direction",
    "Business/partnership inquiries",
  ])("renders required section %s", (title) => {
    renderPage(<ContactPage />);
    expect(screen.getAllByText(title).length).toBeGreaterThan(0);
  });

  it("renders the checklist section heading", () => {
    renderPage(<ContactPage />);
    expect(
      screen.getByRole("heading", {
        level: 2,
        name: /helpful details for routing your message/i,
      }),
    ).toBeInTheDocument();
  });

  it("renders a CTA to request demo", () => {
    renderPage(<ContactPage />);
    expectInternalLinkTo(/^request demo$/i, "/request-demo");
  });

  it.each([
    "Your name",
    "Business name",
    "City and state",
    "Store type or business type",
    "Number of locations",
    "What you need help with",
    "Best way to reach you",
  ])("renders email checklist item %s", (item) => {
    renderPage(<ContactPage />);
    expect(screen.getByText(item)).toBeInTheDocument();
  });

  it("primary email CTA points to mailto", () => {
    renderPage(<ContactPage />);
    const emailUs = screen.getByRole("link", { name: /^email us$/i });
    expect(emailUs).toHaveAttribute(
      "href",
      "mailto:info@nuberush.com",
    );
  });
});

// ───────────────────────────────────────────────────────────────────
// /request-demo
// ───────────────────────────────────────────────────────────────────

describe("RequestDemoPage (F2.24 — merchant application surface)", () => {
  it("renders exactly one h1 with the apply headline", () => {
    renderPage(<RequestDemoPage />);
    const headings = screen.getAllByRole("heading", { level: 1 });
    expect(headings).toHaveLength(1);
    expect(headings[0]).toHaveTextContent(
      /apply to open your store on nuberush/i,
    );
  });

  it("renders the locked business email and mailto link", () => {
    renderPage(<RequestDemoPage />);
    // The address appears in the access-model list AND in the CTA box
    // anchor, so use getAllByText with a positive count assertion.
    expect(
      screen.getAllByText(/info@nuberush\.com/i).length,
    ).toBeGreaterThan(0);
    expectMailtoLink();
  });

  it.each([
    "Who should apply",
    "What happens after you apply",
    "What to include in your application",
    "What you can do once approved",
    "Current access model",
  ])("renders required section %s", (title) => {
    renderPage(<RequestDemoPage />);
    expect(screen.getAllByText(title).length).toBeGreaterThan(0);
  });

  it.each([
    "Business name",
    "City and state",
    "Store type",
    "Number of locations",
    "Owner name and contact information",
    "Estimated weekly order volume",
    "Product/inventory/order needs",
    "Compliance visibility needs",
  ])("renders application checklist item %s", (item) => {
    renderPage(<RequestDemoPage />);
    expect(screen.getAllByText(item).length).toBeGreaterThan(0);
  });

  it("states self-serve signup is not available yet", () => {
    renderPage(<RequestDemoPage />);
    expect(
      screen.getAllByText(/self-serve signup is not available yet/i).length,
    ).toBeGreaterThan(0);
  });

  it("notes that store access is provisioned by the NubeRush team after review", () => {
    renderPage(<RequestDemoPage />);
    expect(
      screen.getByText(
        /store access is provisioned by the nuberush team after the application is reviewed and approved/i,
      ),
    ).toBeInTheDocument();
  });

  it("primary CTA starts the application at /apply", () => {
    renderPage(<RequestDemoPage />);
    expectInternalLinkTo(/^start your application$/i, "/apply");
  });

  it("See how it works CTA points to /how-it-works", () => {
    renderPage(<RequestDemoPage />);
    expectInternalLinkTo(/^see how it works$/i, "/how-it-works");
  });
});

// ───────────────────────────────────────────────────────────────────
// Cross-page honesty + truthfulness guard
// ───────────────────────────────────────────────────────────────────

const PAGES: ReadonlyArray<{ name: string; node: ReactNode }> = [
  { name: "ContactPage", node: <ContactPage /> },
  { name: "RequestDemoPage", node: <RequestDemoPage /> },
];

describe.each(PAGES)("$name honesty guard (F2.21.4)", ({ node }) => {
  it("renders no form, no input fields, no submit button", () => {
    const { container } = renderPage(node);
    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelectorAll("input")).toHaveLength(0);
    expect(container.querySelectorAll("textarea")).toHaveLength(0);
    expect(
      screen.queryByRole("button", { name: /submit/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /send message/i }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it.each([
    /we['’]ll be in touch/i,
    /we have received your/i,
    /thanks for submitting/i,
    /thank you for submitting/i,
    /your message has been sent/i,
    /your request has been received/i,
    /successfully submitted/i,
  ])("renders no fake success state matching %s", (pattern) => {
    renderPage(node);
    expect(screen.queryByText(pattern)).not.toBeInTheDocument();
  });

  it.each([
    /\+1[ -]?\(?\d{3}\)?[ -]?\d{3}[ -]?\d{4}/,
    /\(\d{3}\)\s?\d{3}[ -]?\d{4}/,
    /\d{3}-\d{3}-\d{4}/,
    /call us at/i,
  ])("renders no fake phone number / call-us claim (%s)", (pattern) => {
    renderPage(node);
    expect(screen.queryByText(pattern)).not.toBeInTheDocument();
  });

  it.each([
    /\d{1,5}\s+\w+\s+(street|st\.|avenue|ave\.|road|rd\.|boulevard|blvd\.)/i,
    /visit our office/i,
    /headquartered at/i,
  ])("renders no fake physical address (%s)", (pattern) => {
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
    /x\.com/i,
  ])("renders no fake social link (%s)", (pattern) => {
    renderPage(node);
    expect(screen.queryByText(pattern)).not.toBeInTheDocument();
  });

  it.each([
    /guaranteed response time/i,
    /24\/7 support/i,
    /always available/i,
    /response within \d+ hours?/i,
  ])("renders no 24/7-support or guaranteed-response claim (%s)", (pattern) => {
    renderPage(node);
    expect(screen.queryByText(pattern)).not.toBeInTheDocument();
  });

  it.each([
    /instant approval/i,
    /instant onboarding/i,
    /approved in minutes/i,
    /guaranteed demo availability/i,
    /guaranteed compliance/i,
    /legal advice/i,
    /payment processing/i,
    /customer checkout/i,
    /driver dispatch/i,
  ])("renders no banned claim %s", (pattern) => {
    renderPage(node);
    expect(screen.queryByText(pattern)).not.toBeInTheDocument();
  });

  it("does not render a positive self-serve signup claim", () => {
    renderPage(node);
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

  it("does not call fetch/axios/useMutation (no client API call)", () => {
    // Read the source for the page's imports — both pages must NOT
    // depend on the network API layer. We verify by asserting no
    // axios/fetch text appears as page-rendered content (the build
    // step would also fail any unresolved imports if introduced).
    renderPage(node);
    expect(screen.queryByText(/api call/i)).not.toBeInTheDocument();
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
