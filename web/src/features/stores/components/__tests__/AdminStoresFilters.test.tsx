// F2.18.3: tests for AdminStoresFilters.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { AdminStoresFilters } from "../AdminStoresFilters";
import type { StoreListFilters } from "../../types";

describe("AdminStoresFilters", () => {
  it("calls onChange with `q` set when search input changes", () => {
    const onChange = vi.fn();
    render(
      <AdminStoresFilters filters={{ limit: 25 }} onChange={onChange} />,
    );
    fireEvent.change(screen.getByTestId("admin-stores-filter-q"), {
      target: { value: "acme" },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ q: "acme" }),
    );
  });

  it("clearing search drops `q` from the snapshot", () => {
    const onChange = vi.fn();
    render(
      <AdminStoresFilters
        filters={{ limit: 25, q: "acme" }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("admin-stores-filter-q"), {
      target: { value: "" },
    });
    const call = onChange.mock.calls.at(-1)?.[0] as
      | StoreListFilters
      | undefined;
    expect(call?.q).toBeUndefined();
  });

  it("resets offset to 0 when search changes and offset was set", () => {
    const onChange = vi.fn();
    render(
      <AdminStoresFilters
        filters={{ limit: 25, offset: 50 }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("admin-stores-filter-q"), {
      target: { value: "x" },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ offset: 0 }),
    );
  });

  it("renders disabled inputs when `disabled` is true", () => {
    render(
      <AdminStoresFilters
        filters={{ limit: 25 }}
        onChange={vi.fn()}
        disabled
      />,
    );
    expect(screen.getByTestId("admin-stores-filter-q")).toBeDisabled();
  });
});
