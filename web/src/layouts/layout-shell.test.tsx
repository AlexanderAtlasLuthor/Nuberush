import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";

// F2.22.5.E: stub the Realtime invalidation bridge as a sentinel div
// so:
//   - the bridge does not call useQueryClient() (these tests do not
//     mount a QueryClientProvider; the production bridge expects one);
//   - we can assert mount/no-mount per layout (`getByTestId` /
//     `queryByTestId` against `realtime-bridge`).
// The bridge's real behavior is unit-tested in
// `web/src/features/realtime/__tests__/RealtimeInvalidationBridge.test.tsx`.
vi.mock("@/features/realtime", () => ({
  RealtimeInvalidationBridge: () => (
    <div data-testid="realtime-bridge" hidden />
  ),
}));

import { AdminLayout } from "./AdminLayout";
import { AppShell } from "./AppShell";
import { DashboardLayout } from "./DashboardLayout";
import { StoreLayout } from "./StoreLayout";
import { PublicLayout } from "./PublicLayout";
import { ADMIN_NAV_ITEMS, NAV_ITEMS, STORE_NAV_ITEMS } from "./navigation";
import { AppTopbar } from "./components/AppTopbar";
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
  // The workspace switcher is intentional cross-surface navigation — Admin
  // layouts can legitimately link to /app/store from inside their sidebar.
  // The "no cross-pollination" rule only applies to the Main/Platform nav.
  const switcher = within(sidebar).queryByTestId("workspace-switcher");

  for (const link of within(sidebar).queryAllByRole("link")) {
    if (switcher?.contains(link)) continue;
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
      ["Earnings", "/app/store/earnings"],
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
      ["Applications", "/app/admin/applications"],
      ["Users", "/app/admin/users"],
      ["Products", "/app/admin/products"],
      ["Inventory", "/app/admin/inventory"],
      ["Orders", "/app/admin/orders"],
      ["Earnings", "/app/admin/earnings"],
      ["Audit", "/app/admin/audit"],
      ["Compliance", "/app/admin/compliance"],
      ["Regulatory", "/app/admin/regulatory"],
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

// F2.22.5.E: realtime invalidation bridge mounts inside the
// authenticated AppShell (via AdminLayout / StoreLayout) and is
// absent from PublicLayout. The bridge itself is stubbed at the
// top of this file as a sentinel `data-testid="realtime-bridge"`
// div; its real (hook-firing) behavior is covered by the unit
// test under `web/src/features/realtime/__tests__/`.
describe("RealtimeInvalidationBridge mounting", () => {
  it("mounts inside AdminLayout (authenticated admin shell)", () => {
    render(
      <MemoryRouter initialEntries={["/app/admin"]}>
        <AdminLayout>
          <div>admin content</div>
        </AdminLayout>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("realtime-bridge")).toBeInTheDocument();
  });

  it("mounts inside StoreLayout (authenticated store shell)", () => {
    render(
      <MemoryRouter initialEntries={["/app/store"]}>
        <StoreLayout>
          <div>store content</div>
        </StoreLayout>
      </MemoryRouter>,
    );
    expect(screen.getByTestId("realtime-bridge")).toBeInTheDocument();
  });

  it("is NOT mounted inside PublicLayout (no auth, no AppShell)", () => {
    render(
      <MemoryRouter initialEntries={["/"]}>
        <PublicLayout>
          <div>public marketing content</div>
        </PublicLayout>
      </MemoryRouter>,
    );
    expect(screen.queryByTestId("realtime-bridge")).not.toBeInTheDocument();
  });

  it("mounts exactly once even when nested children re-render", () => {
    render(
      <MemoryRouter initialEntries={["/app/admin"]}>
        <AdminLayout>
          <div>page A</div>
          <div>page B</div>
        </AdminLayout>
      </MemoryRouter>,
    );
    expect(screen.getAllByTestId("realtime-bridge")).toHaveLength(1);
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

    // The modern topbar exposes the surface label twice: once as the mobile
    // compact title and once as the leading breadcrumb crumb on desktop.
    // CSS visibility classes don't influence the accessibility tree under
    // JSDOM, so we accept either.
    expect(screen.getAllByText("Platform Admin").length).toBeGreaterThan(0);
    expect(screen.getByTestId("store-context-indicator")).toHaveTextContent(
      "Global scope",
    );
  });

  it("derives the breadcrumb tail from the active route in a real shell", () => {
    setAuth({ user: makeUser(), isAuthenticated: true });
    setStore({
      currentStoreId: "22222222-2222-2222-2222-222222222222",
      hasStoreContext: true,
      isStoreRequired: true,
    });

    render(
      withRouter(
        <StoreLayout>
          <div>products-slot</div>
        </StoreLayout>,
        "/app/store/products/sku-1",
      ),
    );

    const breadcrumb = screen.getByRole("navigation", { name: /breadcrumb/i });
    expect(within(breadcrumb).getByText("Store Operations")).toBeInTheDocument();
    expect(within(breadcrumb).getByText("Products")).toBeInTheDocument();
  });

  it("keeps search and notifications as inert placeholders — no fake endpoints", () => {
    setAuth({ user: makeUser(), isAuthenticated: true });
    setStore({
      currentStoreId: "22222222-2222-2222-2222-222222222222",
      hasStoreContext: true,
      isStoreRequired: true,
    });

    render(
      withRouter(
        <StoreLayout>
          <div>slot</div>
        </StoreLayout>,
      ),
    );

    expect(
      screen.getByRole("button", { name: /^notifications$/i }),
    ).toBeDisabled();
    expect(screen.getByRole("button", { name: /^search$/i })).toBeDisabled();
  });
});

describe("mobile sidebar drawer", () => {
  beforeEach(() => {
    setAuth({ user: makeUser(), isAuthenticated: true });
    setStore({
      currentStoreId: "22222222-2222-2222-2222-222222222222",
      hasStoreContext: true,
      isStoreRequired: true,
    });
  });

  it("renders the hamburger trigger from the topbar", () => {
    render(
      withRouter(
        <StoreLayout>
          <div>main-content-slot</div>
        </StoreLayout>,
      ),
    );

    expect(
      screen.getByRole("button", { name: /open navigation menu/i }),
    ).toBeInTheDocument();
    expect(screen.queryByTestId("mobile-sidebar")).not.toBeInTheDocument();
  });

  it("opens the drawer when the hamburger is clicked and surfaces real routes", () => {
    render(
      withRouter(
        <StoreLayout>
          <div>main-content-slot</div>
        </StoreLayout>,
      ),
    );

    fireEvent.click(
      screen.getByRole("button", { name: /open navigation menu/i }),
    );

    const drawer = screen.getByTestId("mobile-sidebar");
    expect(drawer).toBeInTheDocument();

    // Real hrefs are present inside the drawer — no fake nav from the ZIP.
    for (const item of STORE_NAV_ITEMS) {
      expect(
        within(drawer).getByRole("link", { name: item.label }),
      ).toHaveAttribute("href", item.href);
    }
    // No drift from the ZIP demo data.
    expect(within(drawer).queryByText(/wynwood/i)).not.toBeInTheDocument();
    expect(within(drawer).queryByText(/marketplace/i)).not.toBeInTheDocument();
    expect(within(drawer).queryByText(/checkout/i)).not.toBeInTheDocument();
  });

  it("closes the drawer when a nav link is activated", () => {
    render(
      withRouter(
        <StoreLayout>
          <div>main-content-slot</div>
        </StoreLayout>,
      ),
    );

    fireEvent.click(
      screen.getByRole("button", { name: /open navigation menu/i }),
    );
    const drawer = screen.getByTestId("mobile-sidebar");
    fireEvent.click(within(drawer).getByRole("link", { name: "Products" }));

    expect(screen.queryByTestId("mobile-sidebar")).not.toBeInTheDocument();
  });

  it("closes the drawer when the backdrop is tapped", () => {
    render(
      withRouter(
        <StoreLayout>
          <div>main-content-slot</div>
        </StoreLayout>,
      ),
    );

    fireEvent.click(
      screen.getByRole("button", { name: /open navigation menu/i }),
    );
    expect(screen.getByTestId("mobile-sidebar")).toBeInTheDocument();

    fireEvent.click(
      screen.getByRole("button", { name: /close navigation menu/i }),
    );
    expect(screen.queryByTestId("mobile-sidebar")).not.toBeInTheDocument();
  });
});

describe("AppShell composition", () => {
  it("renders sidebar, topbar and main content regardless of layout wrapper", () => {
    setAuth({ user: makeUser(), isAuthenticated: true });

    render(
      withRouter(
        <AppShell
          surfaceLabel="Test Surface"
          scopeLabel="Test scope"
          navItems={STORE_NAV_ITEMS}
        >
          <div>raw-shell-slot</div>
        </AppShell>,
      ),
    );

    expect(getSidebar()).toBeInTheDocument();
    // The topbar exposes itself through its aria-label, regardless of whether
    // the host page nests <header> inside a sectioning element.
    expect(screen.getByLabelText("Topbar")).toBeInTheDocument();
    expect(
      screen.getByRole("main", { name: /main content/i }),
    ).toBeInTheDocument();
    expect(screen.getByText("raw-shell-slot")).toBeInTheDocument();
    expect(screen.getByTestId("sidebar-surface-scope")).toHaveTextContent(
      "Test Surface",
    );
  });
});

describe("workspace switcher", () => {
  const FAKE_ZIP_STRINGS = [
    "Wynwood",
    "Brickell",
    "Doral",
    "Hookah House",
    "Vape Co",
    "Fuenmayor",
    "alex@",
    "marketplace",
    "checkout",
    "driver",
    "payments",
    "signup",
  ];

  beforeEach(() => {
    setAuth({
      user: makeUser({ role: "admin", store_id: null }),
      isAuthenticated: true,
    });
    setStore({
      currentStoreId: "22222222-2222-2222-2222-222222222222",
      hasStoreContext: true,
      isStoreRequired: false,
    });
  });

  it("AdminLayout suppresses the workspace switcher entirely", () => {
    render(
      withRouter(
        <AdminLayout>
          <div>admin-slot</div>
        </AdminLayout>,
        "/app/admin",
      ),
    );

    const sidebar = getSidebar();
    expect(
      within(sidebar).queryByTestId("workspace-switcher"),
    ).not.toBeInTheDocument();
    // No cross-surface jump link should appear anywhere in the admin sidebar.
    for (const link of within(sidebar).queryAllByRole("link")) {
      expect(link).not.toHaveAttribute(
        "href",
        expect.stringMatching(/^\/app\/store/),
      );
    }
  });

  it("AdminLayout omits the switcher regardless of the current pathname", () => {
    render(
      withRouter(
        <AdminLayout>
          <div>nested-slot</div>
        </AdminLayout>,
        "/app/admin/stores/store-1",
      ),
    );

    expect(
      within(getSidebar()).queryByTestId("workspace-switcher"),
    ).not.toBeInTheDocument();
  });

  it("StoreLayout exposes only the Store workspace — never Admin", () => {
    setAuth({
      user: makeUser({ role: "manager" }),
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
          <div>store-slot</div>
        </StoreLayout>,
        "/app/store",
      ),
    );

    const sidebar = getSidebar();
    const switcher = within(sidebar).getByTestId("workspace-switcher");
    const store = within(switcher).getByRole("link", { name: "Store" });

    expect(store).toHaveAttribute("href", "/app/store");
    expect(store).toHaveAttribute("aria-current", "page");

    // No Admin entry inside the switcher, in any form.
    expect(
      within(switcher).queryByRole("link", { name: "Admin" }),
    ).not.toBeInTheDocument();
    expect(within(switcher).queryByText(/admin/i)).not.toBeInTheDocument();
    expect(within(switcher).queryByText(/platform/i)).not.toBeInTheDocument();
    expect(within(switcher).queryByText(/global/i)).not.toBeInTheDocument();

    // No /app/admin link anywhere inside the Store sidebar — switcher or otherwise.
    for (const link of within(sidebar).queryAllByRole("link")) {
      expect(link).not.toHaveAttribute("href", expect.stringMatching(/^\/app\/admin/));
    }
  });

  it("Admin mobile drawer also omits the workspace switcher", () => {
    render(
      withRouter(
        <AdminLayout>
          <div>slot</div>
        </AdminLayout>,
      ),
    );

    fireEvent.click(
      screen.getByRole("button", { name: /open navigation menu/i }),
    );
    const drawer = screen.getByTestId("mobile-sidebar");

    expect(
      within(drawer).queryByTestId("workspace-switcher"),
    ).not.toBeInTheDocument();
    for (const link of within(drawer).queryAllByRole("link")) {
      expect(link).not.toHaveAttribute(
        "href",
        expect.stringMatching(/^\/app\/store/),
      );
    }
  });

  it("Store mobile drawer never exposes the Admin workspace", () => {
    setAuth({
      user: makeUser({ role: "manager" }),
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
          <div>slot</div>
        </StoreLayout>,
      ),
    );

    fireEvent.click(
      screen.getByRole("button", { name: /open navigation menu/i }),
    );
    const drawer = screen.getByTestId("mobile-sidebar");
    const switcher = within(drawer).getByTestId("workspace-switcher");

    expect(
      within(switcher).queryByRole("link", { name: "Admin" }),
    ).not.toBeInTheDocument();
    expect(
      within(switcher).getByRole("link", { name: "Store" }),
    ).toHaveAttribute("href", "/app/store");

    // Also defensively assert no /app/admin link anywhere in the drawer.
    for (const link of within(drawer).queryAllByRole("link")) {
      expect(link).not.toHaveAttribute(
        "href",
        expect.stringMatching(/^\/app\/admin/),
      );
    }
  });

  it("closes the mobile drawer when a sidebar nav link is activated", () => {
    render(
      withRouter(
        <AdminLayout>
          <div>slot</div>
        </AdminLayout>,
      ),
    );

    fireEvent.click(
      screen.getByRole("button", { name: /open navigation menu/i }),
    );
    const drawer = screen.getByTestId("mobile-sidebar");
    fireEvent.click(within(drawer).getByRole("link", { name: "Stores" }));

    expect(screen.queryByTestId("mobile-sidebar")).not.toBeInTheDocument();
  });

  it("AdminLayout sidebar never surfaces fake/demo workspace identity from the design system ZIP", () => {
    render(
      withRouter(
        <AdminLayout>
          <div>slot</div>
        </AdminLayout>,
      ),
    );
    const sidebar = getSidebar();

    for (const fake of FAKE_ZIP_STRINGS) {
      expect(
        within(sidebar).queryByText(new RegExp(fake, "i")),
      ).not.toBeInTheDocument();
    }
  });

  it("StoreLayout sidebar contains no fake/demo workspace strings", () => {
    setAuth({
      user: makeUser({ role: "manager" }),
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
          <div>slot</div>
        </StoreLayout>,
      ),
    );
    const sidebar = getSidebar();

    for (const fake of FAKE_ZIP_STRINGS) {
      expect(
        within(sidebar).queryByText(new RegExp(fake, "i")),
      ).not.toBeInTheDocument();
    }
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
