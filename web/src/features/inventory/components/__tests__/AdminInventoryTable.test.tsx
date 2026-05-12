// F2.18.5: tests for AdminInventoryTable.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { AdminInventoryTable } from "../AdminInventoryTable";
import type { InventoryItem } from "../../types";

function makeItem(overrides: Partial<InventoryItem> = {}): InventoryItem {
  return {
    id: "item-1",
    store_id: "11111111-1111-1111-1111-111111111111",
    variant_id: "33333333-3333-3333-3333-333333333333",
    quantity_on_hand: 8,
    quantity_reserved: 2,
    reorder_threshold: 5,
    status: "available",
    last_counted_at: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-02-01T00:00:00Z",
    variant: {
      id: "33333333-3333-3333-3333-333333333333",
      sku: "SKU-1",
      flavor: null,
      size_label: null,
      is_active: true,
      product: {
        id: "22222222-2222-2222-2222-222222222222",
        name: "Test Product",
      } as InventoryItem["variant"]["product"],
    },
    ...overrides,
  };
}

describe("AdminInventoryTable", () => {
  it("renders the loading state", () => {
    render(<AdminInventoryTable items={[]} isLoading />);
    expect(screen.getByText(/loading inventory/i)).toBeInTheDocument();
  });

  it("renders the error state with retry", () => {
    const retry = vi.fn();
    render(
      <AdminInventoryTable
        items={[]}
        error={new Error("boom")}
        onRetry={retry}
      />,
    );
    expect(screen.getByText("Could not load inventory")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(retry).toHaveBeenCalled();
  });

  it("renders the empty state", () => {
    render(<AdminInventoryTable items={[]} />);
    expect(screen.getByText("No inventory found")).toBeInTheDocument();
  });

  it("renders rows with product / sku / stock columns", () => {
    render(<AdminInventoryTable items={[makeItem()]} />);
    const row = screen.getByTestId("admin-inventory-row");
    expect(within(row).getByText("Test Product")).toBeInTheDocument();
    expect(within(row).getByText("SKU-1")).toBeInTheDocument();
    expect(
      within(row).getByTestId("admin-inventory-row-on-hand"),
    ).toHaveTextContent("8");
    expect(
      within(row).getByTestId("admin-inventory-row-reserved"),
    ).toHaveTextContent("2");
    expect(
      within(row).getByTestId("admin-inventory-row-threshold"),
    ).toHaveTextContent("5");
    expect(
      within(row).getByTestId("admin-inventory-row-status"),
    ).toHaveTextContent("available");
  });

  it("renders no actions column (read-only)", () => {
    render(<AdminInventoryTable items={[makeItem()]} />);
    expect(
      screen.queryByRole("button", { name: /receive|adjust|damage/i }),
    ).toBeNull();
  });
});
