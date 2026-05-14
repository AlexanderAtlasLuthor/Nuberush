// StoreEarningsPage render tests.
//
// Mocks both `useStoreContext` (so we control the store id the page
// derives) and the read hook (so each test pins one query state).

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import * as authModule from "@/auth";

import * as storeEarningsHooks from "../../hooks";
import type {
  StoreEarningsSummary,
  StoreEarningsTopProduct,
} from "../../types";
import StoreEarningsPage from "../StoreEarningsPage";

vi.mock("@/auth", async () => {
  const actual = await vi.importActual<typeof import("@/auth")>("@/auth");
  return {
    ...actual,
    useStoreContext: vi.fn(),
  };
});

vi.mock("../../hooks", () => ({
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

function makeTopProduct(
  overrides: Partial<StoreEarningsTopProduct> = {},
): StoreEarningsTopProduct {
  return {
    variant_id: "v0",
    product_name: "Product",
    variant_label: null,
    quantity_sold: 1,
    revenue: "10.00",
    ...overrides,
  };
}

function makeSummary(
  overrides: Partial<StoreEarningsSummary> = {},
): StoreEarningsSummary {
  return {
    delivered_orders: 0,
    total_items_sold: 0,
    product_revenue: "0.00",
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

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/app/store/earnings"]}>
      <StoreEarningsPage />
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

describe("StoreEarningsPage — guard states", () => {
  it("shows a 'no store selected' message when storeId is null", () => {
    mockStoreContext(null);
    vi.mocked(storeEarningsHooks.useStoreEarningsQuery).mockReturnValue(
      asQueryResult({ isPending: true, fetchStatus: "idle" } as never),
    );
    renderPage();
    expect(
      screen.getByTestId("store-earnings-no-store"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("store-earnings-loading"),
    ).not.toBeInTheDocument();
  });

  it("shows a loading state when storeId exists and query is pending", () => {
    mockStoreContext(STORE_ID);
    vi.mocked(storeEarningsHooks.useStoreEarningsQuery).mockReturnValue(
      asQueryResult({ isPending: true }),
    );
    renderPage();
    expect(
      screen.getByTestId("store-earnings-loading"),
    ).toBeInTheDocument();
  });

  it("shows an error state with a working Retry button", () => {
    mockStoreContext(STORE_ID);
    const refetch = vi.fn();
    vi.mocked(storeEarningsHooks.useStoreEarningsQuery).mockReturnValue(
      asQueryResult({
        isError: true,
        error: new Error("nope") as unknown as Error,
        refetch,
      }),
    );
    renderPage();
    expect(
      screen.getByTestId("store-earnings-error"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("store-earnings-retry"));
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});

describe("StoreEarningsPage — populated state", () => {
  beforeEach(() => mockStoreContext(STORE_ID));

  it("renders revenue, items, and avg tiles", () => {
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
    renderPage();
    expect(screen.getByTestId("store-earnings-revenue")).toHaveTextContent(
      /240\.00/,
    );
    expect(screen.getByTestId("store-earnings-revenue")).toHaveTextContent(
      /from 4 delivered orders/i,
    );
    expect(screen.getByTestId("store-earnings-items")).toHaveTextContent(
      /12/,
    );
    expect(screen.getByTestId("store-earnings-avg")).toHaveTextContent(
      /60\.00/,
    );
  });

  it("renders an empty top-products state when none exist", () => {
    vi.mocked(storeEarningsHooks.useStoreEarningsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeSummary({ top_products: [] }),
      }),
    );
    renderPage();
    expect(
      screen.getByTestId("store-earnings-top-products-empty"),
    ).toHaveTextContent(/no products sold yet/i);
  });

  it("renders one row per top product, falling back to em-dash for null variant_label", () => {
    const rows = [
      makeTopProduct({
        variant_id: "vA",
        product_name: "Mango",
        variant_label: "5000 puffs",
        quantity_sold: 2,
        revenue: "100.00",
      }),
      makeTopProduct({
        variant_id: "vB",
        product_name: "Plain",
        variant_label: null,
        quantity_sold: 5,
        revenue: "5.00",
      }),
    ];
    vi.mocked(storeEarningsHooks.useStoreEarningsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeSummary({
          delivered_orders: 3,
          total_items_sold: 7,
          product_revenue: "105.00",
          top_products: rows,
        }),
      }),
    );
    renderPage();

    const mango = screen.getByTestId("store-earnings-row-vA");
    expect(within(mango).getByText("Mango")).toBeInTheDocument();
    expect(mango).toHaveTextContent(/5000 puffs/);
    expect(mango).toHaveTextContent(/100\.00/);

    const plain = screen.getByTestId("store-earnings-row-vB");
    expect(within(plain).getByText("Plain")).toBeInTheDocument();
    // variant_label === null renders the em-dash placeholder.
    expect(plain).toHaveTextContent("—");
  });
});
