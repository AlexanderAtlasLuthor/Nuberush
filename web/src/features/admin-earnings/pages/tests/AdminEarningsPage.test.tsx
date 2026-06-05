// AdminEarningsPage render tests.
//
// We mock the read hook so each test pins exactly one query state
// (pending / error / success) and exercises the page's rendering
// contract: the page is a pure projection of the wire shape.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import * as adminEarningsHooks from "../../hooks";
import type {
  AdminEarningsStoreBreakdown,
  AdminEarningsSummary,
} from "../../types";
import AdminEarningsPage from "../AdminEarningsPage";

vi.mock("../../hooks", () => ({
  useAdminEarningsQuery: vi.fn(),
}));

function asQueryResult(
  partial: Partial<UseQueryResult<AdminEarningsSummary>>,
): UseQueryResult<AdminEarningsSummary> {
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
  } as unknown as UseQueryResult<AdminEarningsSummary>;
}

function makeRow(
  overrides: Partial<AdminEarningsStoreBreakdown> = {},
): AdminEarningsStoreBreakdown {
  return {
    store_id: "00000000-0000-0000-0000-000000000001",
    store_name: "Store A",
    delivered_orders: 1,
    gross_base: "100.00",
    commission: "20.00",
    ...overrides,
  };
}

function makeSummary(
  overrides: Partial<AdminEarningsSummary> = {},
): AdminEarningsSummary {
  return {
    delivered_orders: 0,
    subtotal_total: "0.00",
    delivery_total: "0.00",
    tip_total: "0.00",
    tax_total: "0.00",
    gross_base_total: "0.00",
    commission_total: "0.00",
    customer_paid_total: "0.00",
    commission_rate: "0.20",
    delivery_fee: "10.00",
    by_store: [],
    ...overrides,
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/app/admin/earnings"]}>
      <AdminEarningsPage />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("AdminEarningsPage — query states", () => {
  it("shows a loading state while the query is pending", () => {
    vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReturnValue(
      asQueryResult({ isPending: true, isLoading: true }),
    );
    renderPage();
    expect(
      screen.getByTestId("admin-earnings-loading"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("admin-earnings-commission"),
    ).not.toBeInTheDocument();
  });

  it("shows an error state with a working Retry button", () => {
    const refetch = vi.fn();
    vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReturnValue(
      asQueryResult({
        isError: true,
        error: new Error("nope") as unknown as Error,
        refetch,
      }),
    );
    renderPage();
    expect(
      screen.getByTestId("admin-earnings-error"),
    ).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("admin-earnings-retry"));
    expect(refetch).toHaveBeenCalledTimes(1);
  });
});

describe("AdminEarningsPage — populated state", () => {
  it("renders the four headline money tiles with backend values", () => {
    vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeSummary({
          delivered_orders: 5,
          subtotal_total: "500.00",
          delivery_total: "50.00",
          tax_total: "40.00",
          tip_total: "0.00",
          gross_base_total: "590.00",
          commission_total: "118.00",
          customer_paid_total: "708.00",
        }),
      }),
    );
    renderPage();

    expect(screen.getByTestId("admin-earnings-commission")).toHaveTextContent(
      /118\.00/,
    );
    expect(screen.getByTestId("admin-earnings-commission")).toHaveTextContent(
      /5 delivered orders/,
    );
    expect(screen.getByTestId("admin-earnings-subtotal")).toHaveTextContent(
      /500\.00/,
    );
    expect(screen.getByTestId("admin-earnings-delivery")).toHaveTextContent(
      /50\.00/,
    );
    expect(screen.getByTestId("admin-earnings-tax")).toHaveTextContent(
      /40\.00/,
    );
  });

  it("renders gross_base, customer_paid, and tip tiles", () => {
    vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeSummary({
          gross_base_total: "590.00",
          customer_paid_total: "708.00",
          tip_total: "0.00",
        }),
      }),
    );
    renderPage();
    expect(
      screen.getByTestId("admin-earnings-gross-base"),
    ).toHaveTextContent(/590\.00/);
    expect(
      screen.getByTestId("admin-earnings-customer-paid"),
    ).toHaveTextContent(/708\.00/);
    expect(screen.getByTestId("admin-earnings-tip")).toHaveTextContent(
      /0\.00/,
    );
  });

  it("renders an empty state when there are no by_store rows", () => {
    vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeSummary({ by_store: [] }),
      }),
    );
    renderPage();
    expect(
      screen.getByTestId("admin-earnings-by-store-empty"),
    ).toHaveTextContent(/no delivered orders yet/i);
  });

  it("renders the by_store breakdown table with one row per store", () => {
    const rows: AdminEarningsStoreBreakdown[] = [
      makeRow({
        store_id: "aaaa1111-1111-1111-1111-111111111111",
        store_name: "Big",
        delivered_orders: 2,
        gross_base: "220.00",
        commission: "44.00",
      }),
      makeRow({
        store_id: "bbbb2222-2222-2222-2222-222222222222",
        store_name: "Small",
        delivered_orders: 1,
        gross_base: "20.00",
        commission: "4.00",
      }),
    ];
    vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeSummary({ by_store: rows }),
      }),
    );
    renderPage();
    const big = screen.getByTestId(
      "admin-earnings-row-aaaa1111-1111-1111-1111-111111111111",
    );
    expect(within(big).getByText("Big")).toBeInTheDocument();
    expect(big).toHaveTextContent(/2/);
    expect(big).toHaveTextContent(/220\.00/);
    expect(big).toHaveTextContent(/44\.00/);

    const small = screen.getByTestId(
      "admin-earnings-row-bbbb2222-2222-2222-2222-222222222222",
    );
    expect(within(small).getByText("Small")).toBeInTheDocument();
    expect(small).toHaveTextContent(/4\.00/);
  });
});

describe("AdminEarningsPage — pre-Stripe framing (F2.26.4.A)", () => {
  it("renders the projected / Stripe-pending disclaimer with all three facts", () => {
    vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );
    renderPage();
    const disclaimer = screen.getByTestId("admin-earnings-disclaimer");
    // (1) projected/internal accounting, (2) Stripe not enabled,
    // (3) no funds charged or paid out.
    expect(disclaimer).toHaveTextContent(/projected internal accounting/i);
    expect(disclaimer).toHaveTextContent(/stripe/i);
    expect(disclaimer).toHaveTextContent(/no funds.*charged or paid out/i);
  });

  it("frames the commission headline as projected, not earned", () => {
    vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReturnValue(
      asQueryResult({
        isSuccess: true,
        data: makeSummary({ delivered_orders: 1, commission_total: "20.00" }),
      }),
    );
    renderPage();
    // Same data still renders; only the framing changed.
    expect(screen.getByTestId("admin-earnings-commission")).toHaveTextContent(
      /projected platform commission/i,
    );
    expect(screen.getByTestId("admin-earnings-commission")).toHaveTextContent(
      /20\.00/,
    );
  });

  it("does not present real-money labels as user-facing copy", () => {
    vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );
    renderPage();
    expect(screen.queryByText("Customer paid")).not.toBeInTheDocument();
    expect(screen.queryByText("Commission earned")).not.toBeInTheDocument();
    expect(
      screen.queryByText(/customers were charged/i),
    ).not.toBeInTheDocument();
    expect(screen.queryByText("Delivery collected")).not.toBeInTheDocument();
    expect(screen.queryByText("Taxes collected")).not.toBeInTheDocument();
    expect(screen.queryByText("Tips collected")).not.toBeInTheDocument();
  });
});
