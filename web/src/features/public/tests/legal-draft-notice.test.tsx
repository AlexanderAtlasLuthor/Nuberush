import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { TermsPage } from "../legal/TermsPage";
import { PrivacyPage } from "../legal/PrivacyPage";
import { MerchantAgreementPage } from "../legal/MerchantAgreementPage";
import { AcceptableUsePage } from "../legal/AcceptableUsePage";
import { CookiesPage } from "../legal/CookiesPage";
import { LegalHubPage } from "../legal/LegalHubPage";

const LEGAL_PAGES = [
  { name: "LegalHubPage", node: <LegalHubPage />, title: /legal documents/i },
  { name: "TermsPage", node: <TermsPage />, title: /terms of service/i },
  { name: "PrivacyPage", node: <PrivacyPage />, title: /privacy policy/i },
  {
    name: "MerchantAgreementPage",
    node: <MerchantAgreementPage />,
    title: /merchant agreement/i,
  },
  {
    name: "AcceptableUsePage",
    node: <AcceptableUsePage />,
    title: /acceptable use policy/i,
  },
  { name: "CookiesPage", node: <CookiesPage />, title: /cookie policy/i },
] as const;

describe("legal pages render their title and the locked draft notice (F2.21.1)", () => {
  it.each(LEGAL_PAGES)("$name", ({ node, title }) => {
    render(<MemoryRouter>{node}</MemoryRouter>);

    expect(
      screen.getByRole("heading", { level: 1, name: title }),
    ).toBeInTheDocument();

    expect(
      screen.getByText(
        /this document is provided as an operational draft for review and approval by qualified legal counsel before public launch/i,
      ),
    ).toBeInTheDocument();
  });

  it("never claims final legal approval or guaranteed compliance", () => {
    for (const { node } of LEGAL_PAGES) {
      const { unmount } = render(<MemoryRouter>{node}</MemoryRouter>);
      // Patterns must match positive claims only. Safe disclaimers
      // like "this is not legal advice" or "does not guarantee
      // compliance" are explicitly permitted by the F2.21 contract
      // (§9) and must not trip these assertions.
      const banned = [
        /final legal approval/i,
        /this (?:is|constitutes|provides) legal advice/i,
        /\bguaranteed compliance\b/i,
        /this constitutes binding terms/i,
      ];
      for (const pattern of banned) {
        expect(screen.queryByText(pattern)).not.toBeInTheDocument();
      }
      unmount();
    }
  });
});
