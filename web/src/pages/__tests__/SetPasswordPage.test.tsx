// F2.25.4.D: tests for the owner password-setup page.
//
// `@/lib/supabase` is mocked so getSession / updateUser are controllable
// and offline. Navigation is asserted via a captured useNavigate mock. The
// page must never render a token. Inputs are driven with fireEvent (the
// repo's convention — no @testing-library/user-event dependency).

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const supabaseAuth = vi.hoisted(() => ({
  getSession: vi.fn(),
  updateUser: vi.fn(),
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

import SetPasswordPage from "../SetPasswordPage";

const FAKE_SESSION = { access_token: "fake.access.token" };

beforeEach(() => {
  vi.clearAllMocks();
  supabaseAuth.getSession.mockResolvedValue({
    data: { session: FAKE_SESSION },
  });
  supabaseAuth.updateUser.mockResolvedValue({ data: {}, error: null });
});

function renderPage() {
  return render(
    <MemoryRouter>
      <SetPasswordPage />
    </MemoryRouter>,
  );
}

async function findForm() {
  return waitFor(() =>
    expect(screen.getByPlaceholderText("New password")).toBeInTheDocument(),
  );
}

function fill(newPw: string, confirmPw: string) {
  fireEvent.change(screen.getByPlaceholderText("New password"), {
    target: { value: newPw },
  });
  fireEvent.change(screen.getByPlaceholderText("Confirm password"), {
    target: { value: confirmPw },
  });
}

function submit() {
  fireEvent.click(screen.getByRole("button", { name: /set password/i }));
}

describe("SetPasswordPage", () => {
  it("A. renders the form when a session exists", async () => {
    renderPage();
    await findForm();

    expect(screen.getByPlaceholderText("New password")).toBeInTheDocument();
    expect(
      screen.getByPlaceholderText("Confirm password"),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /set password/i }),
    ).toBeInTheDocument();
  });

  it("B. redirects to /login when no session exists", async () => {
    supabaseAuth.getSession.mockResolvedValue({ data: { session: null } });

    renderPage();

    await waitFor(() =>
      expect(navigateMock).toHaveBeenCalledWith("/login", { replace: true }),
    );
  });

  it("C. shows a validation error and does not call updateUser on mismatch", async () => {
    renderPage();
    await findForm();

    fill("password123", "different123");
    submit();

    expect(screen.getByRole("alert")).toHaveTextContent(/do not match/i);
    expect(supabaseAuth.updateUser).not.toHaveBeenCalled();
  });

  it("D. shows a validation error and does not call updateUser on a short password", async () => {
    renderPage();
    await findForm();

    fill("short", "short");
    submit();

    expect(screen.getByRole("alert")).toHaveTextContent(/at least 8/i);
    expect(supabaseAuth.updateUser).not.toHaveBeenCalled();
  });

  it("E. calls updateUser and redirects to /app on success", async () => {
    renderPage();
    await findForm();

    fill("password123", "password123");
    submit();

    await waitFor(() =>
      expect(supabaseAuth.updateUser).toHaveBeenCalledWith({
        password: "password123",
      }),
    );
    await waitFor(() =>
      expect(navigateMock).toHaveBeenCalledWith("/app", { replace: true }),
    );
  });

  it("F. shows a safe error and does not redirect when updateUser fails", async () => {
    supabaseAuth.updateUser.mockResolvedValue({
      data: {},
      error: new Error("Password is too weak"),
    });

    renderPage();
    await findForm();

    fill("password123", "password123");
    submit();

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(
        /password is too weak/i,
      ),
    );
    expect(navigateMock).not.toHaveBeenCalledWith("/app", { replace: true });
  });

  it("G. never renders a token in the DOM", async () => {
    const { container } = renderPage();
    await findForm();

    expect(container.textContent).not.toContain("access_token");
    expect(container.textContent).not.toContain("fake.access.token");
  });
});
