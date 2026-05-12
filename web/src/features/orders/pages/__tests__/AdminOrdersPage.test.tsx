// F2.18.5: tests for the real Admin Orders page.
//
// Same shape as AdminInventoryPage.test.tsx — stub hooks, render
// plain (no router wrapper needed), exercise filters/pagination/
// read-only guards.
//
// Coverage:
//   - Page header copy (admin-scoped).
//   - Default filters {limit: 50, offset: 0}.
//   - Loading / error / empty / data states.
//   - Filter changes feed back into useAdminOrdersQuery.
//   - `q` input is ABSENT from the DOM.
//   - `q` is NOT serialized into the filter snapshot.
//   - Pagination bounds + advance.
//   - Read-only enforcement.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { UseQueryResult } from "@tanstack/react-query";

import AdminOrdersPage from "../AdminOrdersPage";
import * as ordersHooks from "../../hooks";
import type {
  AdminOrdersFilters,
  OrderRead,
  OrdersListResponse,
} from "../../types";

vi.mock("../../hooks", () => ({
  useAdminOrdersQuery: vi.fn(),
  useOrdersList: vi.fn(),
  useOrder: vi.fn(),
  useOrderAuditLogs: vi.fn(),
  useCreateOrderMutation: vi.fn(),
  useTransitionOrderStatusMutation: vi.fn(),
  useCancelOrderMutation: vi.fn(),
  useReturnOrderMutation: vi.fn(),
  ordersKeys: { all: ["orders"] as const },
}));

const STORE_A_ID = "11111111-1111-1111-1111-111111111111";
const ORDER_ID = "44444444-4444-4444-4444-444444444444";

function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return {
    refetch: vi.fn(),
    ...partial,
  } as unknown as UseQueryResult<TData>;
}

function makeOrder(overrides: Partial<OrderRead> = {}): OrderRead {
  return {
    id: ORDER_ID,
    store_id: STORE_A_ID,
    customer_user_id: null,
    idempotency_key: "key-1",
    status: "pending",
    subtotal_amount: "9.00",
    tax_amount: "1.00",
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
    updated_at: "2026-05-02T00:00:00Z",
    items: [],
    ...overrides,
  };
}

function makeListResponse(
  items: OrderRead[],
  overrides: Partial<OrdersListResponse> = {},
): OrdersListResponse {
  return {
    items,
    total: items.length,
    limit: 50,
    offset: 0,
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(ordersHooks.useAdminOrdersQuery).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Chrome
// --------------------------------------------------------------------- //

describe("AdminOrdersPage — chrome", () => {
  beforeEach(() => {
    vi.mocked(ordersHooks.useAdminOrdersQuery).mockReturnValue(
      asQueryResult<OrdersListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([]),
      }),
    );
  });

  it("renders the page heading 'Orders'", () => {
    render(<AdminOrdersPage />);
    expect(
      screen.getByRole("heading", { level: 1, name: "Orders" }),
    ).toBeInTheDocument();
  });

  it("renders the admin-scope description", () => {
    render(<AdminOrdersPage />);
    expect(
      screen.getByText(
        /Orders across every store in the NubeRush platform\./,
      ),
    ).toBeInTheDocument();
  });

  it("calls useAdminOrdersQuery with default filters {limit: 50, offset: 0}", () => {
    render(<AdminOrdersPage />);
    const lastCall = vi
      .mocked(ordersHooks.useAdminOrdersQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({ limit: 50, offset: 0 });
  });
});

// --------------------------------------------------------------------- //
// Query states
// --------------------------------------------------------------------- //

describe("AdminOrdersPage — query states", () => {
  it("renders the loading state", () => {
    vi.mocked(ordersHooks.useAdminOrdersQuery).mockReturnValue(
      asQueryResult<OrdersListResponse>({
        isLoading: true,
        isFetching: true,
        isError: false,
        isSuccess: false,
      }),
    );
    render(<AdminOrdersPage />);
    expect(screen.getByText(/loading orders/i)).toBeInTheDocument();
  });

  it("renders the error state and retry", () => {
    const refetch = vi.fn();
    vi.mocked(ordersHooks.useAdminOrdersQuery).mockReturnValue(
      asQueryResult<OrdersListResponse>({
        isLoading: false,
        isFetching: false,
        isError: true,
        isSuccess: false,
        error: new Error("forbidden"),
        refetch: refetch as never,
      }),
    );
    render(<AdminOrdersPage />);
    expect(screen.getByText("Could not load orders")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalled();
  });

  it("renders the empty state when items is empty", () => {
    vi.mocked(ordersHooks.useAdminOrdersQuery).mockReturnValue(
      asQueryResult<OrdersListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([]),
      }),
    );
    render(<AdminOrdersPage />);
    expect(screen.getByText("No orders found")).toBeInTheDocument();
    expect(
      screen.queryByTestId("admin-orders-pagination"),
    ).not.toBeInTheDocument();
  });

  it("renders rows when items is non-empty", () => {
    vi.mocked(ordersHooks.useAdminOrdersQuery).mockReturnValue(
      asQueryResult<OrdersListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeOrder()], { total: 1 }),
      }),
    );
    render(<AdminOrdersPage />);
    expect(screen.getByTestId("admin-orders-row")).toBeInTheDocument();
    expect(screen.getByTestId("admin-orders-row-status")).toHaveTextContent(
      "pending",
    );
    expect(screen.getByTestId("admin-orders-row-total")).toHaveTextContent(
      "10.00",
    );
  });

  it("renders the total count when there are items", () => {
    vi.mocked(ordersHooks.useAdminOrdersQuery).mockReturnValue(
      asQueryResult<OrdersListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeOrder()], { total: 42 }),
      }),
    );
    render(<AdminOrdersPage />);
    expect(screen.getByTestId("admin-orders-total")).toHaveTextContent(
      "Total: 42",
    );
  });
});

// --------------------------------------------------------------------- //
// Filters
// --------------------------------------------------------------------- //

describe("AdminOrdersPage — filters", () => {
  beforeEach(() => {
    vi.mocked(ordersHooks.useAdminOrdersQuery).mockReturnValue(
      asQueryResult<OrdersListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([]),
      }),
    );
  });

  it("typing store_id forwards the value", () => {
    render(<AdminOrdersPage />);
    fireEvent.change(
      screen.getByTestId("admin-orders-filter-store-id"),
      { target: { value: STORE_A_ID } },
    );
    const lastCall = vi
      .mocked(ordersHooks.useAdminOrdersQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({ store_id: STORE_A_ID });
  });

  it("clearing store_id drops the key", () => {
    render(<AdminOrdersPage />);
    fireEvent.change(
      screen.getByTestId("admin-orders-filter-store-id"),
      { target: { value: STORE_A_ID } },
    );
    fireEvent.change(
      screen.getByTestId("admin-orders-filter-store-id"),
      { target: { value: "" } },
    );
    const lastCall = vi
      .mocked(ordersHooks.useAdminOrdersQuery)
      .mock.calls.at(-1);
    expect(
      (lastCall?.[0] as AdminOrdersFilters | undefined)?.store_id,
    ).toBeUndefined();
  });

  it("typing date_from and date_to forwards both", () => {
    render(<AdminOrdersPage />);
    fireEvent.change(
      screen.getByTestId("admin-orders-filter-date-from"),
      { target: { value: "2026-01-01" } },
    );
    fireEvent.change(
      screen.getByTestId("admin-orders-filter-date-to"),
      { target: { value: "2026-12-31" } },
    );
    const lastCall = vi
      .mocked(ordersHooks.useAdminOrdersQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({
      date_from: "2026-01-01",
      date_to: "2026-12-31",
    });
  });

  it("does NOT render a `q` search input on the admin orders page", () => {
    render(<AdminOrdersPage />);
    // Test-id naming convention used by the inventory page would be
    // `admin-orders-filter-q` if it existed. It must not.
    expect(
      screen.queryByTestId("admin-orders-filter-q"),
    ).not.toBeInTheDocument();
    // Belt-and-braces: no input placeholder hints at search either.
    expect(screen.queryByPlaceholderText(/search/i)).not.toBeInTheDocument();
  });

  it("does NOT serialize `q` into the filter snapshot regardless of UI interactions", () => {
    render(<AdminOrdersPage />);
    // Drive every supported filter — the resulting snapshot must
    // never contain a `q` key.
    fireEvent.change(
      screen.getByTestId("admin-orders-filter-store-id"),
      { target: { value: STORE_A_ID } },
    );
    fireEvent.change(
      screen.getByTestId("admin-orders-filter-date-from"),
      { target: { value: "2026-01-01" } },
    );
    for (const call of vi.mocked(ordersHooks.useAdminOrdersQuery).mock
      .calls) {
      const snap = call[0] as
        | (AdminOrdersFilters & { q?: unknown })
        | undefined;
      expect(snap?.q).toBeUndefined();
    }
  });
});

// --------------------------------------------------------------------- //
// Pagination
// --------------------------------------------------------------------- //

describe("AdminOrdersPage — pagination", () => {
  it("Previous disabled at first page; Next enabled when more rows", () => {
    vi.mocked(ordersHooks.useAdminOrdersQuery).mockReturnValue(
      asQueryResult<OrdersListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeOrder()], { total: 200, limit: 50, offset: 0 }),
      }),
    );
    render(<AdminOrdersPage />);
    expect(
      screen.getByTestId("admin-orders-pagination-prev"),
    ).toBeDisabled();
    expect(
      screen.getByTestId("admin-orders-pagination-next"),
    ).not.toBeDisabled();
  });

  it("Next disabled on the last page", () => {
    vi.mocked(ordersHooks.useAdminOrdersQuery).mockReturnValue(
      asQueryResult<OrdersListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeOrder()], { total: 50, limit: 50, offset: 0 }),
      }),
    );
    render(<AdminOrdersPage />);
    expect(
      screen.getByTestId("admin-orders-pagination-next"),
    ).toBeDisabled();
  });

  it("clicking Next advances offset by limit", () => {
    vi.mocked(ordersHooks.useAdminOrdersQuery).mockReturnValue(
      asQueryResult<OrdersListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeOrder()], { total: 200, limit: 50, offset: 0 }),
      }),
    );
    render(<AdminOrdersPage />);
    fireEvent.click(screen.getByTestId("admin-orders-pagination-next"));
    const lastCall = vi
      .mocked(ordersHooks.useAdminOrdersQuery)
      .mock.calls.at(-1);
    expect(lastCall?.[0]?.offset).toBe(50);
  });
});

// --------------------------------------------------------------------- //
// Read-only enforcement
// --------------------------------------------------------------------- //

describe("AdminOrdersPage — read-only", () => {
  it("renders no mutation buttons", () => {
    vi.mocked(ordersHooks.useAdminOrdersQuery).mockReturnValue(
      asQueryResult<OrdersListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([makeOrder()], { total: 1 }),
      }),
    );
    render(<AdminOrdersPage />);
    for (const label of [
      /create order/i,
      /cancel/i,
      /return/i,
      /transition/i,
      /update status/i,
    ]) {
      expect(screen.queryByRole("button", { name: label })).toBeNull();
    }
  });

  it("does not invoke any store-scoped orders mutation hook", () => {
    vi.mocked(ordersHooks.useAdminOrdersQuery).mockReturnValue(
      asQueryResult<OrdersListResponse>({
        isLoading: false,
        isFetching: false,
        isError: false,
        isSuccess: true,
        data: makeListResponse([]),
      }),
    );
    render(<AdminOrdersPage />);
    expect(ordersHooks.useCreateOrderMutation).not.toHaveBeenCalled();
    expect(
      ordersHooks.useTransitionOrderStatusMutation,
    ).not.toHaveBeenCalled();
    expect(ordersHooks.useCancelOrderMutation).not.toHaveBeenCalled();
    expect(ordersHooks.useReturnOrderMutation).not.toHaveBeenCalled();
    expect(ordersHooks.useOrdersList).not.toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------- //
// Architecture guard
// --------------------------------------------------------------------- //

describe("AdminOrdersPage — architecture", () => {
  it("does NOT import useAuth / useStoreContext / store-scoped hooks / fetch / axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "AdminOrdersPage.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\bcurrentUser\b/);
    expect(code).not.toMatch(/\buseStoreContext\b/);
    expect(code).not.toMatch(/\buseOrdersList\b/);
    expect(code).not.toMatch(/\bgetOrdersList\b/);
    expect(code).not.toMatch(/\bgetAdminOrders\b/);
    expect(code).not.toMatch(/\bhasPermission\b/);
    expect(code).not.toMatch(/\.role\s*===\s*["']/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
    expect(code).not.toMatch(/apiRequest/);
  });
});
