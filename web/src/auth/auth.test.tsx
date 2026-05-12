// F2.3: focused unit tests for the auth foundation.
//
// Scope is intentionally narrow:
//   - useAuth() outside <AuthProvider> throws
//   - AuthProvider initial state when no token is present
//   - logout() clears the in-memory token holder
//   - ProtectedRoute redirects unauthenticated traffic to /login
//
// What is deliberately NOT covered here:
//   - login() success/failure paths against /auth/login. That requires
//     either mocking the global fetch or pointing at a live backend;
//     both add surface this scaffolding subphase shouldn't take on.
//     Those tests will land alongside the first feature subphase that
//     exercises a real session round-trip.
//   - the AuthScreen page UI. Brittle DOM-shape tests on a visual
//     prototype page don't earn their keep at this stage.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, render, renderHook, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";

import {
  clearAccessToken,
  getAccessToken,
  setAccessToken,
} from "@/api";
import { AuthProvider, ProtectedRoute, useAuth } from "./index";

beforeEach(() => clearAccessToken());
afterEach(() => clearAccessToken());

describe("useAuth", () => {
  it("throws when used outside <AuthProvider>", () => {
    // React logs the thrown error during render; silence it so the
    // test output stays clean. We restore the original at the end.
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

describe("AuthProvider", () => {
  function wrapper({ children }: { children: ReactNode }) {
    return <AuthProvider>{children}</AuthProvider>;
  }

  it("starts unauthenticated when no token is present", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    // Flush the bootstrap effect's microtasks. With no token the
    // shortcut path runs: no /me call, isLoading becomes false.
    await act(async () => {});
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
    expect(result.current.isLoading).toBe(false);
  });

  it("logout() clears the in-memory access-token holder", async () => {
    const { result } = renderHook(() => useAuth(), { wrapper });
    await act(async () => {});

    // Simulate a post-login state by writing directly to the holder.
    // (The real login() flow would do this, plus call /me. Here we
    // only need to verify logout() drops what's there.)
    setAccessToken("fake.access.token");
    expect(getAccessToken()).toBe("fake.access.token");

    act(() => {
      result.current.logout();
    });

    expect(getAccessToken()).toBeNull();
    expect(result.current.user).toBeNull();
    expect(result.current.isAuthenticated).toBe(false);
  });
});

describe("ProtectedRoute", () => {
  function Tree({ initial = "/protected" }: { initial?: string }) {
    return (
      <AuthProvider>
        <MemoryRouter initialEntries={[initial]}>
          <Routes>
            <Route element={<ProtectedRoute />}>
              <Route
                path="/protected"
                element={<div>Secret area</div>}
              />
            </Route>
            <Route path="/login" element={<div>Login here</div>} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    );
  }

  it("redirects unauthenticated users to /login", async () => {
    render(<Tree />);
    // Bootstrap resolves with no token → not authenticated → Navigate
    // to /login. findByText retries until that re-render lands.
    expect(await screen.findByText("Login here")).toBeInTheDocument();
    expect(screen.queryByText("Secret area")).toBeNull();
  });
});
