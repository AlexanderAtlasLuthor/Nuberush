// F2.22.2.G: auth foundation tests — Supabase session + FastAPI /auth/me.
//
// What changed vs the F2.3 suite:
//   - There is no legacy in-memory token holder and no POST /auth/login.
//   - `@/lib/supabase` is mocked so getSession / signInWithPassword /
//     signOut / onAuthStateChange are controllable and offline.
//   - `@/api` is mocked so `authApi.getMe()` (the only /auth/me caller)
//     resolves a fixed app user without real fetch.
//
// Coverage:
//   - useAuth() outside <AuthProvider> throws
//   - AuthProvider treats "no Supabase session" as unauthenticated
//   - AuthProvider bootstraps an existing session via /auth/me
//   - login() calls supabase.auth.signInWithPassword then /auth/me
//   - login() with bad credentials surfaces the error, stays logged out
//   - logout() calls supabase.auth.signOut and clears the user
//   - a SIGNED_OUT auth event clears the user
//   - ProtectedRoute redirects unauthenticated traffic to /login

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, renderHook, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";

import type { AuthUser } from "./types";

// --- Mocks ----------------------------------------------------------------

const supabaseAuth = vi.hoisted(() => ({
  getSession: vi.fn(),
  signInWithPassword: vi.fn(),
  signOut: vi.fn(),
  onAuthStateChange: vi.fn(),
}));

vi.mock("@/lib/supabase", () => ({
  supabase: { auth: supabaseAuth },
}));

const apiRequestMock = vi.hoisted(() => vi.fn());

vi.mock("@/api", () => ({ apiRequest: apiRequestMock }));

import { AuthProvider, ProtectedRoute, useAuth } from "./index";

// --- Fixtures -------------------------------------------------------------

const TEST_USER: AuthUser = {
  id: "11111111-1111-1111-1111-111111111111",
  full_name: "Test Staff",
  email: "staff@example.com",
  role: "staff",
  store_id: "22222222-2222-2222-2222-222222222222",
  is_active: true,
};

const FAKE_SESSION = { access_token: "fake.access.token" };

/** Captured `onAuthStateChange` callback so tests can emit auth events. */
let authChangeCb:
  | ((event: string, session: unknown) => void)
  | null = null;

beforeEach(() => {
  vi.clearAllMocks();
  authChangeCb = null;

  supabaseAuth.onAuthStateChange.mockImplementation(
    (cb: (event: string, session: unknown) => void) => {
      authChangeCb = cb;
      return { data: { subscription: { unsubscribe: vi.fn() } } };
    },
  );
  // Default: no persisted session.
  supabaseAuth.getSession.mockResolvedValue({ data: { session: null } });
  supabaseAuth.signOut.mockResolvedValue({ error: null });
});

afterEach(() => {
  vi.clearAllMocks();
});

function wrapper({ children }: { children: ReactNode }) {
  return <AuthProvider>{children}</AuthProvider>;
}

// --- useAuth --------------------------------------------------------------

describe("useAuth", () => {
  it("throws when used outside <AuthProvider>", () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      expect(() => renderHook(() => useAuth())).toThrow(
        /must be used within an <AuthProvider>/,
      );
    } finally {
      errSpy.mockRestore();
    }
  });
});

// --- AuthProvider bootstrap ----------------------------------------------

describe("AuthProvider bootstrap", () => {
  it("starts unauthenticated when there is no Supabase session", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await act(async () => {});

    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.isLoading).toBe(false);
    // No session → no /auth/me round-trip.
    expect(apiRequestMock).not.toHaveBeenCalled();
  });

  it("bootstraps an existing Supabase session via /auth/me", async () => {
    supabaseAuth.getSession.mockResolvedValue({
      data: { session: FAKE_SESSION },
    });
    apiRequestMock.mockResolvedValue(TEST_USER);

    const { result } = renderHook(() => useAuth(), { wrapper });
    await act(async () => {});

    expect(apiRequestMock).toHaveBeenCalledWith(
      "/auth/me",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result.current.user).toEqual(TEST_USER);
    expect(result.current.isAuthenticated).toBe(true);
    expect(result.current.isLoading).toBe(false);
  });

  it("treats a session with a failing /auth/me as logged out", async () => {
    supabaseAuth.getSession.mockResolvedValue({
      data: { session: FAKE_SESSION },
    });
    apiRequestMock.mockRejectedValue(new Error("401"));

    const { result } = renderHook(() => useAuth(), { wrapper });
    await act(async () => {});

    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.isLoading).toBe(false);
  });
});

// --- login / logout ------------------------------------------------------

describe("AuthProvider login", () => {
  it("signs in via Supabase then loads the user from /auth/me", async () => {
    supabaseAuth.signInWithPassword.mockResolvedValue({
      data: {},
      error: null,
    });
    apiRequestMock.mockResolvedValue(TEST_USER);

    const { result } = renderHook(() => useAuth(), { wrapper });
    await act(async () => {});

    await act(async () => {
      await result.current.login({
        email: "staff@example.com",
        password: "supersecret123",
      });
    });

    expect(supabaseAuth.signInWithPassword).toHaveBeenCalledWith({
      email: "staff@example.com",
      password: "supersecret123",
    });
    expect(apiRequestMock).toHaveBeenCalledWith(
      "/auth/me",
      expect.objectContaining({ method: "GET" }),
    );
    expect(result.current.user).toEqual(TEST_USER);
    expect(result.current.isAuthenticated).toBe(true);
  });

  it("surfaces an error and stays logged out on bad credentials", async () => {
    supabaseAuth.signInWithPassword.mockResolvedValue({
      data: {},
      error: { message: "Invalid login credentials" },
    });

    const { result } = renderHook(() => useAuth(), { wrapper });
    await act(async () => {});

    await act(async () => {
      await expect(
        result.current.login({
          email: "staff@example.com",
          password: "wrong",
        }),
      ).rejects.toThrow(/Invalid login credentials/);
    });

    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    // /auth/me must not run when sign-in failed.
    expect(apiRequestMock).not.toHaveBeenCalled();
  });
});

describe("AuthProvider logout", () => {
  it("signs out via Supabase and clears the user", async () => {
    supabaseAuth.getSession.mockResolvedValue({
      data: { session: FAKE_SESSION },
    });
    apiRequestMock.mockResolvedValue(TEST_USER);

    const { result } = renderHook(() => useAuth(), { wrapper });
    await act(async () => {});
    expect(result.current.user).toEqual(TEST_USER);

    await act(async () => {
      result.current.logout();
    });

    expect(supabaseAuth.signOut).toHaveBeenCalled();
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });

  it("clears the user when a SIGNED_OUT event fires", async () => {
    supabaseAuth.getSession.mockResolvedValue({
      data: { session: FAKE_SESSION },
    });
    apiRequestMock.mockResolvedValue(TEST_USER);

    const { result } = renderHook(() => useAuth(), { wrapper });
    await act(async () => {});
    expect(result.current.user).toEqual(TEST_USER);

    // Emit the event the Supabase client would fire on session loss.
    await act(async () => {
      authChangeCb?.("SIGNED_OUT", null);
    });

    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });
});

// --- AuthProvider recovery / update events (F2.25.4) ----------------------

describe("AuthProvider session-establishing events", () => {
  it.each(["USER_UPDATED", "PASSWORD_RECOVERY"])(
    "loads the user from /auth/me on a %s event with a session",
    async (event) => {
      // Start logged out (no persisted session at bootstrap).
      apiRequestMock.mockResolvedValue(TEST_USER);

      const { result } = renderHook(() => useAuth(), { wrapper });
      await act(async () => {});
      expect(result.current.user).toBeNull();

      // The event the Supabase client fires after a recovery link is
      // consumed (PASSWORD_RECOVERY) or a password is set (USER_UPDATED).
      // The provider defers getMe via setTimeout(0); flush it.
      await act(async () => {
        authChangeCb?.(event, FAKE_SESSION);
        await new Promise((r) => setTimeout(r, 0));
      });

      expect(apiRequestMock).toHaveBeenCalledWith(
        "/auth/me",
        expect.objectContaining({ method: "GET" }),
      );
      expect(result.current.user).toEqual(TEST_USER);
      expect(result.current.isAuthenticated).toBe(true);
    },
  );
});

// --- ProtectedRoute ------------------------------------------------------

describe("ProtectedRoute", () => {
  function Tree({ initial = "/protected" }: { initial?: string }) {
    return (
      <AuthProvider>
        <MemoryRouter initialEntries={[initial]}>
          <Routes>
            <Route element={<ProtectedRoute />}>
              <Route path="/protected" element={<div>Secret area</div>} />
            </Route>
            <Route path="/login" element={<div>Login here</div>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    );
  }

  it("redirects unauthenticated users to /login", async () => {
    render(<Tree />);
    expect(await screen.findByText("Login here")).toBeInTheDocument();
    expect(screen.queryByText("Secret area")).toBeNull();
  });
});
