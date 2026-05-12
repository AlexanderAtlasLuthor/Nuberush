import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";

import { AdminLayout } from "./AdminLayout";
import { DashboardLayout } from "./DashboardLayout";
import { StoreLayout } from "./StoreLayout";
import { ADMIN_NAV_ITEMS, NAV_ITEMS, STORE_NAV_ITEMS } from "./navigation";
import { AppTopbar } from "./components/AppTopbar";
import { FeaturePlaceholder } from "./components/FeaturePlaceholder";
import { UserMenu } from "./components/UserMenu";
import type { AuthContextValue } from "@/auth";
import type { AuthUser, StoreContextState } from "@/auth";

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

const mockStore: { current: StoreContextState } = {
  current: {
    currentStoreId: null,
    hasStoreContext: false,
    isStoreRequired: false,
    storeError: null,
  },
};

vi.mock("@/auth", async (importActual) => {
  const actual = await importActual<typeof import("@/auth")>();
  return {
    ...actual,
    useAuth: () => mockAuth.current,
    useStoreContext: () => mockStore.current,
  };
});

function setAuth(partial: Partial<AuthContextValue>) {
  mockAuth.current = { ...mockAuth.current, ...partial };
}

function setStore(partial: Partial<StoreContextState>) {
  mockStore.current = { ...mockStore.current, ...partial };
}

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

beforeEach(() => {
  setAuth({
    user: null,
    isAuthenticated: false,
    isLoading: false,
    logout: vi.fn(),
  });
  setStore({
    currentStoreId: null,
    hasStoreContext: false,
    isStoreRequired: false,
    storeError: null,
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

function withRouter(node: ReactNode, path = "/app") {
  return <MemoryRouter initialEntries={[path]}>{node}</MemoryRouter>;
}

function getSidebar() {
  return screen.getByRole("complementary", {
    name: /primary navigation/i,
  });
}

function expectNavLinks(
  items: ReadonlyArray<{ label: string; href: string }>,
) {
  const sidebar = getSidebar();

  for (const item of items) {
    expect(
      within(sidebar).getByRole("link", { name: item.label }),
    ).toHaveAttribute("href", item.href);
  }
}

function expectNoNavLinks(paths: RegExp) {
  const sidebar = getSidebar();

  for (const link of within(sidebar).queryAllByRole("link")) {
    expect(link).not.toHaveAttribute("href", expect.stringMatching(paths));
  }
}

function expectActiveNav(label: string) {
  const sidebar = getSidebar();

  expect(within(sidebar).getByRole("link", { name: label })).toHaveAttribute(
    "aria-current",
    "page",
  );
}

function expectInactiveNav(label: string) {
  const sidebar = getSidebar();

  expect(
    within(sidebar).getByRole("link", { name: label }),
  ).not.toHaveAttribute("aria-current", "page");
}

describe("navigation config", () => {
  it("exposes the expected store routes in order", () => {
    expect(STORE_NAV_ITEMS.map((i) => [i.label, i.href])).toEqual([
      ["Dashboard", "/app/store"],
      ["Products", "/app/store/products"],
      ["Inventory", "/app/store/inventory"],
      ["Orders", "/app/store/orders"],
      ["Users", "/app/store/users"],
      ["Audit", "/app/store/audit"],
      ["Settings", "/app/store/settings"],
    ]);
    expect(STORE_NAV_ITEMS.some((i) => i.href.startsWith("/app/admin"))).toBe(
      false,
    );
    expect(STORE_NAV_ITEMS.map((i) => i.label)).not.toContain("Stores");
    expect(STORE_NAV_ITEMS.map((i) => i.label)).not.toContain("Compliance");
    expect(STORE_NAV_ITEMS.map((i) => i.label)).not.toContain("Operations");
    expect(STORE_NAV_ITEMS.map((i) => i.label)).not.toContain("Billing");
  });

  it("exposes the expected admin routes in order", () => {
    expect(ADMIN_NAV_ITEMS.map((i) => [i.label, i.href])).toEqual([
      ["Dashboard", "/app/admin"],
      ["Stores", "/app/admin/stores"],
      ["Users", "/app/admin/users"],
      ["Products", "/app/admin/products"],
      ["Inventory", "/app/admin/inventory"],
      ["Orders", "/app/admin/orders"],
      ["Audit", "/app/admin/audit"],
      ["Compliance", "/app/admin/compliance"],
      ["Operations", "/app/admin/operations"],
      ["Settings", "/app/admin/settings"],
    ]);
    expect(ADMIN_NAV_ITEMS.some((i) => i.href.startsWith("/app/store"))).toBe(
      false,
    );
    expect(ADMIN_NAV_ITEMS.map((i) => i.label)).not.toContain("Checkout");
    expect(ADMIN_NAV_ITEMS.map((i) => i.label)).not.toContain("Cart");
    expect(ADMIN_NAV_ITEMS.map((i) => i.label)).not.toContain("Marketplace");
  });

  it("keeps NAV_ITEMS as the store-navigation compatibility alias", () => {
    expect(NAV_ITEMS).toBe(STORE_NAV_ITEMS);
  });

  it("only marks the admin and store dashboard routes as exact", () => {
    expect(STORE_NAV_ITEMS.filter((i) => i.exact)).toEqual([
      STORE_NAV_ITEMS[0],
    ]);
    expect(ADMIN_NAV_ITEMS.filter((i) => i.exact)).toEqual([
      ADMIN_NAV_ITEMS[0],
    ]);
  });
});

describe("StoreLayout", () => {
  it("renders the operational shell, store scope, nav, and content", () => {
    setAuth({
      user: makeUser(),
      isAuthenticated: true,
    });
    setStore({
      currentStoreId: "22222222-2222-2222-2222-222222222222",
      hasStoreContext: true,
      isStoreRequired: true,
    });

    render(
      withRouter(
        <StoreLayout>
          <div>main-content-slot</div>
        </StoreLayout>,
        "/app/store/products/sku-1",
      ),
    );

    expect(getSidebar()).toBeInTheDocument();
    expect(screen.getByText("NubeRush")).toBeInTheDocument();
    expect(screen.getAllByText("Store Operations").length).toBeGreaterThan(0);
    expect(screen.getByTestId("store-context-indicator")).toHaveTextContent(
      "Store scope | Store: 22222222-2222-2222-2222-222222222222",
    );

    expectNavLinks(STORE_NAV_ITEMS);
    expectNoNavLinks(/^\/app\/admin/);
    expect(screen.queryByRole("link", { name: "Stores" })).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Compliance" }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("link", { name: "Operations" }),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/checkout/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/cart/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/marketplace/i)).not.toBeInTheDocument();

    expect(
      screen.getByRole("main", { name: /main content/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("main-content-slot")).toBeInTheDocument();
  });

  it("uses an honest fallback when no store id is available", () => {
    setAuth({ user: makeUser(), isAuthenticated: true });
    setStore({
      currentStoreId: null,
      hasStoreContext: false,
      isStoreRequired: true,
    });

    render(
      withRouter(
        <StoreLayout>
          <div>store fallback content</div>
        </StoreLayout>,
      ),
    );

    expect(screen.getByTestId("store-context-indicator")).toHaveTextContent(
      "Store scope | No store selected",
    );
  });
});

describe("AdminLayout", () => {
  it("renders the platform shell without requiring store context", () => {
    setAuth({
      user: makeUser({ role: "admin", store_id: null }),
      isAuthenticated: true,
    });
    setStore({
      currentStoreId: "99999999-9999-9999-9999-999999999999",
      hasStoreContext: true,
      isStoreRequired: false,
    });

    render(
      withRouter(
        <AdminLayout>
          <div>admin-placeholder-slot</div>
        </AdminLayout>,
        "/app/admin/stores/store-1",
      ),
    );

    expect(screen.getAllByText("Platform Admin").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Global scope").length).toBeGreaterThan(0);
    expect(screen.getByTestId("store-context-indicator")).toHaveTextContent(
      "Global scope",
    );
    expect(
      screen.queryByText("Store: 99999999-9999-9999-9999-999999999999"),
    ).not.toBeInTheDocument();
    expectNavLinks(ADMIN_NAV_ITEMS);
    expectNoNavLinks(/^\/app\/store/);
    expect(screen.queryByText("Store Operations")).not.toBeInTheDocument();
    expect(screen.queryByText(/checkout/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/cart/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/marketplace/i)).not.toBeInTheDocument();
    expect(screen.getByText("admin-placeholder-slot")).toBeInTheDocument();
  });
});

describe("navigation active states", () => {
  it.each([
    ["/app/admin", AdminLayout, "Dashboard"],
    ["/app/admin/stores", AdminLayout, "Stores"],
    ["/app/admin/stores/store-1", AdminLayout, "Stores"],
    ["/app/admin/products", AdminLayout, "Products"],
    ["/app/admin/orders", AdminLayout, "Orders"],
    ["/app/admin/compliance", AdminLayout, "Compliance"],
    ["/app/admin/operations", AdminLayout, "Operations"],
    ["/app/store", StoreLayout, "Dashboard"],
    ["/app/store/products/product-1", StoreLayout, "Products"],
    ["/app/store/inventory/variant-1", StoreLayout, "Inventory"],
    ["/app/store/orders/new", StoreLayout, "Orders"],
    ["/app/store/orders/order-1", StoreLayout, "Orders"],
  ] as const)("marks %s with active %s nav", (path, Layout, label) => {
    setAuth({ user: makeUser(), isAuthenticated: true });
    setStore({
      currentStoreId: "22222222-2222-2222-2222-222222222222",
      hasStoreContext: true,
      isStoreRequired: true,
    });

    render(
      withRouter(
        <Layout>
          <div>active-state-slot</div>
        </Layout>,
        path,
      ),
    );

    expectActiveNav(label);
  });

  it.each([
    ["/app/admin/products", AdminLayout, "Products"],
    ["/app/store/products/product-1", StoreLayout, "Products"],
  ] as const)(
    "keeps dashboard exact matching for %s",
    (path, Layout, activeLabel) => {
      setAuth({ user: makeUser(), isAuthenticated: true });
      setStore({
        currentStoreId: "22222222-2222-2222-2222-222222222222",
        hasStoreContext: true,
        isStoreRequired: true,
      });

      render(
        withRouter(
          <Layout>
            <div>dashboard-exact-slot</div>
          </Layout>,
          path,
        ),
      );

      expectActiveNav(activeLabel);
      expectInactiveNav("Dashboard");
    },
  );

  it("does not cross-activate admin and store product navigation", () => {
    setAuth({ user: makeUser({ role: "admin" }), isAuthenticated: true });
    setStore({
      currentStoreId: "22222222-2222-2222-2222-222222222222",
      hasStoreContext: true,
      isStoreRequired: false,
    });

    render(
      withRouter(
        <AdminLayout>
          <div>admin-products-slot</div>
        </AdminLayout>,
        "/app/admin/products",
      ),
    );

    expectActiveNav("Products");
    expect(
      within(getSidebar()).getByRole("link", { name: "Products" }),
    ).toHaveAttribute("href", "/app/admin/products");
    expectNoNavLinks(/^\/app\/store/);
  });
});

describe("FeaturePlaceholder", () => {
  it("renders product-facing placeholder sections without internal milestones", () => {
    render(
      <FeaturePlaceholder
        title="Store Dashboard"
        description="Store operations dashboard"
        status="Planned"
        requiredBackend={["Store dashboard summary endpoint"]}
        nonGoals={["No fake metrics"]}
        futureCapabilities={["Daily order activity"]}
      />,
    );

    expect(screen.getByRole("heading", { name: "Store Dashboard" }))
      .toBeInTheDocument();
    expect(screen.getByText("Planned")).toBeInTheDocument();
    expect(
      screen.getByText("Store dashboard summary endpoint"),
    ).toBeInTheDocument();
    expect(screen.getByText("No fake metrics")).toBeInTheDocument();
    expect(screen.getByText("Daily order activity")).toBeInTheDocument();
    expect(screen.queryByText(/F2\.7/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/F2\.12/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/coming soon/i)).not.toBeInTheDocument();
  });
});

describe("DashboardLayout", () => {
  it("remains a StoreLayout alias for older imports", () => {
    setAuth({ user: makeUser(), isAuthenticated: true });
    setStore({
      currentStoreId: "22222222-2222-2222-2222-222222222222",
      hasStoreContext: true,
      isStoreRequired: true,
    });

    render(
      withRouter(
        <DashboardLayout>
          <div>legacy-dashboard-slot</div>
        </DashboardLayout>,
      ),
    );

    expect(screen.getAllByText("Store Operations").length).toBeGreaterThan(0);
    expect(screen.getByText("legacy-dashboard-slot")).toBeInTheDocument();
  });
});

describe("AppTopbar", () => {
  it("renders the supplied surface and scope labels", () => {
    setAuth({
      user: makeUser({ role: "admin", store_id: null }),
      isAuthenticated: true,
    });

    render(
      withRouter(
        <AppTopbar surfaceLabel="Platform Admin" scopeLabel="Global scope" />,
      ),
    );

    expect(screen.getByText("Platform Admin")).toBeInTheDocument();
    expect(screen.getByTestId("store-context-indicator")).toHaveTextContent(
      "Global scope",
    );
  });
});

describe("UserMenu logout", () => {
  it("renders a logged-in trigger that exposes the user's display name", () => {
    setAuth({
      user: makeUser({ full_name: "Ada Lovelace" }),
      isAuthenticated: true,
    });
    render(withRouter(<UserMenu />));
    const trigger = screen.getByRole("button", {
      name: /open account menu/i,
    });
    expect(trigger).toBeInTheDocument();
    expect(trigger).toHaveTextContent("Ada Lovelace");
  });

  it("renders nothing when user is null", () => {
    setAuth({ user: null, isAuthenticated: false });
    const { container } = render(withRouter(<UserMenu />));
    expect(container.querySelector("button")).toBeNull();
  });
});
