// F2.18.5: tests for AdminOrdersTable.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { AdminOrdersTable } from "../AdminOrdersTable";
import type { OrderRead } from "../../types";

function makeOrder(overrides: Partial<OrderRead> = {}): OrderRead {
  return {
    id: "44444444-4444-4444-4444-444444444444",
    store_id: "11111111-1111-1111-1111-111111111111",
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

describe("AdminOrdersTable", () => {
  it("renders the loading state", () => {
    render(<AdminOrdersTable orders={[]} isLoading />);
    expect(screen.getByText(/loading orders/i)).toBeInTheDocument();
  });

  it("renders the error state with retry", () => {
    const retry = vi.fn();
    render(
      <AdminOrdersTable
        orders={[]}
        error={new Error("boom")}
        onRetry={retry}
      />,
    );
    expect(screen.getByText("Could not load orders")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalled();
  });

  it("renders the empty state", () => {
    render(<AdminOrdersTable orders={[]} />);
    expect(screen.getByText("No orders found")).toBeInTheDocument();
  });

  it("renders rows with status / items / total / dates", () => {
    render(
      <AdminOrdersTable
        orders={[
          makeOrder({
            status: "delivered",
            total_amount: "42.50",
            items: [
              {
                id: "i-1",
              } as OrderRead["items"][number],
              {
                id: "i-2",
              } as OrderRead["items"][number],
            ],
          }),
        ]}
      />,
    );
    const row = screen.getByTestId("admin-orders-row");
    expect(
      within(row).getByTestId("admin-orders-row-status"),
    ).toHaveTextContent("delivered");
    expect(
      within(row).getByTestId("admin-orders-row-items"),
    ).toHaveTextContent("2");
    expect(
      within(row).getByTestId("admin-orders-row-total"),
    ).toHaveTextContent("42.50");
    expect(
      within(row).getByTestId("admin-orders-row-created"),
    ).toHaveTextContent("2026-05-01T00:00:00Z");
  });

  it("renders no actions column (read-only)", () => {
    render(<AdminOrdersTable orders={[makeOrder()]} />);
    expect(
      screen.queryByRole("button", { name: /cancel|return|transition/i }),
    ).toBeNull();
  });
});
