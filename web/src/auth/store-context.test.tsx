// F2.4: focused unit tests for the tenancy/store context.
//
// Strategy: the StoreProvider derives everything from useAuth(). To
// exercise the derivation in isolation, we mock the useAuth module
// rather than spinning up AuthProvider + a fake /me round-trip. Each
// test sets the mock's return value and renders just the StoreProvider
// (or StoreGate-with-MemoryRouter for the gate tests).
//
// Scope:
//   - useStoreContext() outside <StoreProvider> throws
//   - StoreProvider derives currentStoreId from user.store_id (non-admin)
//   - StoreProvider returns null currentStoreId for admin (global scope,
//     no error)
//   - StoreProvider surfaces storeError when a non-admin user has
//     store_id = null
//   - StoreGate renders ErrorState when storeError is set
//   - StoreGate renders <Outlet/> when context is valid
//   - StoreGate renders <Outlet/> for admin with null store_id

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, renderHook, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import type { ReactNode } from "react";

import { StoreProvider } from "./StoreProvider";
import { useStoreContext } from "./useStoreContext";
import { StoreGate } from "./StoreGate";
import type { AuthContextValue } from "./auth-context";
import type { AuthUser } from "./types";

// Single mockable export. The default returns "no user, not loading".
// Each test calls setMockAuth(...) to override per-case.
const mockAuth: { current: AuthContextValue } = {
  current: {
    user: null,
    isAuthenticated: false,
    isLoading: false,
    login: vi.fn(),
    logout: vi.fn(),
    refreshSession: vi.fn(),
  },
};

vi.mock("./useAuth", () => ({
  useAuth: () => mockAuth.current,
}));

function setMockAuth(partial: Partial<AuthContextValue>) {
  mockAuth.current = { ...mockAuth.current, ...partial };
}

function makeUser(overrides: Partial<AuthUser> = {}): AuthUser {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    full_name: "Test User",
    email: "test@example.com",
    role: "staff",
    store_id: "22222222-2222-2222-2222-222222222222",
    is_active: true,
    ...overrides,
  };
}

beforeEach(() => {
  setMockAuth({
    user: null,
    isAuthenticated: false,
    isLoading: false,
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useStoreContext", () => {
  it("throws when used outside <StoreProvider>", () => {
    const errSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      expect(() => renderHook(() => useStoreContext())).toThrow(
        /must be used within a <StoreProvider>/,
      );
    } finally {
      errSpy.mockRestore();
    }
  });
});

describe("StoreProvider derivation", () => {
  function wrapper({ children }: { children: ReactNode }) {
    return <StoreProvider>{children}</StoreProvider>;
  }

  it("returns a neutral state when no user is authenticated", () => {
    setMockAuth({ user: null, isAuthenticated: false });
    const { result } = renderHook(() => useStoreContext(), { wrapper });
    expect(result.current.currentStoreId).toBeNull();
    expect(result.current.hasStoreContext).toBe(false);
    expect(result.current.isStoreRequired).toBe(false);
    expect(result.current.storeError).toBeNull();
  });

  it("derives currentStoreId from user.store_id for a non-admin user", () => {
    setMockAuth({
      user: makeUser({
        role: "manager",
        store_id: "33333333-3333-3333-3333-333333333333",
      }),
      isAuthenticated: true,
    });
    const { result } = renderHook(() => useStoreContext(), { wrapper });
    expect(result.current.currentStoreId).toBe(
      "33333333-3333-3333-3333-333333333333",
    );
    expect(result.current.hasStoreContext).toBe(true);
    expect(result.current.isStoreRequired).toBe(true);
    expect(result.current.storeError).toBeNull();
  });

  it("returns null currentStoreId for an admin (global scope, no error)", () => {
    setMockAuth({
      user: makeUser({ role: "admin", store_id: null }),
      isAuthenticated: true,
    });
    const { result } = renderHook(() => useStoreContext(), { wrapper });
    expect(result.current.currentStoreId).toBeNull();
    expect(result.current.hasStoreContext).toBe(false);
    expect(result.current.isStoreRequired).toBe(false);
    expect(result.current.storeError).toBeNull();
  });

  it("surfaces storeError when a non-admin user has store_id=null", () => {
    setMockAuth({
      user: makeUser({ role: "staff", store_id: null }),
      isAuthenticated: true,
    });
    const { result } = renderHook(() => useStoreContext(), { wrapper });
    expect(result.current.currentStoreId).toBeNull();
    expect(result.current.hasStoreContext).toBe(false);
    expect(result.current.isStoreRequired).toBe(true);
    expect(result.current.storeError).toMatch(/not bound to a store/i);
  });
});

describe("StoreGate", () => {
  function Tree() {
    return (
      <StoreProvider>
        <MemoryRouter initialEntries={["/app"]}>
          <Routes>
            <Route element={<StoreGate />}>
              <Route path="/app" element={<div>App body</div>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </StoreProvider>
    );
  }

  it("renders the error state for a non-admin with no store_id", () => {
    setMockAuth({
      user: makeUser({ role: "staff", store_id: null }),
      isAuthenticated: true,
    });
    render(<Tree />);
    expect(
      screen.getByText("No store context available"),
    ).toBeInTheDocument();
    expect(screen.queryByText("App body")).toBeNull();
  });

  it("renders the matched outlet for a non-admin with a valid store_id", () => {
    setMockAuth({
      user: makeUser({ role: "staff" }),
      isAuthenticated: true,
    });
    render(<Tree />);
    expect(screen.getByText("App body")).toBeInTheDocument();
    expect(screen.queryByText("No store context available")).toBeNull();
  });

  it("renders the matched outlet for an admin (global scope is allowed)", () => {
    setMockAuth({
      user: makeUser({ role: "admin", store_id: null }),
      isAuthenticated: true,
    });
    render(<Tree />);
    expect(screen.getByText("App body")).toBeInTheDocument();
    expect(screen.queryByText("No store context available")).toBeNull();
  });
});
