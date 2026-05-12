import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import * as authModule from "@/auth";
import type { StoreContextState } from "@/auth";
import * as auditHooks from "@/features/audit/hooks";
import type { StoreInventoryLogEntry } from "@/features/audit/types";
import * as inventoryHooks from "@/features/inventory/hooks";
import type {
  InventoryItem,
  InventoryListResponse,
} from "@/features/inventory/types";
import * as ordersHooks from "@/features/orders/hooks";
import type {
  OrderItemRead,
  OrderRead,
  OrdersListResponse,
} from "@/features/orders/types";
import * as productsHooks from "@/features/products/hooks";
import type { Product } from "@/features/products/types";

import DashboardHomePage from "../DashboardHomePage";

vi.mock("@/auth", async () => {
  const actual = await vi.importActual<typeof import("@/auth")>("@/auth");
  return {
    ...actual,
    useStoreContext: vi.fn(),
  };
});

vi.mock("@/features/inventory/hooks", () => ({
  useInventoryList: vi.fn(),
}));

vi.mock("@/features/orders/hooks", () => ({
  useOrdersList: vi.fn(),
}));

vi.mock("@/features/products/hooks", () => ({
  useProductsQuery: vi.fn(),
}));

vi.mock("@/features/audit/hooks", () => ({
  useStoreInventoryLogsQuery: vi.fn(),
}));

const STORE_ID = "22222222-2222-2222-2222-222222222222";
const ITEM_ID = "11111111-1111-1111-1111-111111111111";
const VARIANT_ID = "33333333-3333-3333-3333-333333333333";
const PRODUCT_ID = "44444444-4444-4444-4444-444444444444";

const SECTION_TITLES = [
  "Quick actions",
  "Low-stock inventory",
  "Orders to review",
  "Product review",
  "Recent inventory activity",
  "Dashboard summaries require backend support",
] as const;

// Every banned phrase the spec enumerates. These are checked as a single
// page-wide negative sweep on the rendered text. Keep substrings lowercase;
// the assertion lowercases the haystack before comparing.
//
// Care has been taken so none of these collides with the required disclaimer
// "No KPIs are simulated in the frontend." — that string contains "kpi" by
// design, but no entry below is a substring of it (e.g. we ban "fake kpi"
// and "simulated kpi card", not the bare word "kpi").
const FORBIDDEN_RUNTIME_COPY = [
  // Subphase / planning markers
  "F2.7",
  "F2.12",
  "F2.13",
  "coming soon",
  "backend integration pending",
  // Financial / KPI claims
  "revenue",
  "profit",
  "fake kpi",
  "simulated kpi card",
  // Score-style claims
  "health score",
  "inventory health score",
  "store health score",
  "risk score",
  "compliance risk score",
  "order sla score",
  "SLA",
  // E-commerce framings the dashboard must not adopt
  "checkout",
  "cart",
  "marketplace",
  "customer ordering",
  // Dashboard "metric of the day" framings the backend doesn't support
  "orders today",
  "delayed orders",
  // Activity-feed framings the backend doesn't support
  "recent store activity",
  "unified activity feed",
  "store audit feed",
  "fake audit events",
  "fake activity count",
  // Compliance over-reach claims
  "all compliance issues",
  "total restricted products",
] as const;

interface QuickActionFixture {
  name: string;
  href: string;
  testId: string;
}

const QUICK_ACTIONS: ReadonlyArray<QuickActionFixture> = [
  {
    name: "Create order",
    href: "/app/store/orders/new",
    testId: "quick-action-create-order",
  },
  {
    name: "View orders",
    href: "/app/store/orders",
    testId: "quick-action-view-orders",
  },
  {
    name: "View inventory",
    href: "/app/store/inventory",
    testId: "quick-action-view-inventory",
  },
  {
    name: "View products",
    href: "/app/store/products",
    testId: "quick-action-view-products",
  },
  {
    name: "Create store user",
    href: "/app/store/users",
    testId: "quick-action-create-store-user",
  },
  {
    name: "View audit",
    href: "/app/store/audit",
    testId: "quick-action-view-audit",
  },
  {
    name: "Store settings",
    href: "/app/store/settings",
    testId: "quick-action-store-settings",
  },
];

const FORBIDDEN_HREF_PREFIXES = [
  "/app/admin",
  "/app/orders",
  "/app/products",
  "/app/inventory",
  "/checkout",
  "/cart",
  "/marketplace",
] as const;

function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return partial as UseQueryResult<TData>;
}

function makeItem(overrides: Partial<InventoryItem> = {}): InventoryItem {
  return {
    id: ITEM_ID,
    store_id: STORE_ID,
    variant_id: VARIANT_ID,
    quantity_on_hand: 3,
    quantity_reserved: 0,
    reorder_threshold: 10,
    status: "available",
    last_counted_at: null,
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-01T00:00:00Z",
    variant: {
      id: VARIANT_ID,
      sku: "GUM-MIX-10",
      flavor: null,
      size_label: null,
      is_active: true,
      product: {
        id: PRODUCT_ID,
        name: "Cosmic Gummies",
        brand: null,
        category: "edibles",
        compliance_status: "allowed",
        allowed_for_sale: true,
        is_active: true,
      },
    },
    ...overrides,
  };
}

function makeListResponse(
  overrides: Partial<InventoryListResponse> = {},
): InventoryListResponse {
  return {
    items: [],
    total: 0,
    limit: 5,
    offset: 0,
    ...overrides,
  };
}

function mockInventoryQuery(
  partial: Partial<UseQueryResult<InventoryListResponse>>,
) {
  vi.mocked(inventoryHooks.useInventoryList).mockReturnValue(
    asQueryResult<InventoryListResponse>(partial),
  );
}

const ORDER_ID = "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa";

function makeOrderItem(
  overrides: Partial<OrderItemRead> = {},
): OrderItemRead {
  return {
    id: "55555555-5555-5555-5555-555555555555",
    order_id: ORDER_ID,
    variant_id: VARIANT_ID,
    inventory_item_id: "66666666-6666-6666-6666-666666666666",
    quantity: 1,
    unit_price: "10.00",
    line_total: "10.00",
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-01T00:00:00Z",
    variant: {
      id: VARIANT_ID,
      sku: "GUM-MIX-10",
      flavor: null,
      size_label: null,
      is_active: true,
      product: {
        id: PRODUCT_ID,
        name: "Cosmic Gummies",
        brand: null,
        category: "edibles",
        compliance_status: "allowed",
        allowed_for_sale: true,
        is_active: true,
      },
    },
    ...overrides,
  };
}

function makeOrder(overrides: Partial<OrderRead> = {}): OrderRead {
  return {
    id: ORDER_ID,
    store_id: STORE_ID,
    customer_user_id: null,
    idempotency_key: "99999999-9999-4999-8999-999999999999",
    status: "pending",
    subtotal_amount: "10.00",
    tax_amount: "0.00",
    total_amount: "10.00",
    age_verified_at: null,
    age_verified_by_user_id: null,
    accepted_at: null,
    canceled_at: null,
    delivered_at: null,
    returned_at: null,
    cancel_reason: null,
    notes: null,
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-01T00:00:00Z",
    items: [makeOrderItem()],
    ...overrides,
  };
}

function makeOrdersListResponse(
  overrides: Partial<OrdersListResponse> = {},
): OrdersListResponse {
  return {
    items: [],
    total: 0,
    limit: 5,
    offset: 0,
    ...overrides,
  };
}

function mockOrdersQuery(
  partial: Partial<UseQueryResult<OrdersListResponse>>,
) {
  vi.mocked(ordersHooks.useOrdersList).mockReturnValue(
    asQueryResult<OrdersListResponse>(partial),
  );
}

function makeProduct(overrides: Partial<Product> = {}): Product {
  return {
    id: PRODUCT_ID,
    name: "Cosmic Gummies",
    brand: "Nebula",
    category: "edibles",
    description: null,
    compliance_status: "restricted",
    allowed_for_sale: false,
    is_active: true,
    hold_reason: null,
    jurisdiction: "FL",
    last_compliance_check: null,
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-01T00:00:00Z",
    ...overrides,
  };
}

function mockProductsQuery(partial: Partial<UseQueryResult<Product[]>>) {
  vi.mocked(productsHooks.useProductsQuery).mockReturnValue(
    asQueryResult<Product[]>(partial),
  );
}

function makeInventoryLog(
  overrides: Partial<StoreInventoryLogEntry> = {},
): StoreInventoryLogEntry {
  return {
    id: "77777777-7777-7777-7777-777777777777",
    inventory_item_id: "66666666-6666-6666-6666-666666666666",
    store_id: STORE_ID,
    variant_id: VARIANT_ID,
    performed_by_user_id: null,
    movement_type: "receipt",
    quantity_delta: 10,
    quantity_after: 50,
    reason: null,
    reference_type: null,
    reference_id: null,
    created_at: "2026-05-01T00:00:00Z",
    ...overrides,
  };
}

function mockInventoryLogsQuery(
  partial: Partial<UseQueryResult<StoreInventoryLogEntry[]>>,
) {
  vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReturnValue(
    asQueryResult<StoreInventoryLogEntry[]>(partial),
  );
}

function makeStoreContext(
  overrides: Partial<StoreContextState> = {},
): StoreContextState {
  return {
    currentStoreId: STORE_ID,
    hasStoreContext: true,
    isStoreRequired: true,
    storeError: null,
    ...overrides,
  };
}

function mockEmptyData() {
  vi.mocked(authModule.useStoreContext).mockReturnValue(makeStoreContext());
  mockInventoryQuery({
    isLoading: false,
    isError: false,
    isSuccess: true,
    data: makeListResponse(),
    error: null,
    refetch: vi.fn() as never,
  });
  mockOrdersQuery({
    isLoading: false,
    isError: false,
    isSuccess: true,
    data: makeOrdersListResponse(),
    error: null,
    refetch: vi.fn() as never,
  });
  mockProductsQuery({
    isLoading: false,
    isError: false,
    isSuccess: true,
    data: [],
    error: null,
    refetch: vi.fn() as never,
  });
  mockInventoryLogsQuery({
    isLoading: false,
    isError: false,
    isSuccess: true,
    data: [],
    error: null,
    refetch: vi.fn() as never,
  });
}

beforeEach(() => {
  vi.mocked(authModule.useStoreContext).mockReset();
  vi.mocked(inventoryHooks.useInventoryList).mockReset();
  vi.mocked(ordersHooks.useOrdersList).mockReset();
  vi.mocked(productsHooks.useProductsQuery).mockReset();
  vi.mocked(auditHooks.useStoreInventoryLogsQuery).mockReset();
  // Default success/empty so the regression suite (which doesn't care
  // about widget-specific state) doesn't render a loading or error branch.
  mockEmptyData();
});

afterEach(() => {
  vi.clearAllMocks();
});

function renderPage() {
  return render(
    <MemoryRouter>
      <DashboardHomePage />
    </MemoryRouter>,
  );
}

describe("DashboardHomePage - shell", () => {
  it("renders the operational header copy", () => {
    renderPage();

    expect(
      screen.getByRole("heading", { level: 1, name: /store dashboard/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/operational home for this store/i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /review orders, inventory, product review items, and recent inventory activity for this store\./i,
      ),
    ).toBeInTheDocument();
  });

  it("renders all required operational sections", () => {
    renderPage();

    for (const title of SECTION_TITLES) {
      expect(
        screen.getByRole("heading", {
          level: 3,
          name: new RegExp(title, "i"),
        }),
      ).toBeInTheDocument();
    }
  });

  it("renders the explicit no-simulated-KPIs disclaimer", () => {
    renderPage();

    expect(
      screen.getByText(/no kpis are simulated in the frontend\./i),
    ).toBeInTheDocument();
  });

  it("does not expose forbidden runtime copy", () => {
    const { container } = renderPage();

    const visibleText = (container.textContent ?? "").toLowerCase();
    for (const term of FORBIDDEN_RUNTIME_COPY) {
      expect(visibleText).not.toContain(term.toLowerCase());
    }
  });

  it("is no longer a generic single-block placeholder", () => {
    renderPage();

    expect(
      screen.queryByText(/store operations dashboard will show daily/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/^Planned$/)).not.toBeInTheDocument();

    expect(
      screen.getByTestId("dashboard-quick-actions"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-low-stock")).toBeInTheDocument();
    expect(
      screen.getByTestId("dashboard-orders-to-review"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("dashboard-product-review"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("dashboard-inventory-activity"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("dashboard-backend-summary"),
    ).toBeInTheDocument();
  });

  it("documents the future backend endpoints the page depends on", () => {
    renderPage();

    const list = screen.getByTestId("dashboard-future-endpoints");
    expect(list).toBeInTheDocument();
    expect(list.textContent).toContain("/stores/:storeId/dashboard");
    expect(list.textContent).toContain("/stores/:storeId/orders/summary");
    expect(list.textContent).toContain("/stores/:storeId/inventory/summary");
    expect(list.textContent).toContain("/stores/:storeId/products/summary");
    expect(list.textContent).toContain("/stores/:storeId/activity");
    expect(list.textContent).toContain("/stores/:storeId/alerts");
  });
});

describe("DashboardHomePage - quick actions", () => {
  it("renders all 7 quick actions with the expected hrefs", () => {
    renderPage();

    const quickActionsCard = screen.getByTestId("dashboard-quick-actions");

    for (const { name, href, testId } of QUICK_ACTIONS) {
      const link = screen.getByTestId(testId);
      expect(link.tagName).toBe("A");
      expect(link).toHaveAttribute("href", href);
      expect(link.textContent ?? "").toContain(name);
      expect(quickActionsCard).toContainElement(link);
    }
  });

  it("renders quick action descriptions", () => {
    renderPage();

    expect(
      screen.getByText(/start a store order workflow\./i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/review and manage store orders\./i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/check stock levels and inventory actions\./i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /review product catalog and compliance status\./i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/manage store user access\./i),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        /review inventory and operational audit records\./i,
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/manage store configuration\./i),
    ).toBeInTheDocument();
  });

  it("only routes quick actions through /app/store/*", () => {
    const { container } = renderPage();

    const quickActionsCard = screen.getByTestId("dashboard-quick-actions");
    const quickActionLinks = Array.from(
      quickActionsCard.querySelectorAll("a"),
    );

    expect(quickActionLinks).toHaveLength(QUICK_ACTIONS.length);
    for (const link of quickActionLinks) {
      const href = link.getAttribute("href") ?? "";
      expect(href.startsWith("/app/store/")).toBe(true);
    }

    const allLinks = Array.from(container.querySelectorAll("a"));
    for (const link of allLinks) {
      const href = link.getAttribute("href") ?? "";
      for (const forbidden of FORBIDDEN_HREF_PREFIXES) {
        expect(href.startsWith(forbidden)).toBe(false);
      }
    }
  });

  it("renders quick actions as enabled, navigable controls (no disabled buttons)", () => {
    renderPage();

    const quickActionsCard = screen.getByTestId("dashboard-quick-actions");

    const disabledButtons = quickActionsCard.querySelectorAll(
      "button[disabled]",
    );
    expect(disabledButtons.length).toBe(0);

    for (const { testId } of QUICK_ACTIONS) {
      const link = screen.getByTestId(testId);
      expect(link).not.toHaveAttribute("aria-disabled", "true");
      expect(link).not.toHaveAttribute("disabled");
    }
  });
});

describe("DashboardHomePage - Low-stock inventory widget", () => {
  it("calls useInventoryList with low_stock_only and limit 5", () => {
    renderPage();

    expect(inventoryHooks.useInventoryList).toHaveBeenCalledWith(
      expect.objectContaining({
        low_stock_only: true,
        limit: 5,
      }),
    );
  });

  it("renders a loading state while the query is loading", () => {
    mockInventoryQuery({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-low-stock");
    expect(within(card).getByRole("status")).toHaveTextContent(
      /loading low-stock inventory/i,
    );
    // No item rows and no empty/error copy while loading.
    expect(
      within(card).queryByTestId("dashboard-low-stock-list"),
    ).not.toBeInTheDocument();
    expect(
      within(card).queryByText(
        /no low-stock inventory returned by the current filters\./i,
      ),
    ).not.toBeInTheDocument();
  });

  it("renders a scoped error state when the query fails", () => {
    const refetch = vi.fn();
    mockInventoryQuery({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new ApiError(503, "service unavailable", { detail: "boom" }),
      refetch: refetch as never,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-low-stock");
    expect(
      within(card).getByText(/low-stock inventory failed to load\./i),
    ).toBeInTheDocument();

    // Page-level shell still renders — the error is widget-scoped only.
    expect(
      screen.getByRole("heading", { level: 1, name: /store dashboard/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("dashboard-backend-summary"),
    ).toBeInTheDocument();

    // Retry button is wired to the query's refetch.
    const retry = within(card).getByRole("button", { name: /retry/i });
    fireEvent.click(retry);
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders the empty state copy when no low-stock items are returned", () => {
    mockInventoryQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeListResponse({ items: [], total: 0 }),
      error: null,
      refetch: vi.fn() as never,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-low-stock");
    expect(
      within(card).getByText(
        /no low-stock inventory returned by the current filters\./i,
      ),
    ).toBeInTheDocument();

    // None of the discouraged "everything is fine" tones leak through.
    expect(
      within(card).queryByText(/your inventory is healthy/i),
    ).not.toBeInTheDocument();
    expect(
      within(card).queryByText(/everything is fine/i),
    ).not.toBeInTheDocument();
    expect(
      within(card).queryByText(/no inventory issues/i),
    ).not.toBeInTheDocument();
  });

  it("renders up to 5 low-stock items with real fields", () => {
    const items: InventoryItem[] = [
      makeItem({
        id: "00000000-0000-0000-0000-000000000001",
        quantity_on_hand: 2,
        reorder_threshold: 10,
        variant: {
          id: VARIANT_ID,
          sku: "GUM-MIX-10",
          flavor: null,
          size_label: null,
          is_active: true,
          product: {
            id: PRODUCT_ID,
            name: "Cosmic Gummies",
            brand: null,
            category: "edibles",
            compliance_status: "allowed",
            allowed_for_sale: true,
            is_active: true,
          },
        },
      }),
      makeItem({
        id: "00000000-0000-0000-0000-000000000002",
        quantity_on_hand: 0,
        reorder_threshold: 5,
        status: "flagged",
        variant: {
          id: "55555555-5555-5555-5555-555555555555",
          sku: "VAPE-LM-30",
          flavor: "lemon",
          size_label: "30ml",
          is_active: true,
          product: {
            id: "66666666-6666-6666-6666-666666666666",
            name: "Lunar Mist",
            brand: null,
            category: "vapes",
            compliance_status: "allowed",
            allowed_for_sale: true,
            is_active: true,
          },
        },
      }),
    ];

    mockInventoryQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeListResponse({ items, total: items.length }),
      error: null,
      refetch: vi.fn() as never,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-low-stock");
    const rows = within(card).getAllByTestId("dashboard-low-stock-item");
    expect(rows).toHaveLength(items.length);

    // Real fields from the wire shape are rendered.
    expect(within(card).getByText("Cosmic Gummies")).toBeInTheDocument();
    expect(within(card).getByText("GUM-MIX-10")).toBeInTheDocument();
    expect(within(card).getByText("Lunar Mist")).toBeInTheDocument();
    expect(within(card).getByText("VAPE-LM-30")).toBeInTheDocument();
    // Status enum values from the wire (lowercased on the wire).
    expect(within(card).getByText(/^available$/i)).toBeInTheDocument();
    expect(within(card).getByText(/^flagged$/i)).toBeInTheDocument();
  });

  it("links to the full inventory page", () => {
    renderPage();

    const card = screen.getByTestId("dashboard-low-stock");
    const link = within(card).getByTestId("dashboard-low-stock-link");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/app/store/inventory");
  });

  it("never renders fake KPIs, health scores, or alert copy", () => {
    const items = [makeItem()];
    mockInventoryQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeListResponse({ items, total: 1 }),
      error: null,
      refetch: vi.fn() as never,
    });

    const { container } = renderPage();

    const visibleText = (container.textContent ?? "").toLowerCase();
    for (const banned of [
      "inventory health score",
      "stock health score",
      "health score",
      "risk score",
      "fake alert",
      "revenue",
      "profit",
      "checkout",
      "cart",
      "marketplace",
    ]) {
      expect(visibleText).not.toContain(banned);
    }
  });
});

describe("DashboardHomePage - Orders to review widget", () => {
  it("calls useOrdersList with limit 5", () => {
    renderPage();

    expect(ordersHooks.useOrdersList).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 5 }),
    );
  });

  it("renders a loading state while the query is loading", () => {
    mockOrdersQuery({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-orders-to-review");
    expect(within(card).getByRole("status")).toHaveTextContent(
      /loading orders to review/i,
    );
    expect(
      within(card).queryByTestId("dashboard-orders-to-review-list"),
    ).not.toBeInTheDocument();
    expect(
      within(card).queryByText(
        /no orders returned by the current dashboard query\./i,
      ),
    ).not.toBeInTheDocument();
  });

  it("renders a scoped error state when the query fails", () => {
    const refetch = vi.fn();
    mockOrdersQuery({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new ApiError(503, "service unavailable", { detail: "boom" }),
      refetch: refetch as never,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-orders-to-review");
    expect(
      within(card).getByText(/orders to review failed to load\./i),
    ).toBeInTheDocument();

    // Page-level shell still renders — the error is widget-scoped only.
    expect(
      screen.getByRole("heading", { level: 1, name: /store dashboard/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("dashboard-backend-summary"),
    ).toBeInTheDocument();
    // Other widgets still render their default branches.
    expect(screen.getByTestId("dashboard-low-stock")).toBeInTheDocument();

    const retry = within(card).getByRole("button", { name: /retry/i });
    fireEvent.click(retry);
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders the empty state copy when no orders are returned", () => {
    mockOrdersQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeOrdersListResponse({ items: [], total: 0 }),
      error: null,
      refetch: vi.fn() as never,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-orders-to-review");
    expect(
      within(card).getByText(
        /no orders returned by the current dashboard query\./i,
      ),
    ).toBeInTheDocument();

    // None of the discouraged "everything is fine" tones leak through.
    expect(
      within(card).queryByText(/no order issues/i),
    ).not.toBeInTheDocument();
    expect(
      within(card).queryByText(/everything is on track/i),
    ).not.toBeInTheDocument();
    expect(
      within(card).queryByText(/no delayed orders/i),
    ).not.toBeInTheDocument();
  });

  it("renders up to 5 orders with real fields and item-level links", () => {
    const orders: OrderRead[] = [
      makeOrder({
        id: "00000000-0000-0000-0000-0000000000a1",
        status: "pending",
        items: [makeOrderItem(), makeOrderItem()],
      }),
      makeOrder({
        id: "00000000-0000-0000-0000-0000000000a2",
        status: "preparing",
        items: [makeOrderItem()],
      }),
    ];

    mockOrdersQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeOrdersListResponse({ items: orders, total: orders.length }),
      error: null,
      refetch: vi.fn() as never,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-orders-to-review");
    const rows = within(card).getAllByTestId(
      "dashboard-orders-to-review-item",
    );
    expect(rows).toHaveLength(orders.length);

    // Order id and wire status appear; financial fields do NOT.
    expect(
      within(card).getByText("00000000-0000-0000-0000-0000000000a1"),
    ).toBeInTheDocument();
    expect(within(card).getByText(/^pending$/i)).toBeInTheDocument();
    expect(within(card).getByText(/^preparing$/i)).toBeInTheDocument();
    expect(within(card).getByText(/2\s+items/i)).toBeInTheDocument();
    expect(within(card).getByText(/1\s+item$/i)).toBeInTheDocument();

    // Item-level links use the existing /app/store/orders/:orderId pattern.
    const itemLinks = within(card).getAllByTestId(
      "dashboard-orders-to-review-item-link",
    );
    expect(itemLinks).toHaveLength(orders.length);
    expect(itemLinks[0]).toHaveAttribute(
      "href",
      `/app/store/orders/${orders[0].id}`,
    );
    expect(itemLinks[1]).toHaveAttribute(
      "href",
      `/app/store/orders/${orders[1].id}`,
    );

    // Financial / KPI-style copy never reaches the DOM.
    const cardText = (card.textContent ?? "").toLowerCase();
    for (const banned of [
      "subtotal",
      "tax",
      "total amount",
      "$",
      "revenue",
      "profit",
      "orders today",
      "delayed orders",
      "sla",
      "risk score",
    ]) {
      expect(cardText).not.toContain(banned);
    }
  });

  it("links to the full orders page", () => {
    renderPage();

    const card = screen.getByTestId("dashboard-orders-to-review");
    const link = within(card).getByTestId("dashboard-orders-to-review-link");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/app/store/orders");
  });
});

describe("DashboardHomePage - Product review widget", () => {
  it("calls useProductsQuery with limit 5", () => {
    renderPage();

    expect(productsHooks.useProductsQuery).toHaveBeenCalledWith(
      expect.objectContaining({ limit: 5 }),
    );
  });

  it("renders a loading state while the query is loading", () => {
    mockProductsQuery({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-product-review");
    expect(within(card).getByRole("status")).toHaveTextContent(
      /loading product review/i,
    );
    expect(
      within(card).queryByTestId("dashboard-product-review-list"),
    ).not.toBeInTheDocument();
    expect(
      within(card).queryByText(
        /no product review items returned by the current filters\./i,
      ),
    ).not.toBeInTheDocument();
  });

  it("renders a scoped error state when the query fails", () => {
    const refetch = vi.fn();
    mockProductsQuery({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new ApiError(503, "service unavailable", { detail: "boom" }),
      refetch: refetch as never,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-product-review");
    expect(
      within(card).getByText(/product review failed to load\./i),
    ).toBeInTheDocument();

    // Page-level shell still renders — the error is widget-scoped only.
    expect(
      screen.getByRole("heading", { level: 1, name: /store dashboard/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("dashboard-backend-summary"),
    ).toBeInTheDocument();
    // Other widgets still render their default branches.
    expect(screen.getByTestId("dashboard-low-stock")).toBeInTheDocument();
    expect(
      screen.getByTestId("dashboard-orders-to-review"),
    ).toBeInTheDocument();

    const retry = within(card).getByRole("button", { name: /retry/i });
    fireEvent.click(retry);
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders the empty state copy when no products are returned", () => {
    mockProductsQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: [],
      error: null,
      refetch: vi.fn() as never,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-product-review");
    expect(
      within(card).getByText(
        /no product review items returned by the current filters\./i,
      ),
    ).toBeInTheDocument();

    // None of the discouraged "everything is compliant" tones leak through.
    expect(
      within(card).queryByText(/all products are compliant/i),
    ).not.toBeInTheDocument();
    expect(
      within(card).queryByText(/no product issues/i),
    ).not.toBeInTheDocument();
    expect(
      within(card).queryByText(/everything is compliant/i),
    ).not.toBeInTheDocument();
  });

  it("renders up to 5 products with real fields, badges, and item-level links", () => {
    const products: Product[] = [
      makeProduct({
        id: "00000000-0000-0000-0000-0000000000b1",
        name: "Cosmic Gummies",
        brand: "Nebula",
        category: "edibles",
        compliance_status: "restricted",
        is_active: true,
      }),
      makeProduct({
        id: "00000000-0000-0000-0000-0000000000b2",
        name: "Lunar Mist",
        brand: null,
        category: "vapes",
        compliance_status: "banned",
        is_active: false,
      }),
    ];

    mockProductsQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: products,
      error: null,
      refetch: vi.fn() as never,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-product-review");
    const rows = within(card).getAllByTestId("dashboard-product-review-item");
    expect(rows).toHaveLength(products.length);

    // Real wire fields are rendered.
    expect(within(card).getByText("Cosmic Gummies")).toBeInTheDocument();
    expect(within(card).getByText(/^Nebula\s*·\s*edibles$/)).toBeInTheDocument();
    expect(within(card).getByText("Lunar Mist")).toBeInTheDocument();
    // Brand is null on Lunar Mist; only the category appears.
    expect(within(card).getByText("vapes")).toBeInTheDocument();

    // Existing badges render with real wire values.
    expect(
      within(card).getByTestId("product-status-active"),
    ).toBeInTheDocument();
    expect(
      within(card).getByTestId("product-status-inactive"),
    ).toBeInTheDocument();
    expect(
      within(card).getByTestId("product-compliance-restricted"),
    ).toBeInTheDocument();
    expect(
      within(card).getByTestId("product-compliance-banned"),
    ).toBeInTheDocument();

    // Item-level links use the existing /app/store/products/:productId pattern.
    const itemLinks = within(card).getAllByTestId(
      "dashboard-product-review-item-link",
    );
    expect(itemLinks).toHaveLength(products.length);
    expect(itemLinks[0]).toHaveAttribute(
      "href",
      `/app/store/products/${products[0].id}`,
    );
    expect(itemLinks[1]).toHaveAttribute(
      "href",
      `/app/store/products/${products[1].id}`,
    );

    // Forbidden compliance / KPI / financial copy never reaches the card.
    const cardText = (card.textContent ?? "").toLowerCase();
    for (const banned of [
      "compliance risk score",
      "risk score",
      "all compliance issues",
      "total restricted products",
      "revenue",
      "profit",
      "checkout",
      "cart",
      "marketplace",
    ]) {
      expect(cardText).not.toContain(banned);
    }
  });

  it("links to the full products page", () => {
    renderPage();

    const card = screen.getByTestId("dashboard-product-review");
    const link = within(card).getByTestId("dashboard-product-review-link");
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/app/store/products");
  });

  it("does not introduce sellable detail queries from the dashboard", () => {
    // ProductSellableBadge fires a per-product detail query and would
    // create N+1 queries from the dashboard. The widget intentionally
    // never mounts it — assert no sellable-* badge testIds leak into
    // the card.
    const products: Product[] = [makeProduct()];
    mockProductsQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: products,
      error: null,
      refetch: vi.fn() as never,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-product-review");
    expect(
      within(card).queryByTestId(/^product-sellable-/),
    ).not.toBeInTheDocument();
  });
});

describe("DashboardHomePage - Recent inventory activity widget", () => {
  it("calls useStoreInventoryLogsQuery with the active store id and limit 5", () => {
    renderPage();

    expect(auditHooks.useStoreInventoryLogsQuery).toHaveBeenCalledWith(
      expect.objectContaining({ storeId: STORE_ID, limit: 5 }),
    );
  });

  it("renders a loading state while the query is loading", () => {
    mockInventoryLogsQuery({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-inventory-activity");
    expect(within(card).getByRole("status")).toHaveTextContent(
      /loading recent inventory activity/i,
    );
    expect(
      within(card).queryByTestId("dashboard-inventory-activity-list"),
    ).not.toBeInTheDocument();
    expect(
      within(card).queryByText(/no inventory activity returned yet\./i),
    ).not.toBeInTheDocument();
  });

  it("renders a scoped error state when the query fails", () => {
    const refetch = vi.fn();
    mockInventoryLogsQuery({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new ApiError(503, "service unavailable", { detail: "boom" }),
      refetch: refetch as never,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-inventory-activity");
    expect(
      within(card).getByText(/recent inventory activity failed to load\./i),
    ).toBeInTheDocument();

    // Page-level shell still renders — the error is widget-scoped only.
    expect(
      screen.getByRole("heading", { level: 1, name: /store dashboard/i }),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("dashboard-backend-summary"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("dashboard-low-stock")).toBeInTheDocument();
    expect(
      screen.getByTestId("dashboard-orders-to-review"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("dashboard-product-review"),
    ).toBeInTheDocument();

    const retry = within(card).getByRole("button", { name: /retry/i });
    fireEvent.click(retry);
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders the empty state copy when no inventory logs are returned", () => {
    mockInventoryLogsQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: [],
      error: null,
      refetch: vi.fn() as never,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-inventory-activity");
    expect(
      within(card).getByText(/no inventory activity returned yet\./i),
    ).toBeInTheDocument();

    // None of the discouraged "everything is quiet" tones leak through.
    expect(
      within(card).queryByText(/no store activity/i),
    ).not.toBeInTheDocument();
    expect(
      within(card).queryByText(/no audit issues/i),
    ).not.toBeInTheDocument();
    expect(
      within(card).queryByText(/everything is quiet/i),
    ).not.toBeInTheDocument();
    expect(
      within(card).queryByText(/no operational events/i),
    ).not.toBeInTheDocument();
  });

  it("renders up to 5 inventory logs with real fields", () => {
    const logs: StoreInventoryLogEntry[] = [
      makeInventoryLog({
        id: "00000000-0000-0000-0000-0000000000c1",
        movement_type: "receipt",
        quantity_delta: 12,
        quantity_after: 50,
        reason: null,
      }),
      makeInventoryLog({
        id: "00000000-0000-0000-0000-0000000000c2",
        movement_type: "adjustment",
        quantity_delta: -3,
        quantity_after: 47,
        reason: "shrinkage recount",
      }),
    ];

    mockInventoryLogsQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: logs,
      error: null,
      refetch: vi.fn() as never,
    });

    renderPage();

    const card = screen.getByTestId("dashboard-inventory-activity");
    const rows = within(card).getAllByTestId(
      "dashboard-inventory-activity-item",
    );
    expect(rows).toHaveLength(logs.length);

    // Real wire fields are rendered.
    expect(within(card).getByText(/^receipt$/i)).toBeInTheDocument();
    expect(within(card).getByText(/^adjustment$/i)).toBeInTheDocument();
    expect(within(card).getByText("+12")).toBeInTheDocument();
    expect(within(card).getByText("-3")).toBeInTheDocument();
    expect(within(card).getByText(/after\s+50/i)).toBeInTheDocument();
    expect(within(card).getByText(/after\s+47/i)).toBeInTheDocument();
    expect(within(card).getByText(/shrinkage recount/i)).toBeInTheDocument();
  });

  it("renders inventory-scoped heading without unified-feed copy", () => {
    renderPage();

    expect(
      screen.getByRole("heading", {
        level: 3,
        name: /^recent inventory activity$/i,
      }),
    ).toBeInTheDocument();

    // Negative: the widget never re-frames itself as a global feed.
    expect(
      screen.queryByText(/recent store activity/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/unified activity feed/i),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByText(/store audit feed/i),
    ).not.toBeInTheDocument();
  });

  it("links to the audit hub", () => {
    renderPage();

    const card = screen.getByTestId("dashboard-inventory-activity");
    const link = within(card).getByTestId(
      "dashboard-inventory-activity-link",
    );
    expect(link.tagName).toBe("A");
    expect(link).toHaveAttribute("href", "/app/store/audit");

    // No item-level links: each <li> is a static row.
    expect(
      within(card).queryByTestId("dashboard-inventory-activity-item-link"),
    ).not.toBeInTheDocument();
  });

  it("never renders fake activity counts, KPI copy, or unified feed claims", () => {
    const logs = [makeInventoryLog()];
    mockInventoryLogsQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: logs,
      error: null,
      refetch: vi.fn() as never,
    });

    const { container } = renderPage();

    const visibleText = (container.textContent ?? "").toLowerCase();
    for (const banned of [
      "recent store activity",
      "unified activity feed",
      "store audit feed",
      "fake audit events",
      "fake activity count",
      "revenue",
      "profit",
      "checkout",
      "cart",
      "marketplace",
    ]) {
      expect(visibleText).not.toContain(banned);
    }
  });
});

describe("DashboardHomePage - Backend-required dashboard summary", () => {
  it("renders the heading and the no-simulated-KPIs disclaimer", () => {
    renderPage();

    const card = screen.getByTestId("dashboard-backend-summary");
    expect(
      within(card).getByRole("heading", {
        level: 3,
        name: /dashboard summaries require backend support/i,
      }),
    ).toBeInTheDocument();
    expect(
      within(card).getByText(/no kpis are simulated in the frontend\./i),
    ).toBeInTheDocument();
  });

  it("explains the operational lists vs. summary endpoints split", () => {
    renderPage();

    const card = screen.getByTestId("dashboard-backend-summary");
    // The CardDescription covers the three contract points: real list
    // endpoints today, summaries are not simulated, summaries need
    // backend support.
    expect(
      within(card).getByText(/real list endpoints/i),
    ).toBeInTheDocument();
    expect(
      within(card).getByText(/the frontend does not simulate them/i),
    ).toBeInTheDocument();
  });

  it("documents all 7 future backend endpoints exactly", () => {
    renderPage();

    const card = screen.getByTestId("dashboard-backend-summary");
    // The list of future endpoints sits under a real <h4> sub-heading
    // rather than a styled <p>, so screen readers can navigate the
    // backend-required card by heading levels (h3 card title → h4
    // future-endpoints sub-heading).
    expect(
      within(card).getByRole("heading", {
        level: 4,
        name: /^future backend endpoints$/i,
      }),
    ).toBeInTheDocument();

    const list = screen.getByTestId("dashboard-future-endpoints");
    const items = within(list).getAllByRole("listitem");
    const expected = [
      "GET /stores/:storeId/dashboard",
      "GET /stores/:storeId/dashboard/kpis",
      "GET /stores/:storeId/orders/summary",
      "GET /stores/:storeId/inventory/summary",
      "GET /stores/:storeId/products/summary",
      "GET /stores/:storeId/activity",
      "GET /stores/:storeId/alerts",
    ];
    expect(items).toHaveLength(expected.length);
    for (const endpoint of expected) {
      expect(within(list).getByText(endpoint)).toBeInTheDocument();
    }
  });

  it("does not render fake KPI cards, charts, or simulated metrics", () => {
    renderPage();

    const card = screen.getByTestId("dashboard-backend-summary");
    const cardText = (card.textContent ?? "").toLowerCase();

    // Fake KPI / score / financial labels must NOT appear in the
    // backend-required card. The disclaimer "No KPIs are simulated..."
    // contains the word "kpi" by design — these checks are deliberately
    // narrower phrases so they don't collide with the disclaimer.
    for (const banned of [
      "revenue today",
      "orders today",
      "delayed orders",
      "store health score",
      "inventory health score",
      "compliance risk score",
      "order sla score",
      "fake kpi",
      "simulated kpi card",
      "fake alert",
      "fake activity count",
      "$",
    ]) {
      expect(cardText).not.toContain(banned);
    }

    // No chart primitives in the summary card.
    expect(card.querySelector("[data-testid*='chart']")).toBeNull();
    expect(within(card).queryByRole("img", { name: /chart/i })).not
      .toBeInTheDocument();
  });

  it("does not leak stale shell copy from earlier subphases", () => {
    const { container } = renderPage();

    // After F2.13.5, no widget renders a "Backend integration pending"
    // badge or a "Planned" status — the helper PendingSection was
    // removed once all four operational widgets were wired.
    const visibleText = (container.textContent ?? "").toLowerCase();
    for (const stale of [
      "backend integration pending",
      "coming soon",
      "store operations dashboard will show daily",
    ]) {
      expect(visibleText).not.toContain(stale);
    }
    expect(screen.queryByText(/^Planned$/)).not.toBeInTheDocument();
  });
});

describe("DashboardHomePage - regression hardening (F2.13.8)", () => {
  it("locks the page heading hierarchy: 1 × h1, 6 × h3, 1 × h4", () => {
    renderPage();

    // Locking exact counts catches accidental section adds/removes,
    // header demotion/promotion, or losing the F2.13.7 h4 promotion.
    // AlertTitle renders as <h5>, so it does not appear in these counts.
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getAllByRole("heading", { level: 3 })).toHaveLength(6);
    expect(screen.getAllByRole("heading", { level: 4 })).toHaveLength(1);
  });

  it("mounts exactly 6 widget cards (no surprise dashboard-* sections)", () => {
    const { container } = renderPage();

    const allDashboardCards = Array.from(
      container.querySelectorAll<HTMLElement>("[data-testid^='dashboard-']"),
    ).filter((node) => {
      const id = node.getAttribute("data-testid") ?? "";
      // Filter out structural inner testIds (lists, items, links, the
      // future-endpoints <ul>) — only count the top-level card containers.
      return !id.includes("-list")
        && !id.includes("-item")
        && !id.includes("-link")
        && id !== "dashboard-future-endpoints";
    });
    const cardTestIds = allDashboardCards
      .map((node) => node.getAttribute("data-testid"))
      .sort();

    expect(cardTestIds).toEqual([
      "dashboard-backend-summary",
      "dashboard-inventory-activity",
      "dashboard-low-stock",
      "dashboard-orders-to-review",
      "dashboard-product-review",
      "dashboard-quick-actions",
    ]);
  });

  it("renders no disabled buttons anywhere on the page", () => {
    const { container } = renderPage();

    // Page-wide check (not just the Quick actions card). Prevents
    // regressions where a future widget reintroduces dead/disabled
    // controls instead of real navigation.
    const disabledButtons = container.querySelectorAll("button[disabled]");
    expect(disabledButtons).toHaveLength(0);

    // Also no aria-disabled links — a Link styled to look disabled
    // would be functionally indistinguishable from a dead button.
    const ariaDisabled = container.querySelectorAll('[aria-disabled="true"]');
    expect(ariaDisabled).toHaveLength(0);
  });

  it("invokes each widget hook exactly once per render (N+1 guard)", () => {
    renderPage();

    // The strongest N+1 guard available without spinning up real
    // TanStack Query: each list hook must run exactly once on a single
    // dashboard render. Re-introducing a per-item useProductSellableQuery,
    // useInventoryItem, useOrder, etc. inside a list .map() would fail
    // the per-render invocation count.
    expect(inventoryHooks.useInventoryList).toHaveBeenCalledTimes(1);
    expect(ordersHooks.useOrdersList).toHaveBeenCalledTimes(1);
    expect(productsHooks.useProductsQuery).toHaveBeenCalledTimes(1);
    expect(auditHooks.useStoreInventoryLogsQuery).toHaveBeenCalledTimes(1);
  });

  it("renders no chart primitives anywhere on the page", () => {
    // Page-wide chart sweep (not just the backend summary card). Catches
    // regressions where a widget mounts a chart system, KPI viz, or any
    // testid'd chart container.
    const { container } = renderPage();

    expect(container.querySelector("[data-testid*='chart']")).toBeNull();
    expect(
      screen.queryByRole("img", { name: /chart/i }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("graphics-document"),
    ).not.toBeInTheDocument();
  });
});
