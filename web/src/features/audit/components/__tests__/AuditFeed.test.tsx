// F2.16.5: tests for AuditFeed.
//
// Pure presentational component. We render typed `AuditEvent` data
// and assert the four states (loading / error / empty / data),
// the column shape, and the actor-null → "System" fallback. The
// component must not invent fields the wire doesn't carry; this
// suite includes guards against `actor_name`/`actor_email`/
// `store_name`/`severity` ever appearing in the rendered output.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { AuditFeed } from "../AuditFeed";
import type { AuditEvent } from "../../types";

const STORE_ID = "11111111-1111-1111-1111-111111111111";
const ACTOR_ID = "33333333-3333-3333-3333-333333333333";
const ENTITY_ID = "ee111111-2222-3333-4444-555555555555";

function makeEvent(overrides: Partial<AuditEvent> = {}): AuditEvent {
  return {
    id: "evt-1",
    source: "inventory",
    store_id: STORE_ID,
    actor_id: ACTOR_ID,
    action: "receipt",
    entity_type: "inventory_item",
    entity_id: ENTITY_ID,
    summary: "Inventory receipt: +10 units (after 10)",
    metadata: { quantity_delta: 10, quantity_after: 10 },
    created_at: "2026-05-04T08:30:00Z",
    ...overrides,
  };
}

// --------------------------------------------------------------------- //
// Render states
// --------------------------------------------------------------------- //

describe("AuditFeed — loading state", () => {
  it("renders the loading copy when isLoading=true", () => {
    render(<AuditFeed events={[]} isLoading />);
    expect(screen.getByText(/Loading audit events/i)).toBeInTheDocument();
  });

  it("does not render the table while loading", () => {
    render(<AuditFeed events={[]} isLoading />);
    expect(
      screen.queryByTestId("audit-feed-table-wrapper"),
    ).not.toBeInTheDocument();
  });
});

describe("AuditFeed — error state", () => {
  it("renders the error copy when error is truthy", () => {
    render(<AuditFeed events={[]} error={new Error("boom")} />);
    expect(
      screen.getByText("Audit feed failed to load"),
    ).toBeInTheDocument();
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });

  it("renders a Retry button that calls onRetry", () => {
    const onRetry = vi.fn();
    render(
      <AuditFeed
        events={[]}
        error={new Error("boom")}
        onRetry={onRetry}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("omits the Retry button when onRetry is not provided", () => {
    render(<AuditFeed events={[]} error={new Error("boom")} />);
    expect(
      screen.queryByRole("button", { name: "Retry" }),
    ).not.toBeInTheDocument();
  });
});

describe("AuditFeed — empty state", () => {
  it("renders the default empty copy when events is []", () => {
    render(<AuditFeed events={[]} />);
    expect(screen.getByText("No audit events")).toBeInTheDocument();
    expect(
      screen.getByText("No activity recorded for the selected filters."),
    ).toBeInTheDocument();
  });

  it("uses a custom emptyTitle and emptyDescription when provided", () => {
    render(
      <AuditFeed
        events={[]}
        emptyTitle="Custom empty"
        emptyDescription="Custom description here."
      />,
    );
    expect(screen.getByText("Custom empty")).toBeInTheDocument();
    expect(
      screen.getByText("Custom description here."),
    ).toBeInTheDocument();
  });

  it("does not render the table when events is []", () => {
    render(<AuditFeed events={[]} />);
    expect(
      screen.queryByTestId("audit-feed-table-wrapper"),
    ).not.toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Data rows
// --------------------------------------------------------------------- //

describe("AuditFeed — data rows", () => {
  it("renders one row per event with the columns Time / Source / Summary / Action / Entity / Actor", () => {
    const event = makeEvent();
    render(<AuditFeed events={[event]} />);
    expect(
      screen.getByTestId("audit-feed-table-wrapper"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId(`audit-feed-row-${event.id}`),
    ).toBeInTheDocument();

    // The six header labels.
    for (const header of [
      "Time",
      "Source",
      "Summary",
      "Action",
      "Entity",
      "Actor",
    ]) {
      expect(
        screen.getByRole("columnheader", { name: header }),
      ).toBeInTheDocument();
    }
  });

  it("renders the summary verbatim", () => {
    const event = makeEvent({
      summary: "Inventory adjustment: -3 units (after 7)",
    });
    render(<AuditFeed events={[event]} />);
    expect(
      screen.getByTestId(`audit-feed-summary-${event.id}`),
    ).toHaveTextContent("Inventory adjustment: -3 units (after 7)");
  });

  it("renders the action verbatim", () => {
    const event = makeEvent({ action: "order_canceled" });
    render(<AuditFeed events={[event]} />);
    expect(
      screen.getByTestId(`audit-feed-action-${event.id}`),
    ).toHaveTextContent("order_canceled");
  });

  it("renders the AuditEventBadge for each source", () => {
    const inv = makeEvent({ id: "e-inv", source: "inventory" });
    const ord = makeEvent({
      id: "e-ord",
      source: "order",
      entity_type: "order",
    });
    const comp = makeEvent({
      id: "e-comp",
      source: "product_compliance",
      entity_type: "product",
    });
    render(<AuditFeed events={[inv, ord, comp]} />);
    expect(
      screen.getByTestId("audit-event-badge-inventory"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("audit-event-badge-order"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("audit-event-badge-product_compliance"),
    ).toBeInTheDocument();
  });

  it("renders the formatted created_at and exposes the raw ISO via title", () => {
    const event = makeEvent({ created_at: "2026-05-04T08:30:00Z" });
    render(<AuditFeed events={[event]} />);
    const cell = screen.getByTestId(`audit-feed-time-${event.id}`);
    // The raw ISO is preserved on `title` for hover/copy regardless
    // of locale formatting.
    expect(cell).toHaveAttribute("title", "2026-05-04T08:30:00Z");
    // Some formatted output is rendered (we don't pin the exact
    // locale string to avoid environment coupling).
    expect(cell.textContent?.length ?? 0).toBeGreaterThan(0);
  });

  it("renders the entity type label and a short entity_id", () => {
    const event = makeEvent({
      entity_type: "inventory_item",
      entity_id: ENTITY_ID,
    });
    render(<AuditFeed events={[event]} />);
    const cell = screen.getByTestId(`audit-feed-entity-${event.id}`);
    expect(cell).toHaveTextContent("Inventory item");
    // First 8 chars of the entity_id, full value on the cell title.
    expect(cell).toHaveTextContent(ENTITY_ID.slice(0, 8));
    expect(cell).toHaveAttribute("title", ENTITY_ID);
  });

  it("renders the short actor_id when present", () => {
    const event = makeEvent({ actor_id: ACTOR_ID });
    render(<AuditFeed events={[event]} />);
    const cell = screen.getByTestId(`audit-feed-actor-${event.id}`);
    expect(cell).toHaveTextContent(ACTOR_ID.slice(0, 8));
    expect(cell).toHaveAttribute("title", ACTOR_ID);
  });

  it("renders 'System' when actor_id is null", () => {
    const event = makeEvent({ actor_id: null });
    render(<AuditFeed events={[event]} />);
    const cell = screen.getByTestId(`audit-feed-actor-${event.id}`);
    expect(cell).toHaveTextContent("System");
    expect(cell).toHaveAttribute("title", "System");
  });

  it("renders the same number of rows as events", () => {
    const events = [
      makeEvent({ id: "e1" }),
      makeEvent({ id: "e2" }),
      makeEvent({ id: "e3" }),
    ];
    render(<AuditFeed events={events} />);
    expect(
      screen.getAllByTestId(/^audit-feed-row-/),
    ).toHaveLength(3);
  });
});

// --------------------------------------------------------------------- //
// Anti-fake-data guards
// --------------------------------------------------------------------- //

describe("AuditFeed — no fake or invented fields", () => {
  it("does not render actor_name / actor_email / store_name / severity", () => {
    const event = makeEvent({ actor_id: ACTOR_ID });
    const { container } = render(<AuditFeed events={[event]} />);
    const text = container.textContent ?? "";
    for (const forbidden of [
      "actor_name",
      "actor_email",
      "store_name",
      "severity",
      "Severity",
    ]) {
      expect(text).not.toMatch(new RegExp(forbidden));
    }
  });

  it("renders zero rows for an empty events array (no fake placeholder rows)", () => {
    render(<AuditFeed events={[]} />);
    expect(
      screen.queryAllByTestId(/^audit-feed-row-/),
    ).toHaveLength(0);
  });

  it("loading state does not render rows", () => {
    render(<AuditFeed events={[]} isLoading />);
    expect(
      screen.queryAllByTestId(/^audit-feed-row-/),
    ).toHaveLength(0);
  });
});

// --------------------------------------------------------------------- //
// State precedence (loading wins over error wins over empty)
// --------------------------------------------------------------------- //

describe("AuditFeed — state precedence", () => {
  it("loading takes precedence over error", () => {
    render(
      <AuditFeed
        events={[]}
        isLoading
        error={new Error("boom")}
      />,
    );
    expect(screen.getByText(/Loading audit events/i)).toBeInTheDocument();
    expect(
      screen.queryByText("Audit feed failed to load"),
    ).not.toBeInTheDocument();
  });

  it("error takes precedence over empty", () => {
    render(<AuditFeed events={[]} error={new Error("boom")} />);
    expect(
      screen.getByText("Audit feed failed to load"),
    ).toBeInTheDocument();
    expect(screen.queryByText("No audit events")).not.toBeInTheDocument();
  });

  it("data takes precedence over empty when events has rows", () => {
    const event = makeEvent();
    render(<AuditFeed events={[event]} />);
    expect(
      screen.getByTestId("audit-feed-table-wrapper"),
    ).toBeInTheDocument();
    expect(screen.queryByText("No audit events")).not.toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Three-source smoke (end-to-end shape over the row mapping)
// --------------------------------------------------------------------- //

describe("AuditFeed — three sources end-to-end", () => {
  it("renders inventory + order + product_compliance rows correctly", () => {
    const events: AuditEvent[] = [
      makeEvent({
        id: "e-inv",
        source: "inventory",
        action: "receipt",
        entity_type: "inventory_item",
        summary: "Inventory receipt: +10 units (after 10)",
        actor_id: ACTOR_ID,
      }),
      makeEvent({
        id: "e-ord",
        source: "order",
        action: "order_canceled",
        entity_type: "order",
        summary: "Order order_canceled: pending → canceled",
        actor_id: ACTOR_ID,
      }),
      makeEvent({
        id: "e-comp",
        source: "product_compliance",
        action: "compliance_changed",
        entity_type: "product",
        summary: "Compliance: allowed/true → restricted/false",
        actor_id: null,
      }),
    ];
    render(<AuditFeed events={events} />);

    const invRow = screen.getByTestId("audit-feed-row-e-inv");
    expect(
      within(invRow).getByTestId("audit-event-badge-inventory"),
    ).toBeInTheDocument();

    const ordRow = screen.getByTestId("audit-feed-row-e-ord");
    expect(
      within(ordRow).getByTestId("audit-event-badge-order"),
    ).toBeInTheDocument();

    const compRow = screen.getByTestId("audit-feed-row-e-comp");
    expect(
      within(compRow).getByTestId(
        "audit-event-badge-product_compliance",
      ),
    ).toBeInTheDocument();
    // System for null actor on the compliance row.
    expect(
      screen.getByTestId("audit-feed-actor-e-comp"),
    ).toHaveTextContent("System");
  });
});
