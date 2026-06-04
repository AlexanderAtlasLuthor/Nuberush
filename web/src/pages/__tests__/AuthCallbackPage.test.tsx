// F2.25.4.C: tests for the Supabase auth-link landing page.
//
// `@/lib/supabase` is mocked so getSession / exchangeCodeForSession /
// onAuthStateChange are controllable and offline. Navigation is asserted
// via a captured useNavigate mock. No real network; the page must never
// render a token (asserted directly).

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const supabaseAuth = vi.hoisted(() => ({
  getSession: vi.fn(),
  exchangeCodeForSession: vi.fn(),
  onAuthStateChange: vi.fn(),
}));

vi.mock("@/lib/supabase", () => ({
  supabase: { auth: supabaseAuth },
}));

const navigateMock = vi.hoisted(() => vi.fn());

vi.mock("react-router-dom", async () => {
  const actual =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return { ...actual, useNavigate: () => navigateMock };
});

import AuthCallbackPage from "../AuthCallbackPage";

const FAKE_SESSION = { access_token: "fake.access.token" };

let authChangeCb:
  | ((event: string, session: unknown) => void)
  | null = null;

function setUrl(path: string) {
  window.history.replaceState({}, "", path);
}

beforeEach(() => {
  vi.clearAllMocks();
  authChangeCb = null;

  supabaseAuth.onAuthStateChange.mockImplementation(
    (cb: (event: string, session: unknown) => void) => {
      authChangeCb = cb;
      return { data: { subscription: { unsubscribe: vi.fn() } } };
    },
  );
  // Defaults: no session, no code.
  supabaseAuth.getSession.mockResolvedValue({ data: { session: null } });
  supabaseAuth.exchangeCodeForSession.mockResolvedValue({
    data: { session: null },
    error: null,
  });
  setUrl("/auth/callback");
});

afterEach(() => {
  setUrl("/");
});

function renderPage() {
  return render(
    <MemoryRouter>
      <AuthCallbackPage />
    </MemoryRouter>,
  );
}

describe("AuthCallbackPage", () => {
  it("A. renders the verifying state initially", () => {
    renderPage();
    expect(screen.getByText(/verifying your link/i)).toBeInTheDocument();
  });

  it("B. redirects to /auth/set-password when getSession returns a session", async () => {
    supabaseAuth.getSession.mockResolvedValue({
      data: { session: FAKE_SESSION },
    });

    renderPage();

    await waitFor(() =>
      expect(navigateMock).toHaveBeenCalledWith("/auth/set-password", {
        replace: true,
      }),
    );
  });

  it("C. redirects on a PASSWORD_RECOVERY event with a session", async () => {
    renderPage();

    await act(async () => {
      authChangeCb?.("PASSWORD_RECOVERY", FAKE_SESSION);
    });

    expect(navigateMock).toHaveBeenCalledWith("/auth/set-password", {
      replace: true,
    });
  });

  it("D. handles ?code= by exchanging it and redirecting on success", async () => {
    setUrl("/auth/callback?code=abc123");
    supabaseAuth.exchangeCodeForSession.mockResolvedValue({
      data: { session: FAKE_SESSION },
      error: null,
    });

    renderPage();

    await waitFor(() =>
      expect(supabaseAuth.exchangeCodeForSession).toHaveBeenCalledWith(
        "abc123",
      ),
    );
    await waitFor(() =>
      expect(navigateMock).toHaveBeenCalledWith("/auth/set-password", {
        replace: true,
      }),
    );
  });

  it("E. shows a safe error when the URL carries error params", async () => {
    setUrl("/auth/callback#error=access_denied&error_description=otp+expired");

    renderPage();

    expect(
      screen.getByText(/this link is invalid or has expired/i),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: /back to sign in/i }),
    ).toHaveAttribute("href", "/login");
    expect(navigateMock).not.toHaveBeenCalled();
  });

  it("F. shows a safe error when no session is established before the timeout", async () => {
    vi.useFakeTimers();
    try {
      renderPage();
      // Flush the async getSession() (null) microtasks, then trip the timer.
      await act(async () => {
        await vi.runOnlyPendingTimersAsync();
      });
      await act(async () => {
        await vi.advanceTimersByTimeAsync(5000);
      });

      expect(
        screen.getByText(/this link is invalid or has expired/i),
      ).toBeInTheDocument();
      expect(navigateMock).not.toHaveBeenCalled();
    } finally {
      vi.useRealTimers();
    }
  });

  it("G. never renders a token, code, or raw token-bearing URL contents", async () => {
    setUrl(
      "/auth/callback#access_token=fake.access.token&refresh_token=fake.refresh",
    );

    const { container } = renderPage();
    await act(async () => {
      await Promise.resolve();
    });

    expect(container.textContent).not.toContain("access_token");
    expect(container.textContent).not.toContain("refresh_token");
    expect(container.textContent).not.toContain("fake.access.token");
    expect(container.textContent).not.toContain("fake.refresh");
  });
});
