import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { HomePage } from "../pages/HomePage";
import {
  FAQ_ITEMS,
  FEATURES,
  HERO_COPY,
} from "../content/publicCopy";

function renderHome() {
  return render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>,
  );
}

function expectLinkTo(label: RegExp, href: string) {
  const matches = screen.getAllByRole("link", { name: label });
  expect(matches.length).toBeGreaterThan(0);
  expect(matches.some((el) => el.getAttribute("href") === href)).toBe(true);
}

describe("HomePage (F2.21.2)", () => {
  describe("hero", () => {
    it("renders exactly one h1 with the locked headline", () => {
      renderHome();
      const headings = screen.getAllByRole("heading", { level: 1 });
      expect(headings).toHaveLength(1);
      expect(headings[0]).toHaveTextContent(HERO_COPY.headline);
    });

    it("renders the value-proposition subhead", () => {
      renderHome();
      expect(
        screen.getByText(/single workspace for stores to run products/i),
      ).toBeInTheDocument();
    });

    it("primary CTA points to /request-demo", () => {
      renderHome();
      expectLinkTo(/^request demo$/i, "/request-demo");
    });

    it("secondary CTA points to /how-it-works", () => {
      renderHome();
      expectLinkTo(/^see how it works$/i, "/how-it-works");
    });
  });

  describe("required section headings", () => {
    it.each([
      /the problems regulated stores actually face/i,
      /store operations in one workspace/i,
      /what the platform actually ships/i,
      /from first conversation to operating on the platform/i,
      /built for regulated local commerce/i,
      /the operational areas nuberush is organizing/i,
      /talk to the nuberush team/i,
      /frequently asked questions/i,
    ])("renders section heading matching %s", (heading) => {
      renderHome();
      expect(
        screen.getByRole("heading", { level: 2, name: heading }),
      ).toBeInTheDocument();
    });
  });

  describe("feature grid", () => {
    const REQUIRED_FEATURES = [
      "Product oversight",
      "Inventory visibility",
      "Order operations",
      "Compliance visibility",
      "Audit trail",
      "Admin console",
      "Store workspace",
      "Operations alerts",
    ] as const;

    it("renders all eight required feature cards", () => {
      renderHome();
      for (const title of REQUIRED_FEATURES) {
        expect(screen.getAllByText(title).length).toBeGreaterThan(0);
      }
    });

    it("feature copy matches the locked content module", () => {
      renderHome();
      for (const feature of FEATURES) {
        expect(screen.getByText(feature.body)).toBeInTheDocument();
      }
    });
  });

  describe("FAQ", () => {
    it("renders every required question", () => {
      renderHome();
      for (const item of FAQ_ITEMS) {
        expect(
          screen.getByText(item.question, { selector: "span" }),
        ).toBeInTheDocument();
      }
    });

    it.each([
      /what is nuberush\?/i,
      /who is nuberush for\?/i,
      /is nuberush only for smoke shops\?/i,
      /can stores manage products\?/i,
      /does nuberush handle compliance\?/i,
      /can i request a demo\?/i,
      /is self-serve signup available\?/i,
      /is nuberush available outside south florida\?/i,
    ])("renders FAQ question matching %s", (pattern) => {
      renderHome();
      expect(screen.getByText(pattern)).toBeInTheDocument();
    });

    it("self-serve answer says signup is not available yet", () => {
      renderHome();
      expect(
        screen.getByText(/self-serve signup is not available yet/i),
      ).toBeInTheDocument();
    });

    it("compliance answer keeps responsibility with the merchant", () => {
      renderHome();
      // The phrase is intentionally repeated in the FAQ answer and the
      // "Built for regulated local commerce" section so the disclaimer
      // is visible without forcing the FAQ open.
      expect(
        screen.getAllByText(
          /merchants remain responsible for understanding and following/i,
        ).length,
      ).toBeGreaterThan(0);
    });
  });

  describe("how it works preview", () => {
    it("links to /how-it-works", () => {
      renderHome();
      expectLinkTo(/^learn how it works$/i, "/how-it-works");
    });
  });

  describe("contact / demo CTA band", () => {
    it("links to /request-demo and /contact", () => {
      renderHome();
      // Request demo appears in hero AND CTA band — getAllByRole asserts
      // both surfaces resolve to /request-demo.
      const requestDemoLinks = screen
        .getAllByRole("link", { name: /^request demo$/i })
        .filter((el) => el.getAttribute("href") === "/request-demo");
      expect(requestDemoLinks.length).toBeGreaterThanOrEqual(2);
      expectLinkTo(/^contact us$/i, "/contact");
    });
  });

  describe("truthfulness guard", () => {
    it("renders no form, no submit button, no textbox", () => {
      const { container } = renderHome();
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
      /instant approval/i,
      /automatic legal verification/i,
      /approved by government/i,
      /guaranteed delivery/i,
    ])("never claims %s", (banned) => {
      renderHome();
      expect(screen.queryByText(banned)).not.toBeInTheDocument();
    });

    it.each([
      /trusted by [0-9]/i,
      /10,000\+? stores/i,
      /\$[0-9]+ ?(?:m|b)illion/i,
      /99\.[0-9]+%/i,
      /featured in/i,
      /as seen on/i,
    ])("renders no fake stats or testimonial markers (%s)", (pattern) => {
      renderHome();
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
    ])("renders no fake logos/social link (%s)", (pattern) => {
      renderHome();
      expect(screen.queryByText(pattern)).not.toBeInTheDocument();
    });
  });

  describe("no admin/store nav leakage", () => {
    it.each([
      "Admin Dashboard",
      "Store Dashboard",
      "Internal Operations",
      "Platform Admin",
      "Store Operations",
    ])("does not render internal nav label %s", (label) => {
      renderHome();
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    });
  });
});
