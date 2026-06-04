// F2.25.5: focused test that the login page exposes the password-recovery
// affordance. The full login flow is covered by the AuthProvider suite
// (web/src/auth/auth.test.tsx); here we only assert the "Forgot password?"
// link is present and points at the public recovery route.

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

vi.mock("@/auth", () => ({
  useAuth: () => ({ login: vi.fn(), isLoading: false }),
}));

vi.mock("@/api", () => ({
  getApiErrorMessage: (e: unknown) => String(e),
}));

import AuthScreen from "../AuthScreen";

describe("AuthScreen recovery affordance", () => {
  it("shows a 'Forgot password?' link to /auth/forgot-password", () => {
    render(
      <MemoryRouter>
        <AuthScreen />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("link", { name: /forgot password/i }),
    ).toHaveAttribute("href", "/auth/forgot-password");
  });

  it("keeps the existing 'Apply to open a store' link to /apply", () => {
    render(
      <MemoryRouter>
        <AuthScreen />
      </MemoryRouter>,
    );

    expect(
      screen.getByRole("link", { name: /apply to open a store/i }),
    ).toHaveAttribute("href", "/apply");
  });
});
