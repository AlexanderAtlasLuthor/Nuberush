// StoreEarningsWidget render tests.
//
// Strategy: mock both the read hook and `useStoreContext` so the widget
// renders deterministically. The page chrome (sidebar / providers) is
// not under test here — we only check the widget's projection of the
// wire fields plus the divide-by-zero guard.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import * as authModule from "@/auth";

import * as storeEarningsHooks from "../hooks";
import type { StoreEarningsSummary } from "../types";
import { StoreEarningsWidget } from "./StoreEarningsWidget";

vi.mock("@/auth", async () => {
  const actual = await vi.importActual<typeof import("@/auth")>("@/auth");
  return {
    ...actual,
    useStoreContext: vi.fn(),
  };
});

vi.mock("../hooks", () => ({
  useStoreEarningsQuery: vi.fn(),
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";

function asQueryResult(
  partial: Partial<UseQueryResult<StoreEarningsSummary>>,
): UseQueryResult<StoreEarningsSummary> {
  return {
    isPending: false,
    isLoading: false,
    isFetching: false,
    isError: false,
    isSuccess: false,
    data: undefined,
    error: null,
    refetch: vi.fn(),
    ...partial,
  } as unknown as UseQueryResult<StoreEarningsSummary>;
}

function makeSummary(
  overrides: Partial<StoreEarningsSummary> = {},
): StoreEarningsSummary {
  return {
    delivered_orders: 4,
    total_items_sold: 12,
    product_revenue: "240.00",
    top_products: [],
    ...overrides,
  };
}

function mockStoreContext(currentStoreId: string | null) {
  vi.mocked(authModule.useStoreContext).mockReturnValue({
    currentStoreId,
    hasStoreContext: currentStoreId !== null,
    isStoreRequired: false,
    storeError: null,
  });
}

function renderWidget() {
  return render(
    <MemoryRouter initialEntries={["/app/store"]}>
      <StoreEarningsWidget />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(storeEarningsHooks.useStoreEarningsQuery).mockReset();
  vi.mocked(authModule.useStoreContext).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("StoreEarningsWidget", () => {
  it("passes the current store id to useStoreEarningsQuery", () => {
    mockStoreContext(STORE_ID);
    vi.mocked(storeEarningsHooks.useStoreEarningsQuery).mockReturnValue(
      asQueryResult({ isPending: true }),
    );
    renderWidget();
    expect(storeEarningsHooks.useStoreEarningsQuery).toHaveBeenCalledWith({
      storeId: STORE_ID,
    });
  });

  it("renders a loading message while the query is pending", () => {
    mockStoreContext(STORE_ID);
    vi.mocked(storeEarningsHooks.useStoreEarningsQuery).mockReturnValue(
      asQueryResult({ isPending: true }),
    );
    renderWidget();
    expect(
      screen.getByTestId("store-earnings-widget-loading"),
    ).toHaveTextContent(/loading earnings/i);
    expect(
      screen.queryByTestId("store-earnings-widget-revenue"),
    ).not.toBeInTheDocument();
  });

  it("renders an error message when the query errors", () => {
    mockStoreContext(STORE_ID);
    vi.mocked(storeEarningsHooks.useStoreEarningsQuery).mockReturnValue(
      asQueryResult({
        isError: true,
        error: new Error("nope") as unknown as Error,
      }),
    );
    renderWidget();
    expect(
      screen.getByTestId("store-earnings-widget-error"),
    ).toBeInTheDocument();
  });

  it("renders revenue, items sold, and avg per order on success", () => {
    mockStoreContext(STORE_ID);
    vi.mocked(storeEarningsHooks.useStoreEarningsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeSummary({
          delivered_orders: 4,
          total_items_sold: 12,
          product_revenue: "240.00",
        }),
      }),
    );
    renderWidget();

    expect(
      screen.getByTestId("store-earnings-widget-revenue"),
    ).toHaveTextContent(/240\.00/);
    expect(
      screen.getByTestId("store-earnings-widget-items"),
    ).toHaveTextContent(/12/);
    // Avg = 240 / 4 = 60.
    expect(
      screen.getByTestId("store-earnings-widget-avg"),
    ).toHaveTextContent(/60\.00/);
  });

  it("displays a no-orders fallback when delivered_orders is 0", () => {
    mockStoreContext(STORE_ID);
    vi.mocked(storeEarningsHooks.useStoreEarningsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeSummary({
          delivered_orders: 0,
          total_items_sold: 0,
          product_revenue: "0.00",
        }),
      }),
    );
    renderWidget();

    const avg = screen.getByTestId("store-earnings-widget-avg");
    expect(avg).toHaveTextContent(/no delivered orders yet/i);
  });

  it("links 'View details' to the store earnings page", () => {
    mockStoreContext(STORE_ID);
    vi.mocked(storeEarningsHooks.useStoreEarningsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );
    renderWidget();

    const link = screen.getByTestId("store-earnings-widget-link");
    expect(link).toHaveAttribute("href", "/app/store/earnings");
  });
});
