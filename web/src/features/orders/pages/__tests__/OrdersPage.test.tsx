// F2.11-M2.4: tests for OrdersPage.
//
// OrdersPage is a thin page shell over store context + the backend
// orders list query. These tests validate render branches, query args,
// filter/pagination state, and row rendering only.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import * as auth from "@/auth";
import OrdersPage from "../OrdersPage";
import type { GetOrdersListParams } from "../../api";
import * as ordersHooks from "../../hooks";
import type {
  OrderItemRead,
  OrderRead,
  OrdersListResponse,
} from "../../types";

vi.mock("@/auth", () => ({
  useStoreContext: vi.fn(),
}));

vi.mock("../../hooks", () => ({
  useOrdersList: vi.fn(),
}));

const STORE_ID = "22222222-2222-2222-2222-222222222222";
const ORDER_ID = "11111111-1111-1111-1111-111111111111";
const VARIANT_ID = "33333333-3333-3333-3333-333333333333";
const PRODUCT_ID = "44444444-4444-4444-4444-444444444444";

function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return partial as UseQueryResult<TData>;
}

function makeOrderItem(overrides: Partial<OrderItemRead> = {}): OrderItemRead {
  return {
    id: "55555555-5555-5555-5555-555555555555",
    order_id: ORDER_ID,
    variant_id: VARIANT_ID,
    inventory_item_id: "66666666-6666-6666-6666-666666666666",
    quantity: 2,
    unit_price: "12.50",
    line_total: "25.00",
    created_at: "2026-05-01T12:00:00Z",
    updated_at: "2026-05-01T12:00:00Z",
    variant: {
      id: VARIANT_ID,
      sku: "GUM-MIX-10",
      flavor: "Mixed berry",
      size_label: "10 pack",
      is_active: true,
      product: {
        id: PRODUCT_ID,
        name: "Cosmic Gummies",
        brand: "Orbit",
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
    idempotency_key: "orders-page-fixture",
    status: "pending",
    subtotal_amount: "25.00",
    tax_amount: "1.75",
    total_amount: "26.75",
    age_verified_at: null,
    age_verified_by_user_id: null,
    accepted_at: null,
    canceled_at: null,
    delivered_at: null,
    returned_at: null,
    cancel_reason: null,
    notes: null,
    created_at: "2026-05-01T12:00:00Z",
    updated_at: "2026-05-01T12:00:00Z",
    items: [makeOrderItem()],
    ...overrides,
  };
}

function makeListResponse(
  overrides: Partial<OrdersListResponse> = {},
): OrdersListResponse {
  return {
    items: [],
    total: 0,
    limit: 20,
    offset: 0,
    ...overrides,
  };
}

function mockStore(currentStoreId: string | null = STORE_ID) {
  vi.mocked(auth.useStoreContext).mockReturnValue({
    currentStoreId,
  } as ReturnType<typeof auth.useStoreContext>);
}

function mockOrdersQuery(partial: Partial<UseQueryResult<OrdersListResponse>>) {
  vi.mocked(ordersHooks.useOrdersList).mockReturnValue(
    asQueryResult<OrdersListResponse>(partial),
  );
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/app/store/orders"]}>
      <OrdersPage />
    </MemoryRouter>,
  );
}

function latestListParams(): GetOrdersListParams {
  const calls = vi.mocked(ordersHooks.useOrdersList).mock.calls;
  return calls[calls.length - 1][0] as GetOrdersListParams;
}

async function readRuntimeSource(filename: string): Promise<string> {
  const fs = await import("node:fs");
  const path = await import("node:path");
  const here = path.resolve(__dirname, "..", filename);
  const source = fs.readFileSync(here, "utf-8");

  return source
    .replace(/\/\*[\s\S]*?\*\//g, "")
    .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");
}

beforeEach(() => {
  vi.mocked(auth.useStoreContext).mockReset();
  vi.mocked(ordersHooks.useOrdersList).mockReset();
  mockStore();
  mockOrdersQuery({
    isLoading: false,
    isError: false,
    isSuccess: true,
    data: makeListResponse(),
    error: null,
    refetch: vi.fn() as never,
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("OrdersPage - store context", () => {
  it("renders the no-store empty state without table, filters, or pagination", () => {
    mockStore(null);
    mockOrdersQuery({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });

    renderPage();

    expect(screen.getByText(/no store selected/i)).toBeInTheDocument();
    expect(
      screen.getByText(/orders operate inside a store context/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
    expect(screen.queryByLabelText(/^status$/i)).toBeNull();
    expect(screen.queryByLabelText(/created from/i)).toBeNull();
    expect(screen.queryByRole("button", { name: /previous/i })).toBeNull();
    expect(screen.queryByRole("button", { name: /next/i })).toBeNull();
  });
});

describe("OrdersPage - render states", () => {
  it("renders loading state and disables filters while loading", () => {
    mockOrdersQuery({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });

    renderPage();

    expect(screen.getByRole("status")).toHaveTextContent(/loading orders/i);
    expect(screen.getByLabelText(/^status$/i)).toBeDisabled();
    expect(screen.getByLabelText(/created from/i)).toBeDisabled();
    expect(screen.getByLabelText(/created to/i)).toBeDisabled();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("renders backend ApiError detail and wires Retry to query.refetch", () => {
    const refetch = vi.fn();
    mockOrdersQuery({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new ApiError({
        status: 500,
        message: "orders backend exploded",
      }),
      refetch: refetch as never,
    });

    renderPage();

    expect(screen.getByRole("alert")).toHaveTextContent(
      /orders failed to load/i,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      /orders backend exploded/i,
    );

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders the empty state when the backend returns no orders", () => {
    mockOrdersQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeListResponse({ items: [], total: 0 }),
      error: null,
    });

    renderPage();

    expect(screen.getByTestId("orders-total")).toHaveTextContent("Total: 0");
    expect(screen.getByText(/no orders found/i)).toBeInTheDocument();
    expect(
      screen.getByText(/this store has no matching orders/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("table")).toBeNull();
  });

  it("renders backend total, backend row fields verbatim, and create/view links", () => {
    const first = makeOrder({
      id: ORDER_ID,
      status: "accepted",
      total_amount: "26.75",
      created_at: "2026-05-01T12:00:00Z",
      items: [makeOrderItem()],
    });
    const second = makeOrder({
      id: "77777777-7777-7777-7777-777777777777",
      status: "ready",
      total_amount: "0.00",
      created_at: "2026-05-02T09:30:00Z",
      items: [],
    });
    mockOrdersQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeListResponse({ items: [first, second], total: 42 }),
      error: null,
    });

    renderPage();

    expect(screen.getByTestId("orders-total")).toHaveTextContent("Total: 42");
    expect(screen.getByRole("link", { name: /create order/i })).toHaveAttribute(
      "href",
      "/app/store/orders/new",
    );

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(2);

    expect(within(rows[0]).getByText(first.id)).toBeInTheDocument();
    expect(within(rows[0]).getByText("accepted")).toBeInTheDocument();
    expect(within(rows[0]).getByText("26.75")).toBeInTheDocument();
    expect(within(rows[0]).getByText("1")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Cosmic Gummies")).toBeInTheDocument();
    expect(within(rows[0]).getByText("GUM-MIX-10")).toBeInTheDocument();
    expect(
      within(rows[0]).getByText("2026-05-01T12:00:00Z"),
    ).toBeInTheDocument();
    expect(within(rows[0]).getByRole("link", { name: /view/i })).toHaveAttribute(
      "href",
      `/app/store/orders/${first.id}`,
    );

    expect(within(rows[1]).getByText(second.id)).toBeInTheDocument();
    expect(within(rows[1]).getByText("ready")).toBeInTheDocument();
    expect(within(rows[1]).getByText("0.00")).toBeInTheDocument();
    expect(within(rows[1]).getByText("0")).toBeInTheDocument();
    expect(within(rows[1]).getByText(/no items/i)).toBeInTheDocument();
    expect(
      within(rows[1]).getByText("2026-05-02T09:30:00Z"),
    ).toBeInTheDocument();
    expect(within(rows[1]).getByRole("link", { name: /view/i })).toHaveAttribute(
      "href",
      `/app/store/orders/${second.id}`,
    );
  });
});

describe("OrdersPage - filters", () => {
  it("calls useOrdersList with the default backend-query params", () => {
    renderPage();

    expect(ordersHooks.useOrdersList).toHaveBeenCalledWith({
      limit: 20,
      offset: 0,
      status: undefined,
      created_from: undefined,
      created_to: undefined,
    });
  });

  it("sends selected status to the hook and clears back to undefined", () => {
    renderPage();

    fireEvent.click(screen.getByLabelText(/^status$/i));
    fireEvent.click(screen.getByRole("option", { name: /^accepted$/i }));
    expect(latestListParams()).toMatchObject({
      limit: 20,
      offset: 0,
      status: "accepted",
    });

    fireEvent.click(screen.getByLabelText(/^status$/i));
    fireEvent.click(screen.getByRole("option", { name: /all statuses/i }));
    expect(latestListParams()).toMatchObject({
      limit: 20,
      offset: 0,
      status: undefined,
    });
  });

  it("sends created_from and created_to datetime values and clears empty values to undefined", () => {
    renderPage();

    fireEvent.change(screen.getByLabelText(/created from/i), {
      target: { value: "2026-05-01T08:30" },
    });
    expect(latestListParams()).toMatchObject({
      created_from: "2026-05-01T08:30",
      created_to: undefined,
    });

    fireEvent.change(screen.getByLabelText(/created to/i), {
      target: { value: "2026-05-03T17:45" },
    });
    expect(latestListParams()).toMatchObject({
      created_from: "2026-05-01T08:30",
      created_to: "2026-05-03T17:45",
    });

    fireEvent.change(screen.getByLabelText(/created from/i), {
      target: { value: "" },
    });
    fireEvent.change(screen.getByLabelText(/created to/i), {
      target: { value: "" },
    });
    expect(latestListParams()).toMatchObject({
      created_from: undefined,
      created_to: undefined,
    });
  });

  it("resets offset to 0 when filters change", () => {
    mockOrdersQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeListResponse({ items: [makeOrder()], total: 45 }),
      error: null,
    });
    renderPage();

    fireEvent.click(screen.getByRole("button", { name: /next/i }));
    expect(latestListParams()).toMatchObject({ offset: 20 });

    fireEvent.click(screen.getByLabelText(/^status$/i));
    fireEvent.click(screen.getByRole("option", { name: /^preparing$/i }));
    expect(latestListParams()).toMatchObject({
      offset: 0,
      status: "preparing",
    });
  });
});

describe("OrdersPage - pagination", () => {
  it("uses backend total to enable and disable Previous and Next while paging", () => {
    mockOrdersQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeListResponse({ items: [makeOrder()], total: 35 }),
      error: null,
    });
    renderPage();

    const previous = screen.getByRole("button", { name: /previous/i });
    const next = screen.getByRole("button", { name: /next/i });

    expect(previous).toBeDisabled();
    expect(next).not.toBeDisabled();

    fireEvent.click(next);
    expect(latestListParams()).toMatchObject({ limit: 20, offset: 20 });
    expect(previous).not.toBeDisabled();
    expect(next).toBeDisabled();

    fireEvent.click(previous);
    expect(latestListParams()).toMatchObject({ limit: 20, offset: 0 });
    expect(previous).toBeDisabled();
    expect(next).not.toBeDisabled();
  });
});

describe("OrdersPage - architecture", () => {
  it("does NOT import useAuth / currentUser / role checks / permission helpers / fetch / axios", async () => {
    const code = await readRuntimeSource("OrdersPage.tsx");

    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\bcurrentUser\b/);
    expect(code).not.toMatch(/\buser\.role\b/);
    expect(code).not.toMatch(/\brole\s*===/);
    expect(code).not.toMatch(/\bcanView\b/);
    expect(code).not.toMatch(/\bcanManage\b/);
    expect(code).not.toMatch(/\bhasPermission\b/);
    expect(code).not.toMatch(/\ballowedRoles\b/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
  });

  it("does NOT compute order totals or mutate backend rows client-side", async () => {
    const code = await readRuntimeSource("OrdersPage.tsx");

    expect(code).not.toMatch(/subtotal_amount\s*[-+*/]/);
    expect(code).not.toMatch(/tax_amount\s*[-+*/]/);
    expect(code).not.toMatch(/total_amount\s*[-+*/]/);
    expect(code).not.toMatch(/unit_price\s*[-+*/]/);
    expect(code).not.toMatch(/line_total\s*[-+*/]/);
    expect(code).not.toMatch(/items\s*\.\s*sort\s*\(/);
    expect(code).not.toMatch(/items\s*\.\s*filter\s*\(/);
    expect(code).not.toMatch(/items\s*\.\s*reduce\s*\(/);
    expect(code).not.toMatch(/\baggregate\s*\(/);
  });

  it("keeps status filtering as query arguments instead of transition authority", async () => {
    const code = await readRuntimeSource("OrdersPage.tsx");

    expect(code).not.toMatch(/_ALLOWED_TRANSITIONS\s*=/);
    expect(code).not.toMatch(/transitionMatrix\s*=/);
    expect(code).not.toMatch(/canTransitionTo\s*\(/);
    expect(code).not.toMatch(/isTransitionAllowed\s*\(/);
  });
});
