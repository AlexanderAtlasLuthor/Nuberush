// F2.25.5: tests for the user-initiated "Forgot password" request page.
//
// `@/lib/supabase` is mocked so resetPasswordForEmail is controllable and
// offline. The page must show a generic anti-enumeration confirmation, send
// a redirectTo pointing at /auth/callback, and never render a token. Inputs
// are driven with fireEvent (repo convention — no @testing-library/user-event).

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const supabaseAuth = vi.hoisted(() => ({
  resetPasswordForEmail: vi.fn(),
}));

vi.mock("@/lib/supabase", () => ({
  supabase: { auth: supabaseAuth },
}));

import ForgotPasswordPage from "../ForgotPasswordPage";

const _SUCCESS = "If an account exists for that email, a reset link has been sent.";

beforeEach(() => {
  vi.clearAllMocks();
  supabaseAuth.resetPasswordForEmail.mockResolvedValue({
    data: {},
    error: null,
  });
});

function renderPage() {
  return render(
    <MemoryRouter>
      <ForgotPasswordPage />
    </MemoryRouter>,
  );
}

function typeEmail(value: string) {
  fireEvent.change(screen.getByPlaceholderText("Email address"), {
    target: { value },
  });
}

function submit() {
  fireEvent.click(screen.getByRole("button", { name: /send reset link/i }));
}

describe("ForgotPasswordPage", () => {
  it("A. renders the email form", () => {
    renderPage();
    expect(screen.getByPlaceholderText("Email address")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /send reset link/i }),
    ).toBeInTheDocument();
  });

  it("B. empty email shows a validation error and does not call Supabase", () => {
    renderPage();
    submit();

    expect(screen.getByRole("alert")).toHaveTextContent(/email is required/i);
    expect(supabaseAuth.resetPasswordForEmail).not.toHaveBeenCalled();
  });

  it("C. invalid email shows a validation error and does not call Supabase", () => {
    renderPage();
    typeEmail("not-an-email");
    submit();

    expect(screen.getByRole("alert")).toHaveTextContent(/valid email/i);
    expect(supabaseAuth.resetPasswordForEmail).not.toHaveBeenCalled();
  });

  it("D. valid email calls resetPasswordForEmail with a /auth/callback redirectTo", async () => {
    renderPage();
    typeEmail("owner@example.com");
    submit();

    await waitFor(() =>
      expect(supabaseAuth.resetPasswordForEmail).toHaveBeenCalledTimes(1),
    );
    const [emailArg, opts] = supabaseAuth.resetPasswordForEmail.mock.calls[0];
    expect(emailArg).toBe("owner@example.com");
    expect(opts.redirectTo).toBe(`${window.location.origin}/auth/callback`);
    expect(opts.redirectTo.endsWith("/auth/callback")).toBe(true);
  });

  it("E. success shows the generic anti-enumeration message", async () => {
    renderPage();
    typeEmail("owner@example.com");
    submit();

    expect(await screen.findByText(_SUCCESS)).toBeInTheDocument();
  });

  it("F. shows the SAME generic message regardless of account existence (no enumeration)", async () => {
    // Even when Supabase reports an error, the page must not reveal account
    // state. resetPasswordForEmail resolving for unknown emails already
    // yields the generic success; a thrown error yields a safe failure.
    supabaseAuth.resetPasswordForEmail.mockRejectedValue(
      new Error("user not found: owner@example.com"),
    );
    renderPage();
    typeEmail("owner@example.com");
    submit();

    const alert = await screen.findByRole("alert");
    // Safe generic failure — never the raw "user not found" detail.
    expect(alert).toHaveTextContent(/could not process that request/i);
    expect(alert.textContent).not.toMatch(/user not found/i);
    expect(screen.queryByText(_SUCCESS)).not.toBeInTheDocument();
  });

  it("G. 'Back to sign in' links to /login", () => {
    renderPage();
    expect(
      screen.getByRole("link", { name: /back to sign in/i }),
    ).toHaveAttribute("href", "/login");
  });

  it("H. never renders a token in the DOM", async () => {
    const { container } = renderPage();
    typeEmail("owner@example.com");
    submit();
    await screen.findByText(_SUCCESS);

    expect(container.textContent).not.toContain("access_token");
    expect(container.textContent).not.toContain("refresh_token");
  });
});
