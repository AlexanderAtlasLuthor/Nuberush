import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import {
  MemoryRouter,
  useLocation,
  useRoutes,
} from "react-router-dom";
import type { AuthContextValue, AuthUser, StoreContextState } from "@/auth";

const mockAuth = vi.hoisted(
  (): { current: AuthContextValue } => ({
    current: {
      user: null,
      isAuthenticated: true,
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
      currentStoreId: "22222222-2222-2222-2222-222222222222",
      hasStoreContext: true,
      isStoreRequired: true,
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

vi.mock("@/features/dashboard/pages/DashboardHomePage", () => ({
  default: () => <div>Store dashboard page</div>,
}));

vi.mock("@/features/products/pages/ProductsPage", () => ({
  default: () => <div>Products page</div>,
}));

vi.mock("@/features/products/pages/ProductDetailPage", () => ({
  default: () => <div>Product detail page</div>,
}));

vi.mock("@/features/inventory/pages/InventoryPage", () => ({
  default: () => <div>Inventory page</div>,
}));

vi.mock("@/features/inventory/pages/AdminInventoryPage", () => ({
  default: () => <div>Admin inventory page</div>,
}));

vi.mock("@/features/orders/pages/OrdersPage", () => ({
  default: () => <div>Orders page</div>,
}));

vi.mock("@/features/orders/pages/AdminOrdersPage", () => ({
  default: () => <div>Admin orders page</div>,
}));

vi.mock("@/features/orders/pages/CreateOrderPage", () => ({
  default: () => <div>Create order page</div>,
}));

vi.mock("@/features/orders/pages/OrderDetailPage", () => ({
  default: () => <div>Order detail page</div>,
}));

vi.mock("@/features/users/pages/UsersPage", () => ({
  default: () => <div>Users page</div>,
}));

vi.mock("@/features/audit/pages/AuditPage", () => ({
  default: () => <div>Audit page</div>,
}));

vi.mock("@/features/audit/pages/AdminAuditPage", () => ({
  default: () => <div>Admin audit page</div>,
}));

vi.mock("@/features/store/pages/StoreSettingsPage", () => ({
  default: () => <div>Store settings page</div>,
}));

vi.mock("@/features/stores/pages/AdminStoresPage", () => ({
  default: () => <div>Admin stores page</div>,
}));

vi.mock("@/features/stores/pages/AdminStoreDetailPage", () => ({
  default: () => <div>Admin store detail page</div>,
}));

// F2.19.5: /app/admin now mounts the real AdminDashboardPage. Mock
// it the same way the other admin pages are mocked so router tests
// stay independent of the dashboard's internals.
vi.mock("@/features/admin-dashboard/pages/AdminDashboardPage", () => ({
  default: () => <div>Admin dashboard page</div>,
}));

// F2.19.6: /app/admin/operations now mounts the real
// AdminOperationsPage. Same mock convention.
vi.mock("@/features/admin-operations/pages/AdminOperationsPage", () => ({
  default: () => <div>Admin operations page</div>,
}));

import { appRoutes } from "./router";

function makeUser(overrides: Partial<AuthUser> = {}): AuthUser {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    full_name: "Ada Lovelace",
    email: "ada@example.com",
    role: "manager",
    store_id: "22222222-2222-2222-2222-222222222222",
    is_active: true,
    ...overrides,
  };
}

function setAuth(user: AuthUser | null) {
  mockAuth.current = {
    ...(mockAuth.current as AuthContextValue),
    user,
    isAuthenticated: user !== null,
  };
}

function setStore(overrides: Partial<StoreContextState> = {}) {
  mockStore.current = {
    currentStoreId: "22222222-2222-2222-2222-222222222222",
    hasStoreContext: true,
    isStoreRequired: true,
    storeError: null,
    ...overrides,
  };
}

function RouteHarness() {
  const element = useRoutes(appRoutes);
  const location = useLocation();

  return (
    <>
      {element}
      <div data-testid="location-path">{location.pathname}</div>
    </>
  );
}

function renderRoute(
  path: string,
  user: AuthUser | null = makeUser(),
  storeOverrides: Partial<StoreContextState> = {},
) {
  setAuth(user);
  setStore(storeOverrides);
  return render(
    <MemoryRouter initialEntries={[path]}>
      <RouteHarness />
    </MemoryRouter>,
  );
}

function getSidebar() {
  return screen.getByRole("complementary", {
    name: /primary navigation/i,
  });
}

function expectSidebarLink(label: string, href: string) {
  expect(within(getSidebar()).getByRole("link", { name: label })).toHaveAttribute(
    "href",
    href,
  );
}

function expectNoSidebarLinks(paths: RegExp) {
  for (const link of within(getSidebar()).queryAllByRole("link")) {
    expect(link).not.toHaveAttribute("href", expect.stringMatching(paths));
  }
}

async function expectRedirect(
  from: string,
  to: string,
  user: AuthUser | null = makeUser(),
) {
  renderRoute(from, user);
  await waitFor(() =>
    expect(screen.getByTestId("location-path").textContent).toBe(to),
  );
}

describe("app route split", () => {
  it("redirects /app for admin users to /app/admin", async () => {
    await expectRedirect(
      "/app",
      "/app/admin",
      makeUser({ role: "admin", store_id: null }),
    );
  });

  it.each(["owner", "manager", "staff"] as const)(
    "redirects /app for %s users to /app/store",
    async (role) => {
      await expectRedirect("/app", "/app/store", makeUser({ role }));
    },
  );

  it("redirects unsupported app roles to /login", async () => {
    await expectRedirect(
      "/app",
      "/login",
      makeUser({ role: "driver", store_id: null }),
    );
    expect(mockAuth.current.logout).toHaveBeenCalledTimes(1);
  });

  it.each([
    ["/app/products", "/app/store/products"],
    ["/app/products/product-1", "/app/store/products/product-1"],
    ["/app/inventory", "/app/store/inventory"],
    ["/app/inventory/variant-1", "/app/store/inventory/variant-1"],
    ["/app/orders", "/app/store/orders"],
    ["/app/orders/new", "/app/store/orders/new"],
    ["/app/orders/order-1", "/app/store/orders/order-1"],
    ["/app/users", "/app/store/users"],
    ["/app/audit", "/app/store/audit"],
    ["/app/settings", "/app/store/settings"],
  ])("redirects legacy route %s to %s", async (from, to) => {
    await expectRedirect(from, to);
  });

  // F2.19.6: /app/admin/operations now mounts the real
  // AdminOperationsPage. The placeholder copy ("Admin Operations",
  // "Operations alerts endpoint", "No fake incidents") must not
  // appear at that path anymore. The remaining placeholder routes
  // (products / compliance / settings) keep their copy — covered
  // by the parametrized tests below.
  it("renders the real AdminOperationsPage at /app/admin/operations (no longer a placeholder)", async () => {
    renderRoute(
      "/app/admin/operations",
      makeUser({ role: "admin", store_id: null }),
      {
        currentStoreId: null,
        hasStoreContext: false,
        isStoreRequired: false,
      },
    );
    expect(
      await screen.findByText("Admin operations page"),
    ).toBeInTheDocument();
    // Placeholder copy must NOT be present anywhere.
    expect(
      screen.queryByRole("heading", { name: "Admin Operations" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Operations alerts endpoint"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("No fake incidents")).not.toBeInTheDocument();
    expect(screen.queryByText("Backend Required")).not.toBeInTheDocument();
    expect(screen.queryByTestId("store-gate")).not.toBeInTheDocument();
  });

  // F2.19.5: /app/admin now mounts the real AdminDashboardPage.
  // The placeholder copy ("Admin dashboard KPI endpoints", "No fake
  // admin data is rendered.", "No simulated KPIs", etc.) must NOT
  // appear at /app/admin anymore. The remaining placeholder routes
  // (products / compliance / operations / settings) keep their copy
  // — covered by the parametrized tests below.
  it("renders the real AdminDashboardPage at /app/admin (no longer a placeholder)", async () => {
    renderRoute(
      "/app/admin",
      makeUser({ role: "admin", store_id: null }),
      {
        currentStoreId: null,
        hasStoreContext: false,
        isStoreRequired: false,
      },
    );
    expect(
      await screen.findByText("Admin dashboard page"),
    ).toBeInTheDocument();
    // Placeholder copy must NOT be present anywhere.
    expect(
      screen.queryByRole("heading", { name: "Admin Dashboard" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Admin dashboard KPI endpoints"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("No fake admin data is rendered."),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Backend Required")).not.toBeInTheDocument();
    // Admin shell still applies; store gate must not.
    expect(screen.queryByTestId("store-gate")).not.toBeInTheDocument();
  });

  it("renders the real AdminStoresPage at /app/admin/stores (no longer a placeholder)", async () => {
    renderRoute(
      "/app/admin/stores",
      makeUser({ role: "admin", store_id: null }),
    );
    expect(await screen.findByText("Admin stores page")).toBeInTheDocument();
    expectSidebarLink("Stores", "/app/admin/stores");
    expectSidebarLink("Compliance", "/app/admin/compliance");
    expectSidebarLink("Operations", "/app/admin/operations");
    expectNoSidebarLinks(/^\/app\/store/);
    // Placeholder copy must NOT be present anywhere.
    expect(
      screen.queryByRole("heading", { name: "Admin Stores" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("GET /stores")).not.toBeInTheDocument();
    expect(screen.queryByText("No fake store list")).not.toBeInTheDocument();
    expect(screen.queryByText("Backend Required")).not.toBeInTheDocument();
  });

  it("renders the real AdminStoreDetailPage at /app/admin/stores/:storeId (no longer a placeholder)", async () => {
    renderRoute(
      "/app/admin/stores/store-1",
      makeUser({ role: "admin", store_id: null }),
    );
    expect(
      await screen.findByText("Admin store detail page"),
    ).toBeInTheDocument();
    // Placeholder copy must NOT be present anywhere.
    expect(
      screen.queryByRole("heading", { name: "Admin Store Detail" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("GET /stores/:storeId")).not.toBeInTheDocument();
    expect(
      screen.queryByText("storeId route parameter: store-1"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(
        "Route context only; no store data is fetched or fabricated.",
      ),
    ).not.toBeInTheDocument();
  });

  // F2.15.7 + F2.18.3 + F2.19.5: /app/admin/users, /app/admin/stores,
  // /app/admin/stores/:storeId and /app/admin no longer render
  // placeholders — they mount real pages. The placeholder-blocker
  // matrix intentionally excludes them.
  it.each([
    [
      "/app/admin/products",
      "Admin Global Products",
      "Global products query",
    ],
    [
      "/app/admin/compliance",
      "Admin Compliance",
      "Global compliance feed",
    ],
    [
      "/app/admin/settings",
      "Admin Settings",
      "Platform settings endpoint",
    ],
  ])(
    "renders admin placeholder route %s with backend blockers",
    async (path, heading, blocker) => {
      renderRoute(
        path,
        makeUser({ role: "admin", store_id: null }),
        {
          currentStoreId: null,
          hasStoreContext: false,
          isStoreRequired: false,
        },
      );

      expect(
        await screen.findByRole("heading", { name: heading }),
      ).toBeInTheDocument();
      expect(screen.getAllByText("Platform Admin").length).toBeGreaterThan(0);
      expect(screen.getAllByText("Global scope").length).toBeGreaterThan(0);
      expect(screen.getByText("Status")).toBeInTheDocument();
      expect(screen.getByText("Backend Required")).toBeInTheDocument();
      expect(
        screen.getByText("Required backend capabilities"),
      ).toBeInTheDocument();
      expect(screen.getByText("Not simulated in frontend")).toBeInTheDocument();
      expect(screen.getByText("Future capabilities")).toBeInTheDocument();
      expect(screen.getByText(blocker)).toBeInTheDocument();
      expect(
        screen.getByText("No fake admin data is rendered."),
      ).toBeInTheDocument();
      expect(screen.queryByTestId("store-gate")).not.toBeInTheDocument();
      expect(screen.queryByText("Store Operations")).not.toBeInTheDocument();
      expect(screen.queryByText(/Store: /)).not.toBeInTheDocument();
    },
  );

  it.each([
    // F2.15.7: /app/admin/users now renders the real UsersPage.
    // F2.18.3: /app/admin/stores now renders the real AdminStoresPage.
    // F2.18.4: /app/admin/audit now renders the real AdminAuditPage.
    // F2.18.5: /app/admin/inventory and /app/admin/orders now render
    //          the real AdminInventoryPage and AdminOrdersPage.
    // F2.19.5: /app/admin now renders the real AdminDashboardPage —
    //          its "No simulated KPIs" / "No fake global metrics"
    //          rows are gone with the placeholder.
    // F2.19.6: /app/admin/operations now renders the real
    //          AdminOperationsPage — its "No fake incidents" row is
    //          gone with the placeholder.
    ["/app/admin/products", "No fake product data"],
    ["/app/admin/compliance", "No fake compliance queue"],
    ["/app/admin/settings", "No billing simulation"],
  ])("renders admin non-goal %s", async (path, nonGoal) => {
    renderRoute(
      path,
      makeUser({ role: "admin", store_id: null }),
      {
        currentStoreId: null,
        hasStoreContext: false,
        isStoreRequired: false,
      },
    );

    expect(await screen.findByText(nonGoal)).toBeInTheDocument();
  });

  it("renders the real UsersPage at /app/admin/users (no longer a placeholder)", async () => {
    renderRoute(
      "/app/admin/users",
      makeUser({ role: "admin", store_id: null }),
      {
        currentStoreId: null,
        hasStoreContext: false,
        isStoreRequired: false,
      },
    );
    expect(await screen.findByText("Users page")).toBeInTheDocument();
    // The placeholder copy must NOT be present anywhere.
    expect(screen.queryByText("Admin Users")).not.toBeInTheDocument();
    expect(screen.queryByText("GET /auth/users")).not.toBeInTheDocument();
    expect(screen.queryByText("Backend Required")).not.toBeInTheDocument();
    expect(
      screen.queryByText("No frontend role authority"),
    ).not.toBeInTheDocument();
  });

  it("renders the real AdminInventoryPage at /app/admin/inventory (no longer a placeholder)", async () => {
    renderRoute(
      "/app/admin/inventory",
      makeUser({ role: "admin", store_id: null }),
      {
        currentStoreId: null,
        hasStoreContext: false,
        isStoreRequired: false,
      },
    );
    expect(
      await screen.findByText("Admin inventory page"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Admin Global Inventory" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Global inventory query"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Backend Required")).not.toBeInTheDocument();
    expect(
      screen.queryByText("No fake stock totals"),
    ).not.toBeInTheDocument();
  });

  it("renders the real AdminOrdersPage at /app/admin/orders (no longer a placeholder)", async () => {
    renderRoute(
      "/app/admin/orders",
      makeUser({ role: "admin", store_id: null }),
      {
        currentStoreId: null,
        hasStoreContext: false,
        isStoreRequired: false,
      },
    );
    expect(
      await screen.findByText("Admin orders page"),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("heading", { name: "Admin Global Orders" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText("Global orders query"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Backend Required")).not.toBeInTheDocument();
    expect(
      screen.queryByText("No frontend aggregation of store orders"),
    ).not.toBeInTheDocument();
  });

  it("renders the real AdminAuditPage at /app/admin/audit (no longer a placeholder)", async () => {
    renderRoute(
      "/app/admin/audit",
      makeUser({ role: "admin", store_id: null }),
      {
        currentStoreId: null,
        hasStoreContext: false,
        isStoreRequired: false,
      },
    );
    expect(
      await screen.findByText("Admin audit page"),
    ).toBeInTheDocument();
    // Placeholder copy must NOT be present anywhere.
    expect(
      screen.queryByRole("heading", { name: "Admin Audit" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Global audit feed")).not.toBeInTheDocument();
    expect(screen.queryByText("Backend Required")).not.toBeInTheDocument();
    expect(
      screen.queryByText("No fake audit events"),
    ).not.toBeInTheDocument();
  });

  it.each([
    ["/app/store", "Store dashboard page"],
    ["/app/store/products", "Products page"],
    ["/app/store/products/product-1", "Product detail page"],
    ["/app/store/inventory", "Inventory page"],
    ["/app/store/inventory/variant-1", "Inventory page"],
    ["/app/store/orders", "Orders page"],
    ["/app/store/orders/new", "Create order page"],
    ["/app/store/orders/order-1", "Order detail page"],
    ["/app/store/users", "Users page"],
    ["/app/store/audit", "Audit page"],
    ["/app/store/settings", "Store settings page"],
  ])("renders store route %s", async (path, label) => {
    renderRoute(path);
    expect(await screen.findByText(label)).toBeInTheDocument();
    expect(screen.getByTestId("store-gate")).toBeInTheDocument();
    expect(screen.getAllByText("Store Operations").length).toBeGreaterThan(0);
    expect(screen.queryByText("Platform Admin")).not.toBeInTheDocument();
    expect(screen.queryByText("Global scope")).not.toBeInTheDocument();
    expectSidebarLink("Dashboard", "/app/store");
    expectSidebarLink("Products", "/app/store/products");
    expectNoSidebarLinks(/^\/app\/admin/);
    expect(screen.getByTestId("store-context-indicator")).toHaveTextContent(
      "Store scope | Store: 22222222-2222-2222-2222-222222222222",
    );
  });

  it("legacy product redirect lands in the store navigation surface", async () => {
    renderRoute("/app/products");
    await waitFor(() =>
      expect(screen.getByTestId("location-path").textContent).toBe(
        "/app/store/products",
      ),
    );

    expect(await screen.findByText("Products page")).toBeInTheDocument();
    expectSidebarLink("Products", "/app/store/products");
    expectNoSidebarLinks(/^\/app\/admin/);
  });
});
