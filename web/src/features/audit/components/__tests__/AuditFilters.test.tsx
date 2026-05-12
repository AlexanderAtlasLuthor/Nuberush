// F2.16.5: tests for AuditFilters.
//
// Controlled component driven through fire-event interactions
// (mirrors features/users/components/__tests__/UsersFilters.test.tsx).
// We assert the `onChange` payload against the documented behavior
// of `StoreAuditFilters`: source-set/clear, text-trim, empty-string
// omission, preserve-limit, and the offset-reset rule.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { AuditFilters } from "../AuditFilters";
import type { StoreAuditFilters } from "../../types";

const ACTOR_ID = "33333333-3333-3333-3333-333333333333";

// --------------------------------------------------------------------- //
// Render
// --------------------------------------------------------------------- //

describe("AuditFilters — render", () => {
  it("renders the source select trigger", () => {
    render(<AuditFilters filters={{}} onChange={() => {}} />);
    expect(
      screen.getByTestId("audit-filter-source-trigger"),
    ).toBeInTheDocument();
  });

  it("renders the action input", () => {
    render(<AuditFilters filters={{}} onChange={() => {}} />);
    expect(screen.getByTestId("audit-filter-action")).toBeInTheDocument();
  });

  it("renders the actor_id input", () => {
    render(<AuditFilters filters={{}} onChange={() => {}} />);
    expect(
      screen.getByTestId("audit-filter-actor-id"),
    ).toBeInTheDocument();
  });

  it("renders the date_from input", () => {
    render(<AuditFilters filters={{}} onChange={() => {}} />);
    expect(
      screen.getByTestId("audit-filter-date-from"),
    ).toBeInTheDocument();
  });

  it("renders the date_to input", () => {
    render(<AuditFilters filters={{}} onChange={() => {}} />);
    expect(
      screen.getByTestId("audit-filter-date-to"),
    ).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Source select
// --------------------------------------------------------------------- //

describe("AuditFilters — source", () => {
  it("selecting Inventory emits source: inventory", () => {
    const onChange = vi.fn();
    render(<AuditFilters filters={{}} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("audit-filter-source-trigger"));
    fireEvent.click(screen.getByRole("option", { name: "Inventory" }));
    expect(onChange).toHaveBeenCalledWith({ source: "inventory" });
  });

  it("selecting Order emits source: order", () => {
    const onChange = vi.fn();
    render(<AuditFilters filters={{}} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("audit-filter-source-trigger"));
    fireEvent.click(screen.getByRole("option", { name: "Order" }));
    expect(onChange).toHaveBeenCalledWith({ source: "order" });
  });

  it("selecting Compliance emits source: product_compliance", () => {
    const onChange = vi.fn();
    render(<AuditFilters filters={{}} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("audit-filter-source-trigger"));
    fireEvent.click(screen.getByRole("option", { name: "Compliance" }));
    expect(onChange).toHaveBeenCalledWith({ source: "product_compliance" });
  });

  it("selecting 'All sources' removes source from filters", () => {
    const onChange = vi.fn();
    render(
      <AuditFilters
        filters={{ source: "inventory" }}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByTestId("audit-filter-source-trigger"));
    const listbox = screen.getByRole("listbox");
    fireEvent.click(
      within(listbox).getByRole("option", { name: "All sources" }),
    );
    const next = onChange.mock.calls[0][0] as StoreAuditFilters;
    expect(next).not.toHaveProperty("source");
  });
});

// --------------------------------------------------------------------- //
// Action input
// --------------------------------------------------------------------- //

describe("AuditFilters — action", () => {
  it("typing a value emits a trimmed action", () => {
    const onChange = vi.fn();
    render(<AuditFilters filters={{}} onChange={onChange} />);
    fireEvent.change(screen.getByTestId("audit-filter-action"), {
      target: { value: "  receipt  " },
    });
    expect(onChange).toHaveBeenCalledWith({ action: "receipt" });
  });

  it("clearing action removes it from filters", () => {
    const onChange = vi.fn();
    render(
      <AuditFilters
        filters={{ action: "receipt" }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("audit-filter-action"), {
      target: { value: "" },
    });
    const next = onChange.mock.calls[0][0] as StoreAuditFilters;
    expect(next).not.toHaveProperty("action");
  });

  it("typing whitespace-only removes action", () => {
    const onChange = vi.fn();
    render(
      <AuditFilters
        filters={{ action: "receipt" }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("audit-filter-action"), {
      target: { value: "   " },
    });
    const next = onChange.mock.calls[0][0] as StoreAuditFilters;
    expect(next).not.toHaveProperty("action");
  });
});

// --------------------------------------------------------------------- //
// Actor / dates
// --------------------------------------------------------------------- //

describe("AuditFilters — actor_id", () => {
  it("typing emits a trimmed actor_id", () => {
    const onChange = vi.fn();
    render(<AuditFilters filters={{}} onChange={onChange} />);
    fireEvent.change(screen.getByTestId("audit-filter-actor-id"), {
      target: { value: `  ${ACTOR_ID}  ` },
    });
    expect(onChange).toHaveBeenCalledWith({ actor_id: ACTOR_ID });
  });

  it("clearing removes actor_id", () => {
    const onChange = vi.fn();
    render(
      <AuditFilters
        filters={{ actor_id: ACTOR_ID }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("audit-filter-actor-id"), {
      target: { value: "" },
    });
    const next = onChange.mock.calls[0][0] as StoreAuditFilters;
    expect(next).not.toHaveProperty("actor_id");
  });
});

describe("AuditFilters — date_from / date_to", () => {
  it("typing date_from sets the value", () => {
    const onChange = vi.fn();
    render(<AuditFilters filters={{}} onChange={onChange} />);
    fireEvent.change(screen.getByTestId("audit-filter-date-from"), {
      target: { value: "2026-01-01" },
    });
    expect(onChange).toHaveBeenCalledWith({ date_from: "2026-01-01" });
  });

  it("clearing date_from removes it", () => {
    const onChange = vi.fn();
    render(
      <AuditFilters
        filters={{ date_from: "2026-01-01" }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("audit-filter-date-from"), {
      target: { value: "" },
    });
    const next = onChange.mock.calls[0][0] as StoreAuditFilters;
    expect(next).not.toHaveProperty("date_from");
  });

  it("typing date_to sets the value", () => {
    const onChange = vi.fn();
    render(<AuditFilters filters={{}} onChange={onChange} />);
    fireEvent.change(screen.getByTestId("audit-filter-date-to"), {
      target: { value: "2026-02-01" },
    });
    expect(onChange).toHaveBeenCalledWith({ date_to: "2026-02-01" });
  });

  it("clearing date_to removes it", () => {
    const onChange = vi.fn();
    render(
      <AuditFilters
        filters={{ date_to: "2026-02-01" }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("audit-filter-date-to"), {
      target: { value: "" },
    });
    const next = onChange.mock.calls[0][0] as StoreAuditFilters;
    expect(next).not.toHaveProperty("date_to");
  });
});

// --------------------------------------------------------------------- //
// Limit preservation and offset reset
// --------------------------------------------------------------------- //

describe("AuditFilters — limit and offset semantics", () => {
  it("preserves limit when other filters change", () => {
    const onChange = vi.fn();
    render(
      <AuditFilters
        filters={{ limit: 25 }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("audit-filter-action"), {
      target: { value: "receipt" },
    });
    expect(onChange.mock.calls[0][0]).toEqual({
      limit: 25,
      action: "receipt",
    });
  });

  it("resets offset to 0 when an offset existed and a filter changes", () => {
    const onChange = vi.fn();
    render(
      <AuditFilters
        filters={{ limit: 25, offset: 100, action: "receipt" }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("audit-filter-action"), {
      target: { value: "sale" },
    });
    expect(onChange.mock.calls[0][0]).toEqual({
      limit: 25,
      offset: 0,
      action: "sale",
    });
  });

  it("does not introduce offset when no offset existed", () => {
    const onChange = vi.fn();
    render(
      <AuditFilters
        filters={{ limit: 25 }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("audit-filter-action"), {
      target: { value: "sale" },
    });
    const next = onChange.mock.calls[0][0] as StoreAuditFilters;
    expect(next).not.toHaveProperty("offset");
  });

  it("resets offset to 0 on source change too", () => {
    const onChange = vi.fn();
    render(
      <AuditFilters
        filters={{ offset: 100 }}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByTestId("audit-filter-source-trigger"));
    fireEvent.click(screen.getByRole("option", { name: "Inventory" }));
    expect(onChange.mock.calls[0][0]).toEqual({
      offset: 0,
      source: "inventory",
    });
  });
});

// --------------------------------------------------------------------- //
// Disabled
// --------------------------------------------------------------------- //

describe("AuditFilters — disabled", () => {
  it("disables every input control when disabled=true", () => {
    render(
      <AuditFilters filters={{}} onChange={() => {}} disabled />,
    );
    expect(screen.getByTestId("audit-filter-action")).toBeDisabled();
    expect(screen.getByTestId("audit-filter-actor-id")).toBeDisabled();
    expect(screen.getByTestId("audit-filter-date-from")).toBeDisabled();
    expect(screen.getByTestId("audit-filter-date-to")).toBeDisabled();
    expect(
      screen.getByTestId("audit-filter-source-trigger"),
    ).toBeDisabled();
  });

  it("inputs are NOT disabled when disabled prop is omitted", () => {
    render(<AuditFilters filters={{}} onChange={() => {}} />);
    expect(screen.getByTestId("audit-filter-action")).not.toBeDisabled();
    expect(
      screen.getByTestId("audit-filter-source-trigger"),
    ).not.toBeDisabled();
  });
});
