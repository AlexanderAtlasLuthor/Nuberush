// F2.19.5: tests for the real Admin Dashboard page.
//
// Stub `../../hooks` so we drive every query state without TanStack
// Query or the API. The page renders <Link> elements, so we wrap
// the harness in MemoryRouter — the page itself does NOT use
// react-router-dom hooks (no useParams, no useLocation), and does
// NOT use useStoreContext / useAuth (verified by the architecture
// assertion at the bottom).
//
// Coverage:
//   - Loading state surfaced.
//   - Error state + retry calls query.refetch.
//   - Success: six KPI values render verbatim (including zeros).
//   - Success: orders.by_status renders for every locked status.
//   - Success: orders.recent rows render with id/status/total/created_at.
//   - Success: recent_audit rows render with action + summary.
//   - Empty: orders.recent empty → empty state.
//   - Empty: recent_audit empty → empty state.
//   - Operations CTA links to /app/admin/operations.
//   - Drill-down links to stores/inventory/orders/audit.
//   - No admin-operations hook is invoked.
//   - No auth/store-context provider required.
//   - Page uses useAdminDashboardQuery (not getAdminDashboard).

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import AdminDashboardPage from "../AdminDashboardPage";
import * as adminDashboardHooks from "../../hooks";
import type { AdminDashboardSummary } from "../../types";

vi.mock("../../hooks", () => ({
  useAdminDashboardQuery: vi.fn(),
  adminDashboardKeys: { all: ["admin-dashboard"] as const },
}));

// Replace the earnings widget with a tiny placeholder ONLY in these
// dashboard tests. The widget calls useQuery internally and these
// existing tests don't wrap renders in a QueryClientProvider, so
// without this replacement they would crash on mount. The widget's
// real behaviour is covered by its own dedicated test file in
// features/admin-earnings.
vi.mock(
  "@/features/admin-earnings/components/AdminEarningsWidget",
  () => ({
    AdminEarningsWidget: () => (
      <div data-testid="admin-earnings-widget-stub" />
    ),
  }),
);

const STORE_ID = "11111111-1111-1111-1111-111111111111";
const ORDER_ID_1 = "22222222-2222-2222-2222-222222222222";
const ORDER_ID_2 = "33333333-3333-3333-3333-333333333333";
const AUDIT_ID_1 = "44444444-4444-4444-4444-444444444444";
const AUDIT_ID_2 = "55555555-5555-5555-5555-555555555555";

function asQueryResult(
  partial: Partial<UseQueryResult<AdminDashboardSummary>>,
): UseQueryResult<AdminDashboardSummary> {
  return {
    refetch: vi.fn(),
    isPending: false,
    isLoading: false,
    isError: false,
    isSuccess: false,
    isFetching: false,
    data: undefined,
    error: null,
    ...partial,
  } as unknown as UseQueryResult<AdminDashboardSummary>;
}

function makeSummary(
  overrides: Partial<AdminDashboardSummary> = {},
): AdminDashboardSummary {
  return {
    stores: { total: 5, active: 4, inactive: 1 },
    users: { total: 12, active: 10 },
    inventory: { low_stock_count: 7 },
    orders: {
      open_count: 9,
      by_status: {
        pending: 3,
        accepted: 2,
        preparing: 1,
        ready: 1,
        out_for_delivery: 2,
        delivered: 10,
        canceled: 1,
        returned: 0,
      },
      recent: [
        {
          id: ORDER_ID_1,
          store_id: STORE_ID,
          customer_user_id: null,
          idempotency_key: "k-1",
          status: "pending",
          subtotal_amount: "19.99",
          tax_amount: "0.00",
          total_amount: "19.99",
          age_verified_at: null,
          age_verified_by_user_id: null,
          accepted_at: null,
          canceled_at: null,
          delivered_at: null,
          returned_at: null,
          cancel_reason: null,
          notes: null,
          created_at: "2026-05-12T08:30:00Z",
          updated_at: "2026-05-12T08:30:00Z",
          items: [],
        },
        {
          id: ORDER_ID_2,
          store_id: STORE_ID,
          customer_user_id: null,
          idempotency_key: "k-2",
          status: "accepted",
          subtotal_amount: "42.00",
          tax_amount: "0.00",
          total_amount: "42.00",
          age_verified_at: null,
          age_verified_by_user_id: null,
          accepted_at: null,
          canceled_at: null,
          delivered_at: null,
          returned_at: null,
          cancel_reason: null,
          notes: null,
          created_at: "2026-05-12T07:30:00Z",
          updated_at: "2026-05-12T07:30:00Z",
          items: [],
        },
      ],
    },
    compliance: { blocked_count: 2 },
    products: { pending_approvals_count: 3 },
    recent_audit: [
      {
        id: AUDIT_ID_1,
        source: "inventory",
        store_id: STORE_ID,
        actor_id: null,
        action: "receipt",
        entity_type: "inventory_item",
        entity_id: "item-1",
        summary: "Inventory receipt: +10 units (after 10)",
        metadata: { quantity_delta: 10 },
        created_at: "2026-05-12T08:00:00Z",
      },
      {
        id: AUDIT_ID_2,
        source: "order",
        store_id: STORE_ID,
        actor_id: null,
        action: "order_canceled",
        entity_type: "order",
        entity_id: ORDER_ID_2,
        summary: "Order order_canceled: pending → canceled",
        metadata: {},
        created_at: "2026-05-12T07:00:00Z",
      },
    ],
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter>
      <AdminDashboardPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Loading state
// --------------------------------------------------------------------- //

describe("AdminDashboardPage — loading state", () => {
  it("renders a loading message while the query is pending", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isPending: true, isLoading: true }),
    );

    renderPage();

    expect(
      screen.getByTestId("admin-dashboard-loading"),
    ).toBeInTheDocument();
    // Success-state sections must NOT render during loading.
    expect(
      screen.queryByTestId("admin-dashboard-kpi-grid"),
    ).not.toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Error state
// --------------------------------------------------------------------- //

describe("AdminDashboardPage — error state", () => {
  it("renders the error alert with a retry button", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({
        isError: true,
        error: new Error("network blew up"),
      }),
    );

    renderPage();

    expect(
      screen.getByTestId("admin-dashboard-error"),
    ).toBeInTheDocument();
    expect(screen.getByText(/network blew up/)).toBeInTheDocument();
    expect(
      screen.getByTestId("admin-dashboard-retry"),
    ).toBeInTheDocument();
  });

  it("retry button calls query.refetch", () => {
    const refetch = vi.fn();
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({
        isError: true,
        error: new Error("oops"),
        refetch,
      }),
    );

    renderPage();

    fireEvent.click(screen.getByTestId("admin-dashboard-retry"));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("falls back to a generic error message when error has no message", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({
        isError: true,
        error: {} as unknown as Error,
      }),
    );

    renderPage();

    expect(
      screen.getByTestId("admin-dashboard-error"),
    ).toBeInTheDocument();
    expect(screen.getByText("Unable to load dashboard.")).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Success: six KPI cards
// --------------------------------------------------------------------- //

describe("AdminDashboardPage — KPI cards (backend values verbatim)", () => {
  it("renders all seven KPI values from backend summary", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );

    renderPage();

    const grid = screen.getByTestId("admin-dashboard-kpi-grid");
    expect(within(grid).getByTestId("kpi-stores-total")).toHaveTextContent(
      "5",
    );
    expect(
      within(grid).getByTestId("kpi-stores-active"),
    ).toHaveTextContent("4");
    expect(within(grid).getByTestId("kpi-users-total")).toHaveTextContent(
      "12",
    );
    expect(
      within(grid).getByTestId("kpi-inventory-low-stock"),
    ).toHaveTextContent("7");
    expect(within(grid).getByTestId("kpi-orders-open")).toHaveTextContent(
      "9",
    );
    expect(
      within(grid).getByTestId("kpi-compliance-blocked"),
    ).toHaveTextContent("2");
    expect(
      within(grid).getByTestId("kpi-products-pending-approvals"),
    ).toHaveTextContent("3");
  });

  it("renders zeros as `0` (not hidden, not empty)", () => {
    const summary = makeSummary({
      stores: { total: 0, active: 0, inactive: 0 },
      users: { total: 0, active: 0 },
      inventory: { low_stock_count: 0 },
      orders: {
        open_count: 0,
        by_status: {
          pending: 0,
          accepted: 0,
          preparing: 0,
          ready: 0,
          out_for_delivery: 0,
          delivered: 0,
          canceled: 0,
          returned: 0,
        },
        recent: [],
      },
      compliance: { blocked_count: 0 },
      products: { pending_approvals_count: 0 },
      recent_audit: [],
    });
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: summary }),
    );

    renderPage();

    const grid = screen.getByTestId("admin-dashboard-kpi-grid");
    expect(within(grid).getByTestId("kpi-stores-total")).toHaveTextContent(
      "0",
    );
    expect(within(grid).getByTestId("kpi-orders-open")).toHaveTextContent(
      "0",
    );
    expect(
      within(grid).getByTestId("kpi-compliance-blocked"),
    ).toHaveTextContent("0");
    expect(
      within(grid).getByTestId("kpi-products-pending-approvals"),
    ).toHaveTextContent("0");
    // No "—" or "N/A" or any fake substitute.
    expect(within(grid).queryByText("—")).not.toBeInTheDocument();
    expect(within(grid).queryByText("N/A")).not.toBeInTheDocument();
  });

  it("KPI cards link to the right drill-down routes", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );

    renderPage();

    const grid = screen.getByTestId("admin-dashboard-kpi-grid");
    const storesTotal = within(grid)
      .getByTestId("kpi-stores-total")
      .closest("a");
    const storesActive = within(grid)
      .getByTestId("kpi-stores-active")
      .closest("a");
    const usersTotal = within(grid)
      .getByTestId("kpi-users-total")
      .closest("a");
    const inventoryLowStock = within(grid)
      .getByTestId("kpi-inventory-low-stock")
      .closest("a");
    const ordersOpen = within(grid)
      .getByTestId("kpi-orders-open")
      .closest("a");
    const complianceBlocked = within(grid)
      .getByTestId("kpi-compliance-blocked")
      .closest("a");
    const pendingApprovals = within(grid)
      .getByTestId("kpi-products-pending-approvals")
      .closest("a");

    expect(storesTotal).toHaveAttribute("href", "/app/admin/stores");
    expect(storesActive).toHaveAttribute("href", "/app/admin/stores");
    expect(usersTotal).toHaveAttribute("href", "/app/admin/users");
    expect(inventoryLowStock).toHaveAttribute(
      "href",
      "/app/admin/inventory",
    );
    expect(ordersOpen).toHaveAttribute("href", "/app/admin/orders");
    expect(complianceBlocked).toHaveAttribute("href", "/app/admin/audit");
    // The pending-approvals tile deep-links into the admin products
    // list with the approval filter pre-applied.
    expect(pendingApprovals).toHaveAttribute(
      "href",
      "/app/admin/products?approval_status=pending",
    );
  });
});

// --------------------------------------------------------------------- //
// Success: orders by status
// --------------------------------------------------------------------- //

describe("AdminDashboardPage — orders by status panel", () => {
  it("renders the full status histogram from backend by_status", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );

    renderPage();

    const panel = screen.getByTestId("admin-dashboard-orders-by-status");
    expect(within(panel).getByTestId("status-pending")).toHaveTextContent(
      "3",
    );
    expect(within(panel).getByTestId("status-accepted")).toHaveTextContent(
      "2",
    );
    expect(
      within(panel).getByTestId("status-preparing"),
    ).toHaveTextContent("1");
    expect(within(panel).getByTestId("status-ready")).toHaveTextContent(
      "1",
    );
    expect(
      within(panel).getByTestId("status-out_for_delivery"),
    ).toHaveTextContent("2");
    expect(
      within(panel).getByTestId("status-delivered"),
    ).toHaveTextContent("10");
    expect(within(panel).getByTestId("status-canceled")).toHaveTextContent(
      "1",
    );
    expect(within(panel).getByTestId("status-returned")).toHaveTextContent(
      "0",
    );
  });

  it("renders every status even when all counts are zero", () => {
    const summary = makeSummary({
      orders: {
        open_count: 0,
        by_status: {
          pending: 0,
          accepted: 0,
          preparing: 0,
          ready: 0,
          out_for_delivery: 0,
          delivered: 0,
          canceled: 0,
          returned: 0,
        },
        recent: [],
      },
    });
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: summary }),
    );

    renderPage();

    const panel = screen.getByTestId("admin-dashboard-orders-by-status");
    for (const status of [
      "pending",
      "accepted",
      "preparing",
      "ready",
      "out_for_delivery",
      "delivered",
      "canceled",
      "returned",
    ]) {
      expect(within(panel).getByTestId(`status-${status}`)).toBeInTheDocument();
    }
  });
});

// --------------------------------------------------------------------- //
// Success: recent orders + recent activity
// --------------------------------------------------------------------- //

describe("AdminDashboardPage — recent orders panel", () => {
  it("renders the backend recent orders tail", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );

    renderPage();

    const panel = screen.getByTestId("admin-dashboard-recent-orders");
    expect(within(panel).getByTestId(`recent-order-${ORDER_ID_1}`)).toBeInTheDocument();
    expect(within(panel).getByTestId(`recent-order-${ORDER_ID_2}`)).toBeInTheDocument();
    expect(
      within(panel).getByTestId(`recent-order-status-${ORDER_ID_1}`),
    ).toHaveTextContent("pending");
    expect(
      within(panel).getByTestId(`recent-order-total-${ORDER_ID_1}`),
    ).toHaveTextContent("19.99");
    expect(within(panel).queryByTestId("recent-orders-empty")).not.toBeInTheDocument();
  });

  it("renders an empty state when recent is empty", () => {
    const summary = makeSummary({
      orders: {
        open_count: 0,
        by_status: {
          pending: 0,
          accepted: 0,
          preparing: 0,
          ready: 0,
          out_for_delivery: 0,
          delivered: 0,
          canceled: 0,
          returned: 0,
        },
        recent: [],
      },
    });
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: summary }),
    );

    renderPage();

    const panel = screen.getByTestId("admin-dashboard-recent-orders");
    expect(
      within(panel).getByTestId("recent-orders-empty"),
    ).toBeInTheDocument();
    expect(
      within(panel).queryByTestId("recent-orders-list"),
    ).not.toBeInTheDocument();
  });
});

describe("AdminDashboardPage — recent activity panel", () => {
  it("renders the backend recent_audit tail", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );

    renderPage();

    const panel = screen.getByTestId("admin-dashboard-recent-activity");
    expect(
      within(panel).getByTestId(`recent-activity-${AUDIT_ID_1}`),
    ).toBeInTheDocument();
    expect(
      within(panel).getByTestId(`recent-activity-action-${AUDIT_ID_1}`),
    ).toHaveTextContent("receipt");
    expect(
      within(panel).getByTestId(`recent-activity-summary-${AUDIT_ID_2}`),
    ).toHaveTextContent("Order order_canceled: pending → canceled");
  });

  it("renders an empty state when recent_audit is empty", () => {
    const summary = makeSummary({ recent_audit: [] });
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: summary }),
    );

    renderPage();

    const panel = screen.getByTestId("admin-dashboard-recent-activity");
    expect(
      within(panel).getByTestId("recent-activity-empty"),
    ).toBeInTheDocument();
    expect(
      within(panel).queryByTestId("recent-activity-list"),
    ).not.toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Operations CTA + drill-down link surface
// --------------------------------------------------------------------- //

describe("AdminDashboardPage — operations CTA + drill-downs", () => {
  it("renders an Operations CTA linking to /app/admin/operations", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );

    renderPage();

    const cta = screen.getByTestId("admin-dashboard-operations-cta");
    const link = within(cta).getByTestId("admin-dashboard-operations-link");
    expect(link).toHaveAttribute("href", "/app/admin/operations");
  });

  it("renders 'View all' links for recent orders and recent activity", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );

    renderPage();

    expect(
      screen.getByTestId("recent-orders-view-all"),
    ).toHaveAttribute("href", "/app/admin/orders");
    expect(
      screen.getByTestId("recent-activity-view-all"),
    ).toHaveAttribute("href", "/app/admin/audit");
  });
});

// --------------------------------------------------------------------- //
// Phase C — bento layout + fake/demo guard
// --------------------------------------------------------------------- //

describe("AdminDashboardPage — bento layout (Phase C)", () => {
  it("promotes Open orders to the hero tile and links to /app/admin/orders", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );

    renderPage();

    const grid = screen.getByTestId("admin-dashboard-kpi-grid");
    const heroLink = within(grid)
      .getByTestId("kpi-orders-open")
      .closest("a");

    // The hero tile still wraps a real Link with the same drill-down
    // route. The bento promotion only changes visual weight, not data
    // or routing.
    expect(heroLink).toHaveAttribute("href", "/app/admin/orders");
    expect(within(grid).getByTestId("kpi-orders-open")).toHaveTextContent(
      "9",
    );
  });

  it("orders-by-status total is the sum of the backend densified counts", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );

    renderPage();

    const total = screen.getByTestId(
      "admin-dashboard-orders-by-status-total",
    );
    // 3 + 2 + 1 + 1 + 2 + 10 + 1 + 0 = 20 — straight from `makeSummary`.
    expect(total).toHaveTextContent("20");
  });

  it("orders-by-status total is 0 when every count is 0 (no fake denominator)", () => {
    const summary = makeSummary({
      orders: {
        open_count: 0,
        by_status: {
          pending: 0,
          accepted: 0,
          preparing: 0,
          ready: 0,
          out_for_delivery: 0,
          delivered: 0,
          canceled: 0,
          returned: 0,
        },
        recent: [],
      },
    });
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: summary }),
    );

    renderPage();

    expect(
      screen.getByTestId("admin-dashboard-orders-by-status-total"),
    ).toHaveTextContent("0");
  });

  it("recent orders rows show the real status text inside the status pill", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );

    renderPage();

    // The status pill is the same element carrying the existing
    // `recent-order-status-{id}` test id — the visual upgrade only
    // wraps the text in a colored span without touching the value.
    expect(
      screen.getByTestId(`recent-order-status-${ORDER_ID_1}`),
    ).toHaveTextContent("pending");
    expect(
      screen.getByTestId(`recent-order-status-${ORDER_ID_2}`),
    ).toHaveTextContent("accepted");
  });
});

describe("AdminDashboardPage — fake/demo guard (Phase C)", () => {
  // Strings the design-system ZIP ships as demo content. None of
  // these may leak into the production dashboard, ever.
  const ZIP_DEMO_STRINGS = [
    "Wynwood",
    "Brickell",
    "Doral",
    "Hookah House",
    "Vape Co",
    "Alex Fuenmayor",
    "alex@",
    "marketplace",
    "checkout",
    "driver",
    "payments",
    "signup",
  ];

  // Fake metric vocabulary that bento dashboards often invent.
  // The admin dashboard contract only exposes counts; anything
  // here would be an aggregation we are not allowed to render.
  const FAKE_METRIC_STRINGS = [
    "GMV",
    "AOV",
    "revenue",
    "conversion",
    "sparkline",
    "trend delta",
    "+12%",
    "-8%",
  ];

  it("does not render any ZIP demo identity strings", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );

    renderPage();

    const page = screen.getByTestId("admin-dashboard-page");
    for (const fake of ZIP_DEMO_STRINGS) {
      const literal = fake.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      expect(
        within(page).queryByText(new RegExp(literal, "i")),
      ).not.toBeInTheDocument();
    }
  });

  it("does not render any fake-metric vocabulary", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );

    renderPage();

    const page = screen.getByTestId("admin-dashboard-page");
    for (const fake of FAKE_METRIC_STRINGS) {
      // Escape regex metacharacters in the fake-string literals so
      // entries like "+12%" / "-8%" are treated as literal text.
      const literal = fake.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      expect(
        within(page).queryByText(new RegExp(literal, "i")),
      ).not.toBeInTheDocument();
    }
  });

  it("does not render fake trend delta percentage chips on KPI cards", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );

    renderPage();

    const grid = screen.getByTestId("admin-dashboard-kpi-grid");
    // No chip-style "+N%" or "−N%" text inside any KPI card. The wire
    // contract has no historical deltas, so the bento upgrade cannot
    // ship trend chips.
    expect(within(grid).queryByText(/^[+−-]?\d+(\.\d+)?%$/)).not.toBeInTheDocument();
    expect(within(grid).queryByText(/vs\.? (yesterday|last week|prior)/i))
      .not.toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Architecture guards
// --------------------------------------------------------------------- //

describe("AdminDashboardPage — architecture", () => {
  it("calls useAdminDashboardQuery exactly once per render", () => {
    vi.mocked(adminDashboardHooks.useAdminDashboardQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );

    renderPage();

    expect(
      adminDashboardHooks.useAdminDashboardQuery,
    ).toHaveBeenCalledTimes(1);
  });

  it("does NOT import or reference admin-operations hooks / API / fetch / auth / store context", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");

    // Mirror the AdminAuditPage architecture-test pattern: use the
    // CJS `__dirname` (vitest provides it) and strip comments before
    // grepping so the page's own docstring negations don't trigger
    // false positives.
    const pagePath = path.resolve(__dirname, "..", "AdminDashboardPage.tsx");
    const source = fs.readFileSync(pagePath, "utf-8");
    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/from\s+["']@\/features\/admin-operations/);
    expect(code).not.toMatch(/\buseAdminOperationsAlertsQuery\b/);
    expect(code).not.toMatch(/\bgetAdminOperationsAlerts\b/);
    expect(code).not.toMatch(/from\s+["']@\/auth/);
    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\buseStoreContext\b/);
    expect(code).not.toMatch(/\bfetch\(/);
    expect(code).not.toMatch(/\baxios\b/);
    expect(code).not.toMatch(/\bgetAdminDashboard\b/);
    expect(code).not.toMatch(/\bapiRequest\b/);
    expect(code).not.toMatch(/\buseMutation\b/);
    expect(code).not.toMatch(/\buseQueryClient\b/);
    expect(code).not.toMatch(/\bsetQueryData\b/);
  });
});
