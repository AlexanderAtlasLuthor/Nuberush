// F2.18.5: tests for AdminInventoryFilters.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { AdminInventoryFilters } from "../AdminInventoryFilters";
import type { AdminInventoryFilters as AdminInventoryFiltersType } from "../../types";

describe("AdminInventoryFilters", () => {
  it("renders all 6 admin inventory filter controls", () => {
    render(
      <AdminInventoryFilters
        filters={{ limit: 100 }}
        onChange={vi.fn()}
      />,
    );
    for (const tid of [
      "admin-inventory-filter-store-id",
      "admin-inventory-filter-q",
      "admin-inventory-filter-status-trigger",
      "admin-inventory-filter-product-id",
      "admin-inventory-filter-variant-id",
      "admin-inventory-filter-low-stock",
    ]) {
      expect(screen.getByTestId(tid)).toBeInTheDocument();
    }
  });

  it("emits store_id when input has a non-empty value", () => {
    const onChange = vi.fn();
    render(
      <AdminInventoryFilters
        filters={{ limit: 100 }}
        onChange={onChange}
      />,
    );
    fireEvent.change(
      screen.getByTestId("admin-inventory-filter-store-id"),
      { target: { value: "store-uuid" } },
    );
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ store_id: "store-uuid" }),
    );
  });

  it("trims store_id and drops the key when only whitespace", () => {
    const onChange = vi.fn();
    render(
      <AdminInventoryFilters
        filters={{ limit: 100, store_id: "x" }}
        onChange={onChange}
      />,
    );
    fireEvent.change(
      screen.getByTestId("admin-inventory-filter-store-id"),
      { target: { value: "   " } },
    );
    const next = onChange.mock.calls.at(-1)?.[0] as
      | AdminInventoryFiltersType
      | undefined;
    expect(next?.store_id).toBeUndefined();
  });

  it("emits product_id and variant_id verbatim when non-empty", () => {
    const onChange = vi.fn();
    render(
      <AdminInventoryFilters
        filters={{ limit: 100 }}
        onChange={onChange}
      />,
    );

    fireEvent.change(
      screen.getByTestId("admin-inventory-filter-product-id"),
      { target: { value: "product-uuid" } },
    );
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ product_id: "product-uuid" }),
    );

    fireEvent.change(
      screen.getByTestId("admin-inventory-filter-variant-id"),
      { target: { value: "variant-uuid" } },
    );
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ variant_id: "variant-uuid" }),
    );
  });

  it("toggling Low stock only sets low_stock=true; toggling off drops it", () => {
    const onChange = vi.fn();
    const { rerender } = render(
      <AdminInventoryFilters
        filters={{ limit: 100 }}
        onChange={onChange}
      />,
    );
    fireEvent.click(
      screen.getByTestId("admin-inventory-filter-low-stock"),
    );
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ low_stock: true }),
    );

    rerender(
      <AdminInventoryFilters
        filters={{ limit: 100, low_stock: true }}
        onChange={onChange}
      />,
    );
    fireEvent.click(
      screen.getByTestId("admin-inventory-filter-low-stock"),
    );
    const next = onChange.mock.calls.at(-1)?.[0] as
      | AdminInventoryFiltersType
      | undefined;
    expect(next?.low_stock).toBeUndefined();
  });

  it("resets offset to 0 when a filter changes and offset was set", () => {
    const onChange = vi.fn();
    render(
      <AdminInventoryFilters
        filters={{ limit: 100, offset: 200 }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("admin-inventory-filter-q"), {
      target: { value: "x" },
    });
    const next = onChange.mock.calls.at(-1)?.[0] as
      | AdminInventoryFiltersType
      | undefined;
    expect(next?.offset).toBe(0);
  });

  it("does NOT introduce offset when the parent never set one", () => {
    const onChange = vi.fn();
    render(
      <AdminInventoryFilters
        filters={{ limit: 100 }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("admin-inventory-filter-q"), {
      target: { value: "x" },
    });
    const next = onChange.mock.calls.at(-1)?.[0] as
      | AdminInventoryFiltersType
      | undefined;
    expect(next?.offset).toBeUndefined();
  });

  it("disables all inputs when `disabled` is true", () => {
    render(
      <AdminInventoryFilters
        filters={{ limit: 100 }}
        onChange={vi.fn()}
        disabled
      />,
    );
    for (const tid of [
      "admin-inventory-filter-store-id",
      "admin-inventory-filter-q",
      "admin-inventory-filter-product-id",
      "admin-inventory-filter-variant-id",
      "admin-inventory-filter-low-stock",
    ]) {
      expect(screen.getByTestId(tid)).toBeDisabled();
    }
  });
});
