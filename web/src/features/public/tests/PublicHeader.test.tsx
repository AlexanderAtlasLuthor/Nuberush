import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { PublicHeader } from "../components/PublicHeader";

function renderHeader() {
  return render(
    <MemoryRouter>
      <PublicHeader />
    </MemoryRouter>,
  );
}

// Header links can render twice (desktop + mobile nav). We assert that
// each expected destination is reachable by at least one link with the
// expected label, and that no admin/store internal nav labels leak
// onto the public surface.

function expectLinkTo(label: RegExp, href: string) {
  const matches = screen.getAllByRole("link", { name: label });
  expect(matches.length).toBeGreaterThan(0);
  expect(matches.some((el) => el.getAttribute("href") === href)).toBe(true);
}

describe("PublicHeader", () => {
  it("renders the NubeRush brand link", () => {
    renderHeader();
    const brand = screen.getByRole("link", { name: /nuberush home/i });
    expect(brand).toHaveAttribute("href", "/");
    expect(within(brand).getByText("NubeRush")).toBeInTheDocument();
  });

  it("links public nav items to their public routes", () => {
    renderHeader();
    expectLinkTo(/^for stores$/i, "/for-stores");
    expectLinkTo(/^how it works$/i, "/how-it-works");
    expectLinkTo(/^features$/i, "/features");
    expectLinkTo(/^contact$/i, "/contact");
    expectLinkTo(/^support$/i, "/support");
  });

  it("links Sign in to /login", () => {
    renderHeader();
    expectLinkTo(/^sign in$/i, "/login");
  });

  it("links the primary Apply to sell action to /apply", () => {
    renderHeader();
    expectLinkTo(/^apply to sell$/i, "/apply");
  });

  it("no longer renders a Request demo button in the header", () => {
    renderHeader();
    expect(
      screen.queryByRole("link", { name: /^request demo$/i }),
    ).not.toBeInTheDocument();
  });

  it("exposes the public site navigation with an aria-label", () => {
    renderHeader();
    // Desktop + mobile navs each carry a labelled <nav>; at least one
    // must match.
    expect(
      screen.getAllByRole("navigation", { name: /public site navigation/i })
        .length,
    ).toBeGreaterThan(0);
  });

  it("does not render admin/store internal nav labels", () => {
    renderHeader();
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
