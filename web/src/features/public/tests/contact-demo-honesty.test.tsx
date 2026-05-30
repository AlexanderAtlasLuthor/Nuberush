import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ContactPage } from "../pages/ContactPage";
import { RequestDemoPage } from "../pages/RequestDemoPage";

function renderPage(node: React.ReactNode) {
  return render(<MemoryRouter>{node}</MemoryRouter>);
}

const FAKE_SUCCESS_PATTERNS = [
  /we['’]ll be in touch/i,
  /we have received your/i,
  /thanks for submitting/i,
  /thank you for submitting/i,
  /your message has been sent/i,
  /your request has been received/i,
  /successfully submitted/i,
];

describe.each([
  { name: "ContactPage", node: <ContactPage /> },
  { name: "RequestDemoPage", node: <RequestDemoPage /> },
])("$name honest email CTA (F2.21.1)", ({ node }) => {
  it("exposes the business email as a mailto link", () => {
    renderPage(node);
    const email = screen.getByRole("link", {
      name: /info@nuberush\.com/i,
    });
    expect(email).toHaveAttribute(
      "href",
      "mailto:info@nuberush.com",
    );
  });

  it("does not render a form", () => {
    const { container } = renderPage(node);
    expect(container.querySelector("form")).toBeNull();
    // No submit-style buttons either — public site never POSTs in F2.21.
    expect(
      screen.queryByRole("button", { name: /submit/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /send message/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("textbox"),
    ).not.toBeInTheDocument();
  });

  it("does not render a fake success state", () => {
    renderPage(node);
    for (const pattern of FAKE_SUCCESS_PATTERNS) {
      expect(screen.queryByText(pattern)).not.toBeInTheDocument();
    }
  });
});
