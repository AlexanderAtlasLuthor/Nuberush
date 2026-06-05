// F2.11-M2.4: tests for OrderDetailPage.
//
// The detail page should render backend order data verbatim and mount
// child action/audit surfaces without owning transition, audit, totals,
// network, or authorization logic.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import {
  MemoryRouter,
  Route,
  Routes,
} from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import OrderDetailPage from "../OrderDetailPage";
import * as ordersHooks from "../../hooks";
import type { OrderItemRead, OrderRead } from "../../types";

vi.mock("../../hooks", () => ({
  useOrder: vi.fn(),
}));

vi.mock("../../components/OrderActionsBar", () => ({
  OrderActionsBar: ({ order }: { order: OrderRead }) => (
    <div data-testid="mock-order-actions-bar" data-order-id={order.id}>
      Actions for {order.id}
    </div>
  ),
}));

vi.mock("../../components/OrderAuditLogsPanel", () => ({
  OrderAuditLogsPanel: ({ orderId }: { orderId: string }) => (
    <div data-testid="mock-order-audit-logs-panel" data-order-id={orderId}>
      Audit logs for {orderId}
    </div>
  ),
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
    quantity: 3,
    unit_price: "9.50",
    line_total: "28.50",
    created_at: "2026-05-01T12:00:00Z",
    updated_at: "2026-05-01T12:00:00Z",
    variant: {
      id: VARIANT_ID,
      sku: "TEA-MINT-12OZ",
      flavor: "Mint",
      size_label: "12 oz",
      is_active: true,
      product: {
        id: PRODUCT_ID,
        name: "Aurora Tea",
        brand: "Northlight",
        category: "beverages",
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
    customer_user_id: "77777777-7777-7777-7777-777777777777",
    idempotency_key: "detail-page-idempotency-key",
    status: "preparing",
    subtotal_amount: "28.50",
    tax_amount: "1.99",
    total_amount: "30.49",
    age_verified_at: null,
    age_verified_by_user_id: null,
    accepted_at: null,
    canceled_at: null,
    delivered_at: null,
    returned_at: null,
    cancel_reason: null,
    notes: "Leave by the side counter",
    created_at: "2026-05-01T12:00:00Z",
    updated_at: "2026-05-01T12:05:00Z",
    items: [makeOrderItem()],
    ...overrides,
  };
}

function mockOrderQuery(partial: Partial<UseQueryResult<OrderRead>>) {
  vi.mocked(ordersHooks.useOrder).mockReturnValue(asQueryResult<OrderRead>(partial));
}

function renderAt(entry: string) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/app/store/orders" element={<OrderDetailPage />} />
        <Route path="/app/store/orders/:orderId" element={<OrderDetailPage />} />
      </Routes>
    </MemoryRouter>,
  );
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
  vi.mocked(ordersHooks.useOrder).mockReset();
  mockOrderQuery({
    isLoading: false,
    isError: false,
    isSuccess: true,
    data: makeOrder(),
    error: null,
    refetch: vi.fn() as never,
  });
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("OrderDetailPage - route and render branches", () => {
  it("renders the missing-id branch when the route has no orderId", () => {
    mockOrderQuery({
      isLoading: false,
      isError: false,
      data: undefined,
      error: null,
    });

    renderAt("/app/store/orders");

    expect(screen.getByRole("alert")).toHaveTextContent(/missing order id/i);
    expect(screen.getByRole("alert")).toHaveTextContent(
      /route did not provide a valid order id/i,
    );
    expect(ordersHooks.useOrder).toHaveBeenCalledWith("");
  });

  it("renders loading state", () => {
    mockOrderQuery({
      isLoading: true,
      isError: false,
      data: undefined,
      error: null,
    });

    renderAt(`/app/store/orders/${ORDER_ID}`);

    expect(screen.getByRole("status")).toHaveTextContent(/loading order/i);
    expect(screen.queryByTestId("mock-order-actions-bar")).toBeNull();
  });

  it("renders backend ApiError detail and wires Retry to query.refetch", () => {
    const refetch = vi.fn();
    mockOrderQuery({
      isLoading: false,
      isError: true,
      data: undefined,
      error: new ApiError({
        status: 404,
        message: "order disappeared",
      }),
      refetch: refetch as never,
    });

    renderAt(`/app/store/orders/${ORDER_ID}`);

    expect(screen.getByRole("alert")).toHaveTextContent(
      /order failed to load/i,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/order disappeared/i);

    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(refetch).toHaveBeenCalledTimes(1);
  });

  it("renders not-found state when the query returns no order data", () => {
    mockOrderQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: undefined,
      error: null,
    });

    renderAt(`/app/store/orders/${ORDER_ID}`);

    expect(screen.getByText(/order not found/i)).toBeInTheDocument();
    expect(
      screen.getByText(/we couldn't find this order/i),
    ).toBeInTheDocument();
  });
});

describe("OrderDetailPage - success detail", () => {
  it("renders backend summary fields verbatim and mounts actions/audit child surfaces", () => {
    const order = makeOrder();
    mockOrderQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: order,
      error: null,
    });

    renderAt(`/app/store/orders/${order.id}`);

    expect(screen.getByText(order.id)).toBeInTheDocument();
    expect(screen.getByText("Preparing")).toBeInTheDocument();
    expect(screen.getByText(order.customer_user_id as string)).toBeInTheDocument();
    expect(screen.getAllByText("28.50").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("1.99")).toBeInTheDocument();
    expect(screen.getByText("30.49")).toBeInTheDocument();
    expect(screen.getByText("detail-page-idempotency-key")).toBeInTheDocument();
    expect(screen.getByText("Leave by the side counter")).toBeInTheDocument();
    expect(screen.getByText("2026-05-01T12:00:00Z")).toBeInTheDocument();
    expect(screen.getByText("2026-05-01T12:05:00Z")).toBeInTheDocument();

    expect(screen.getByTestId("mock-order-actions-bar")).toHaveAttribute(
      "data-order-id",
      order.id,
    );
    expect(screen.getByTestId("mock-order-audit-logs-panel")).toHaveAttribute(
      "data-order-id",
      order.id,
    );
    expect(screen.getByTestId("order-detail-back")).toHaveAttribute(
      "href",
      "/app/store/orders",
    );
  });

  it("renders the empty items state when backend items are empty", () => {
    mockOrderQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeOrder({ items: [] }),
      error: null,
    });

    renderAt(`/app/store/orders/${ORDER_ID}`);

    expect(screen.getByText(/no items/i)).toBeInTheDocument();
    expect(
      screen.getByText(/this order has no line items/i),
    ).toBeInTheDocument();
  });

  it("uses operator-friendly summary labels, not debug field names (F2.26.4.D)", () => {
    mockOrderQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeOrder(),
      error: null,
    });

    renderAt(`/app/store/orders/${ORDER_ID}`);

    expect(screen.getByText("Customer")).toBeInTheDocument();
    expect(screen.queryByText(/customer user id/i)).not.toBeInTheDocument();
    expect(screen.getByText("Order reference")).toBeInTheDocument();
    expect(screen.queryByText(/idempotency key/i)).not.toBeInTheDocument();
  });

  it("renders populated item rows using backend line item fields", () => {
    const item = makeOrderItem();
    mockOrderQuery({
      isLoading: false,
      isError: false,
      isSuccess: true,
      data: makeOrder({ items: [item] }),
      error: null,
    });

    renderAt(`/app/store/orders/${ORDER_ID}`);

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows).toHaveLength(1);

    expect(within(rows[0]).getByText("Aurora Tea")).toBeInTheDocument();
    expect(within(rows[0]).getByText("TEA-MINT-12OZ")).toBeInTheDocument();
    expect(within(rows[0]).getByText("Mint")).toBeInTheDocument();
    expect(within(rows[0]).getByText("12 oz")).toBeInTheDocument();
    expect(within(rows[0]).getByText("3")).toBeInTheDocument();
    expect(within(rows[0]).getByText("9.50")).toBeInTheDocument();
    expect(within(rows[0]).getByText("28.50")).toBeInTheDocument();
  });
});

describe("OrderDetailPage - architecture", () => {
  it("does NOT recompute totals or own transition validity", async () => {
    const code = await readRuntimeSource("OrderDetailPage.tsx");

    expect(code).not.toMatch(/subtotal_amount\s*[-+*/]/);
    expect(code).not.toMatch(/tax_amount\s*[-+*/]/);
    expect(code).not.toMatch(/total_amount\s*[-+*/]/);
    expect(code).not.toMatch(/unit_price\s*[-+*/]/);
    expect(code).not.toMatch(/line_total\s*[-+*/]/);
    expect(code).not.toMatch(/_ALLOWED_TRANSITIONS\s*=/);
    expect(code).not.toMatch(/transitionMatrix\s*=/);
    expect(code).not.toMatch(/canTransitionTo\s*\(/);
    expect(code).not.toMatch(/isTransitionAllowed\s*\(/);
  });

  it("does NOT import auth, role checks, permission helpers, fetch, or axios", async () => {
    const code = await readRuntimeSource("OrderDetailPage.tsx");

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

  it("delegates audit display instead of deriving audit logs locally", async () => {
    const code = await readRuntimeSource("OrderDetailPage.tsx");

    expect(code).not.toMatch(/\buseOrderAuditLogs\b/);
    expect(code).not.toMatch(/\bOrderAuditLogRead\b/);
    expect(code).not.toMatch(/auditLogs\s*\.\s*map\s*\(/);
    expect(code).not.toMatch(/\bprevious_status\b/);
    expect(code).not.toMatch(/\bnew_status\b/);
  });
});
