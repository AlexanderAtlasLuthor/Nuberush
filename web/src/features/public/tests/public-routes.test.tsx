import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, useRoutes } from "react-router-dom";
import type { AuthContextValue, StoreContextState } from "@/auth";

// Public routes do not depend on auth/store context, but the router
// module also wires authenticated /app/* routes whose imports pull in
// AuthProvider state. We provide the same mock posture as
// router.test.tsx so importing `appRoutes` does not crash and the
// auth-gated branches stay inert during public-route rendering.

const mockAuth = vi.hoisted(
  (): { current: AuthContextValue } => ({
    current: {
      user: null,
      isAuthenticated: false,
      isLoading: false,
      login: vi.fn(),
      logout: vi.fn(),
      refreshSession: vi.fn(),
    },
  }),
);

const mockStore = vi.hoisted(
  (): { current: StoreContextState } => ({
    current: {
      currentStoreId: null,
      hasStoreContext: false,
      isStoreRequired: false,
      storeError: null,
    },
  }),
);

vi.mock("@/auth", async () => {
  const routerDom =
    await vi.importActual<typeof import("react-router-dom")>(
      "react-router-dom",
    );
  return {
    useAuth: () => mockAuth.current,
    useStoreContext: () => mockStore.current,
    ProtectedRoute: () => <routerDom.Outlet />,
    StoreGate: () => (
      <div data-testid="store-gate">
        <routerDom.Outlet />
      </div>
    ),
  };
});

vi.mock("@/pages/AuthScreen", () => ({
  default: () => <div>Login page</div>,
}));

import { appRoutes } from "@/app/router";

function RouteHarness() {
  return useRoutes(appRoutes);
}

function renderPath(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <RouteHarness />
    </MemoryRouter>,
  );
}

const PUBLIC_PAGES: ReadonlyArray<{ path: string; heading: RegExp }> = [
  { path: "/", heading: /operating platform for regulated local commerce/i },
  { path: "/for-stores", heading: /operational clarity before chaos starts/i },
  { path: "/how-it-works", heading: /from request to operating on the platform/i },
  { path: "/features", heading: /capabilities for stores that need operational visibility/i },
  { path: "/contact", heading: /contact nuberush/i },
  { path: "/request-demo", heading: /request a demo of nuberush/i },
  { path: "/apply", heading: /apply to bring your store onto nuberush/i },
  { path: "/support", heading: /support and contact/i },
  { path: "/legal", heading: /legal documents/i },
  { path: "/legal/terms", heading: /terms of service/i },
  { path: "/legal/privacy", heading: /privacy policy/i },
  { path: "/legal/merchant-agreement", heading: /merchant agreement/i },
  { path: "/legal/acceptable-use", heading: /acceptable use policy/i },
  { path: "/legal/cookies", heading: /cookie policy/i },
];

describe("public routes (F2.21.1)", () => {
  it.each(PUBLIC_PAGES)(
    "renders %s with its public layout and a single h1",
    ({ path, heading }) => {
      renderPath(path);

      const headings = screen.getAllByRole("heading", { level: 1 });
      expect(headings).toHaveLength(1);
      expect(headings[0]).toHaveTextContent(heading);

      // PublicLayout markers — header + main + footer should be present.
      expect(
        screen.getByRole("main", { name: /main content/i }),
      ).toBeInTheDocument();
      expect(
        screen.getAllByRole("navigation", {
          name: /public site navigation/i,
        }).length,
      ).toBeGreaterThan(0);
      expect(screen.getByRole("contentinfo")).toBeInTheDocument();

      // Admin/store shells must NOT render on public routes.
      expect(screen.queryByTestId("store-gate")).not.toBeInTheDocument();
      expect(screen.queryByText("Platform Admin")).not.toBeInTheDocument();
      expect(screen.queryByText("Store Operations")).not.toBeInTheDocument();
    },
  );

  it("does not leak admin/store internal nav labels on public routes", () => {
    renderPath("/");
    const leaked = [
      "Admin Dashboard",
      "Store Dashboard",
      "Internal Operations",
    ];
    for (const label of leaked) {
      expect(screen.queryByText(label)).not.toBeInTheDocument();
    }
  });

  it("renders /login independently of the public shell", () => {
    renderPath("/login");
    expect(screen.getByText("Login page")).toBeInTheDocument();
    // /login is intentionally outside PublicLayout — no public header.
    expect(
      screen.queryAllByRole("navigation", {
        name: /public site navigation/i,
      }),
    ).toHaveLength(0);
  });
});
