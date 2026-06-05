// F2.18.4: tests for AdminAuditFilters.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { AdminAuditFilters } from "../AdminAuditFilters";
import type { AdminAuditFilters as AdminAuditFiltersType } from "../../types";

describe("AdminAuditFilters — text fields", () => {
  it("emits a `store_id` when the input has a non-empty value", () => {
    const onChange = vi.fn();
    render(
      <AdminAuditFilters filters={{ limit: 50 }} onChange={onChange} />,
    );
    fireEvent.change(
      screen.getByTestId("admin-audit-filter-store-id"),
      { target: { value: "store-uuid" } },
    );
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ store_id: "store-uuid" }),
    );
  });

  it("trims store_id and drops the key when only whitespace", () => {
    const onChange = vi.fn();
    render(
      <AdminAuditFilters
        filters={{ limit: 50, store_id: "x" }}
        onChange={onChange}
      />,
    );
    fireEvent.change(
      screen.getByTestId("admin-audit-filter-store-id"),
      { target: { value: "   " } },
    );
    const next = onChange.mock.calls.at(-1)?.[0] as
      | AdminAuditFiltersType
      | undefined;
    expect(next?.store_id).toBeUndefined();
  });

  it("trims action and emits the trimmed value", () => {
    const onChange = vi.fn();
    render(
      <AdminAuditFilters filters={{ limit: 50 }} onChange={onChange} />,
    );
    fireEvent.change(screen.getByTestId("admin-audit-filter-action"), {
      target: { value: "  receipt  " },
    });
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ action: "receipt" }),
    );
  });

  it("emits actor_id, date_from, date_to verbatim when non-empty", () => {
    const onChange = vi.fn();
    render(
      <AdminAuditFilters filters={{ limit: 50 }} onChange={onChange} />,
    );

    fireEvent.change(
      screen.getByTestId("admin-audit-filter-actor-id"),
      { target: { value: "actor-uuid" } },
    );
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ actor_id: "actor-uuid" }),
    );

    fireEvent.change(
      screen.getByTestId("admin-audit-filter-date-from"),
      { target: { value: "2026-01-01" } },
    );
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ date_from: "2026-01-01" }),
    );

    fireEvent.change(
      screen.getByTestId("admin-audit-filter-date-to"),
      { target: { value: "2026-12-31" } },
    );
    expect(onChange).toHaveBeenLastCalledWith(
      expect.objectContaining({ date_to: "2026-12-31" }),
    );
  });

  it("resets offset to 0 when a filter changes and offset was set", () => {
    const onChange = vi.fn();
    render(
      <AdminAuditFilters
        filters={{ limit: 50, offset: 100 }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("admin-audit-filter-action"), {
      target: { value: "x" },
    });
    const next = onChange.mock.calls.at(-1)?.[0] as
      | AdminAuditFiltersType
      | undefined;
    expect(next?.offset).toBe(0);
  });

  it("does NOT introduce offset when the parent never set one", () => {
    const onChange = vi.fn();
    render(
      <AdminAuditFilters filters={{ limit: 50 }} onChange={onChange} />,
    );
    fireEvent.change(screen.getByTestId("admin-audit-filter-action"), {
      target: { value: "x" },
    });
    const next = onChange.mock.calls.at(-1)?.[0] as
      | AdminAuditFiltersType
      | undefined;
    expect(next?.offset).toBeUndefined();
  });

  it("disables all inputs when `disabled` is true", () => {
    render(
      <AdminAuditFilters
        filters={{ limit: 50 }}
        onChange={vi.fn()}
        disabled
      />,
    );
    expect(
      screen.getByTestId("admin-audit-filter-store-id"),
    ).toBeDisabled();
    expect(
      screen.getByTestId("admin-audit-filter-action"),
    ).toBeDisabled();
    expect(
      screen.getByTestId("admin-audit-filter-actor-id"),
    ).toBeDisabled();
    expect(
      screen.getByTestId("admin-audit-filter-date-from"),
    ).toBeDisabled();
    expect(
      screen.getByTestId("admin-audit-filter-date-to"),
    ).toBeDisabled();
  });
});

describe("AdminAuditFilters — render surface", () => {
  it("renders all 7 admin filter controls", () => {
    render(
      <AdminAuditFilters filters={{ limit: 50 }} onChange={vi.fn()} />,
    );
    expect(
      screen.getByTestId("admin-audit-filter-store-id"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("admin-audit-filter-source-trigger"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("admin-audit-filter-entity-type-trigger"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("admin-audit-filter-action"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("admin-audit-filter-actor-id"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("admin-audit-filter-date-from"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("admin-audit-filter-date-to"),
    ).toBeInTheDocument();
  });

  it("reflects supplied `filters` values back into the inputs", () => {
    render(
      <AdminAuditFilters
        filters={{
          limit: 50,
          store_id: "store-x",
          action: "receipt",
          actor_id: "actor-x",
          date_from: "2026-01-01",
          date_to: "2026-12-31",
        }}
        onChange={vi.fn()}
      />,
    );
    expect(
      screen.getByTestId("admin-audit-filter-store-id"),
    ).toHaveValue("store-x");
    expect(
      screen.getByTestId("admin-audit-filter-action"),
    ).toHaveValue("receipt");
    expect(
      screen.getByTestId("admin-audit-filter-actor-id"),
    ).toHaveValue("actor-x");
    expect(
      screen.getByTestId("admin-audit-filter-date-from"),
    ).toHaveValue("2026-01-01");
    expect(
      screen.getByTestId("admin-audit-filter-date-to"),
    ).toHaveValue("2026-12-31");
  });
});

describe("AdminAuditFilters — copy guardrails (F2.26.4.D)", () => {
  it("uses operator-friendly ID placeholders, not raw 'UUID' wording", () => {
    render(<AdminAuditFilters filters={{ limit: 50 }} onChange={vi.fn()} />);

    const storeInput = screen.getByTestId("admin-audit-filter-store-id");
    expect(storeInput).toHaveAttribute(
      "placeholder",
      expect.stringMatching(/filter by store id/i),
    );
    expect(storeInput.getAttribute("placeholder")).not.toMatch(/uuid/i);

    const actorInput = screen.getByTestId("admin-audit-filter-actor-id");
    expect(actorInput.getAttribute("placeholder")).not.toMatch(/uuid/i);
  });
});
