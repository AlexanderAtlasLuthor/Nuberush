// AdminEarningsWidget render tests.
//
// Strategy: mock the read hook so we control every render state
// (pending / error / success), then assert what is on the DOM. The
// widget itself owns no fetching, no math, no derivations — it only
// projects the wire fields onto MoneyTile children.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { UseQueryResult } from "@tanstack/react-query";

import * as adminEarningsHooks from "../hooks";
import type { AdminEarningsSummary } from "../types";
import { AdminEarningsWidget } from "./AdminEarningsWidget";

vi.mock("../hooks", () => ({
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

function makeSummary(
  overrides: Partial<AdminEarningsSummary> = {},
): AdminEarningsSummary {
  return {
    delivered_orders: 4,
    subtotal_total: "400.00",
    delivery_total: "40.00",
    tip_total: "0.00",
    tax_total: "32.00",
    gross_base_total: "472.00",
    commission_total: "94.40",
    customer_paid_total: "566.40",
    commission_rate: "0.20",
    delivery_fee: "10.00",
    by_store: [],
    ...overrides,
  };
}

function renderWidget() {
  return render(
    <MemoryRouter initialEntries={["/app/admin"]}>
      <AdminEarningsWidget />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("AdminEarningsWidget", () => {
  it("renders a loading message while the query is pending", () => {
    vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReturnValue(
      asQueryResult({ isPending: true, isLoading: true }),
    );
    renderWidget();

    expect(
      screen.getByTestId("admin-earnings-widget-loading"),
    ).toHaveTextContent(/loading earnings/i);
    expect(
      screen.queryByTestId("admin-earnings-widget-commission"),
    ).not.toBeInTheDocument();
  });

  it("renders an error message when the query errors", () => {
    vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReturnValue(
      asQueryResult({
        isError: true,
        error: new Error("boom") as unknown as Error,
      }),
    );
    renderWidget();

    expect(
      screen.getByTestId("admin-earnings-widget-error"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("admin-earnings-widget-commission"),
    ).not.toBeInTheDocument();
  });

  it("renders the three money tiles with backend values", () => {
    const summary = makeSummary();
    vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: summary }),
    );
    renderWidget();

    // Money values render via the shared MoneyTile (formatUsd applies);
    // we only assert the numeric body of each tile so a future format
    // tweak doesn't have to update three assertions.
    const commission = screen.getByTestId(
      "admin-earnings-widget-commission",
    );
    expect(commission).toHaveTextContent(/94\.40/);
    expect(commission).toHaveTextContent(/4 delivered orders/);

    const gross = screen.getByTestId("admin-earnings-widget-gross-base");
    expect(gross).toHaveTextContent(/472\.00/);

    const customerPaid = screen.getByTestId(
      "admin-earnings-widget-customer-paid",
    );
    expect(customerPaid).toHaveTextContent(/566\.40/);
    // Average = 566.40 / 4 = 141.60.
    expect(customerPaid).toHaveTextContent(/141\.60/);
  });

  it("avoids dividing by zero when there are no delivered orders", () => {
    const summary = makeSummary({
      delivered_orders: 0,
      customer_paid_total: "0.00",
      commission_total: "0.00",
      gross_base_total: "0.00",
    });
    vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: summary }),
    );
    renderWidget();

    const customerPaid = screen.getByTestId(
      "admin-earnings-widget-customer-paid",
    );
    // Description prints `Avg $0.00 per order`, not "NaN" / "Infinity".
    expect(customerPaid).toHaveTextContent(/avg.*\$0\.00.*per order/i);
  });

  it("links the 'View details' affordance to the admin earnings page", () => {
    vi.mocked(adminEarningsHooks.useAdminEarningsQuery).mockReturnValue(
      asQueryResult({ isSuccess: true, data: makeSummary() }),
    );
    renderWidget();

    const link = screen.getByTestId("admin-earnings-widget-link");
    expect(link).toHaveAttribute("href", "/app/admin/earnings");
  });
});
