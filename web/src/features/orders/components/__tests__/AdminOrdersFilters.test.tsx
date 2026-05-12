// F2.18.5: tests for AdminOrdersFilters.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { AdminOrdersFilters } from "../AdminOrdersFilters";
import type { AdminOrdersFilters as AdminOrdersFiltersType } from "../../types";

describe("AdminOrdersFilters", () => {
  it("renders all 4 admin orders filter controls and NO `q` input", () => {
    render(
      <AdminOrdersFilters filters={{ limit: 50 }} onChange={vi.fn()} />,
    );
    for (const tid of [
      "admin-orders-filter-store-id",
      "admin-orders-filter-status-trigger",
      "admin-orders-filter-date-from",
      "admin-orders-filter-date-to",
    ]) {
      expect(screen.getByTestId(tid)).toBeInTheDocument();
    }
    expect(
      screen.queryByTestId("admin-orders-filter-q"),
    ).not.toBeInTheDocument();
  });

  it("emits store_id, date_from, date_to verbatim when non-empty", () => {
    const onChange = vi.fn();
    render(
      <AdminOrdersFilters filters={{ limit: 50 }} onChange={onChange} />,
    );

    fireEvent.change(
      screen.getByTestId("admin-orders-filter-store-id"),
      { target: { value: "store-uuid" } },
    );
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ store_id: "store-uuid" }),
    );

    fireEvent.change(
      screen.getByTestId("admin-orders-filter-date-from"),
      { target: { value: "2026-01-01" } },
    );
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ date_from: "2026-01-01" }),
    );

    fireEvent.change(
      screen.getByTestId("admin-orders-filter-date-to"),
      { target: { value: "2026-12-31" } },
    );
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ date_to: "2026-12-31" }),
    );
  });

  it("trims store_id and drops the key when only whitespace", () => {
    const onChange = vi.fn();
    render(
      <AdminOrdersFilters
        filters={{ limit: 50, store_id: "x" }}
        onChange={onChange}
      />,
    );
    fireEvent.change(
      screen.getByTestId("admin-orders-filter-store-id"),
      { target: { value: "   " } },
    );
    const next = onChange.mock.calls.at(-1)?.[0] as
      | AdminOrdersFiltersType
      | undefined;
    expect(next?.store_id).toBeUndefined();
  });

  it("never serializes a `q` key into the snapshot", () => {
    const onChange = vi.fn();
    render(
      <AdminOrdersFilters filters={{ limit: 50 }} onChange={onChange} />,
    );
    fireEvent.change(
      screen.getByTestId("admin-orders-filter-store-id"),
      { target: { value: "s" } },
    );
    fireEvent.change(
      screen.getByTestId("admin-orders-filter-date-from"),
      { target: { value: "2026-01-01" } },
    );
    for (const call of onChange.mock.calls) {
      const snap = call[0] as
        | (AdminOrdersFiltersType & { q?: unknown })
        | undefined;
      expect(snap?.q).toBeUndefined();
    }
  });

  it("resets offset to 0 when a filter changes and offset was set", () => {
    const onChange = vi.fn();
    render(
      <AdminOrdersFilters
        filters={{ limit: 50, offset: 100 }}
        onChange={onChange}
      />,
    );
    fireEvent.change(
      screen.getByTestId("admin-orders-filter-date-from"),
      { target: { value: "2026-01-01" } },
    );
    const next = onChange.mock.calls.at(-1)?.[0] as
      | AdminOrdersFiltersType
      | undefined;
    expect(next?.offset).toBe(0);
  });

  it("does NOT introduce offset when the parent never set one", () => {
    const onChange = vi.fn();
    render(
      <AdminOrdersFilters filters={{ limit: 50 }} onChange={onChange} />,
    );
    fireEvent.change(
      screen.getByTestId("admin-orders-filter-date-from"),
      { target: { value: "2026-01-01" } },
    );
    const next = onChange.mock.calls.at(-1)?.[0] as
      | AdminOrdersFiltersType
      | undefined;
    expect(next?.offset).toBeUndefined();
  });

  it("disables all inputs when `disabled` is true", () => {
    render(
      <AdminOrdersFilters
        filters={{ limit: 50 }}
        onChange={vi.fn()}
        disabled
      />,
    );
    for (const tid of [
      "admin-orders-filter-store-id",
      "admin-orders-filter-date-from",
      "admin-orders-filter-date-to",
    ]) {
      expect(screen.getByTestId(tid)).toBeDisabled();
    }
  });
});
