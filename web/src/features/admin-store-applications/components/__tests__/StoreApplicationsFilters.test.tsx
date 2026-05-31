// F2.24.C7: tests for StoreApplicationsFilters.
//
// The Radix listbox renders in a portal that jsdom can't drive reliably,
// so the status assertions go through the visually-hidden native <select>
// fallback, which shares the same handler as the styled control.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { StoreApplicationsFilters } from "../StoreApplicationsFilters";
import type { StoreApplicationListFilters } from "../../types";

describe("StoreApplicationsFilters", () => {
  it("calls onChange with `q` set when search changes", () => {
    const onChange = vi.fn();
    render(
      <StoreApplicationsFilters filters={{ limit: 25 }} onChange={onChange} />,
    );
    fireEvent.change(screen.getByTestId("store-applications-search"), {
      target: { value: "acme" },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ q: "acme" }),
    );
  });

  it("drops `q` when search is cleared", () => {
    const onChange = vi.fn();
    render(
      <StoreApplicationsFilters
        filters={{ limit: 25, q: "acme" }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("store-applications-search"), {
      target: { value: "" },
    });
    const call = onChange.mock.calls.at(-1)?.[0] as
      | StoreApplicationListFilters
      | undefined;
    expect(call?.q).toBeUndefined();
  });

  it("calls onChange with the selected status", () => {
    const onChange = vi.fn();
    render(
      <StoreApplicationsFilters filters={{ limit: 25 }} onChange={onChange} />,
    );
    fireEvent.change(screen.getByTestId("store-applications-status-native"), {
      target: { value: "approved" },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ status: "approved" }),
    );
  });

  it("drops `status` when 'all' is selected", () => {
    const onChange = vi.fn();
    render(
      <StoreApplicationsFilters
        filters={{ limit: 25, status: "approved" }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("store-applications-status-native"), {
      target: { value: "all" },
    });
    const call = onChange.mock.calls.at(-1)?.[0] as
      | StoreApplicationListFilters
      | undefined;
    expect(call?.status).toBeUndefined();
  });

  it("disables inputs when disabled", () => {
    render(
      <StoreApplicationsFilters
        filters={{ limit: 25 }}
        onChange={vi.fn()}
        disabled
      />,
    );
    expect(screen.getByTestId("store-applications-search")).toBeDisabled();
  });
});
