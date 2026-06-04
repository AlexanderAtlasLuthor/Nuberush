// F2.25.6: tests for the static store-onboarding landing page.
//
// The page is static (no data fetching, no auth/store hooks), so it renders
// with just a MemoryRouter (needed for <Link>). No QueryClient or mocks.

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import StoreOnboardingPage from "../StoreOnboardingPage";

function renderPage() {
  return render(
    <MemoryRouter>
      <StoreOnboardingPage />
    </MemoryRouter>,
  );
}

describe("StoreOnboardingPage", () => {
  it("renders the getting-started heading and intro", () => {
    renderPage();
    expect(
      screen.getByRole("heading", { name: /getting started with your store/i }),
    ).toBeInTheDocument();
  });

  it("renders all five checklist items", () => {
    renderPage();
    expect(screen.getByText("Complete store profile")).toBeInTheDocument();
    expect(screen.getByText("Add first products")).toBeInTheDocument();
    expect(screen.getByText("Set inventory thresholds")).toBeInTheDocument();
    expect(screen.getByText("Review orders dashboard")).toBeInTheDocument();
    expect(screen.getByText("Contact NubeRush support")).toBeInTheDocument();
  });

  it("links each item to an existing route", () => {
    renderPage();
    const expected: Array<[RegExp, string]> = [
      [/complete store profile/i, "/app/store/settings"],
      [/add first products/i, "/app/store/products"],
      [/set inventory thresholds/i, "/app/store/inventory"],
      [/review orders dashboard/i, "/app/store/orders"],
      [/contact nuberush support/i, "/support"],
    ];
    for (const [name, href] of expected) {
      expect(screen.getByRole("link", { name })).toHaveAttribute("href", href);
    }
  });

  it("renders no auth token or service-role text", () => {
    const { container } = renderPage();
    expect(container.textContent).not.toContain("access_token");
    expect(container.textContent).not.toContain("refresh_token");
    expect(container.textContent?.toLowerCase()).not.toContain("service_role");
    expect(container.textContent?.toLowerCase()).not.toContain("service-role");
  });
});
