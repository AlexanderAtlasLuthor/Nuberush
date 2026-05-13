import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { PublicFooter } from "../components/PublicFooter";

function renderFooter() {
  return render(
    <MemoryRouter>
      <PublicFooter />
    </MemoryRouter>,
  );
}

describe("PublicFooter", () => {
  it("renders the brand summary", () => {
    renderFooter();
    expect(
      screen.getByText(/operating platform for regulated local commerce/i),
    ).toBeInTheDocument();
  });

  it("renders the public link cluster", () => {
    renderFooter();
    const publicNav = screen.getByRole("navigation", { name: /public links/i });
    const linksOf = (label: RegExp) =>
      within(publicNav).getByRole("link", { name: label });

    expect(linksOf(/^for stores$/i)).toHaveAttribute("href", "/for-stores");
    expect(linksOf(/^how it works$/i)).toHaveAttribute("href", "/how-it-works");
    expect(linksOf(/^features$/i)).toHaveAttribute("href", "/features");
    expect(linksOf(/^contact$/i)).toHaveAttribute("href", "/contact");
    expect(linksOf(/^request demo$/i)).toHaveAttribute("href", "/request-demo");
    expect(linksOf(/^support$/i)).toHaveAttribute("href", "/support");
    expect(linksOf(/^sign in$/i)).toHaveAttribute("href", "/login");
  });

  it("renders the full legal link cluster", () => {
    renderFooter();
    const legalNav = screen.getByRole("navigation", { name: /^legal$/i });
    const linksOf = (label: RegExp) =>
      within(legalNav).getByRole("link", { name: label });

    expect(linksOf(/^legal hub$/i)).toHaveAttribute("href", "/legal");
    expect(linksOf(/^terms$/i)).toHaveAttribute("href", "/legal/terms");
    expect(linksOf(/^privacy$/i)).toHaveAttribute("href", "/legal/privacy");
    expect(linksOf(/^merchant agreement$/i)).toHaveAttribute(
      "href",
      "/legal/merchant-agreement",
    );
    expect(linksOf(/^acceptable use$/i)).toHaveAttribute(
      "href",
      "/legal/acceptable-use",
    );
    expect(linksOf(/^cookies$/i)).toHaveAttribute("href", "/legal/cookies");
  });

  it("exposes the business contact email", () => {
    renderFooter();
    const email = screen.getByRole("link", {
      name: /team@fuenmayorindustries\.com/i,
    });
    expect(email).toHaveAttribute(
      "href",
      "mailto:team@fuenmayorindustries.com",
    );
  });

  it("does not render fake social links", () => {
    renderFooter();
    const allLinks = screen.getAllByRole("link");
    const fakeSocialPatterns = [
      /twitter/i,
      /x\.com/i,
      /facebook/i,
      /instagram/i,
      /linkedin/i,
      /tiktok/i,
      /youtube/i,
    ];
    for (const link of allLinks) {
      for (const pattern of fakeSocialPatterns) {
        expect(link.textContent ?? "").not.toMatch(pattern);
        expect(link.getAttribute("href") ?? "").not.toMatch(pattern);
      }
    }
  });

  it("does not render admin/store internal nav labels", () => {
    renderFooter();
    const leaked = [
      "Admin Dashboard",
      "Store Dashboard",
      "Inventory",
      "Orders",
      "Audit",
      "Users",
      "Compliance",
      "Operations",
      "Platform Admin",
      "Store Operations",
    ];
    for (const label of leaked) {
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    }
  });
});
