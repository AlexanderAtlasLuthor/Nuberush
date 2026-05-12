// F2.16.5: tests for AuditEventBadge.
//
// Pure render-only component; no hooks, no events. We assert the
// locked source-to-label map and that nothing other than the three
// known sources is rendered.

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { AuditEventBadge } from "../AuditEventBadge";

describe("AuditEventBadge", () => {
  it("renders 'Inventory' for source=inventory", () => {
    render(<AuditEventBadge source="inventory" />);
    expect(screen.getByText("Inventory")).toBeInTheDocument();
    expect(
      screen.getByTestId("audit-event-badge-inventory"),
    ).toHaveAttribute("data-source", "inventory");
  });

  it("renders 'Order' for source=order", () => {
    render(<AuditEventBadge source="order" />);
    expect(screen.getByText("Order")).toBeInTheDocument();
    expect(
      screen.getByTestId("audit-event-badge-order"),
    ).toHaveAttribute("data-source", "order");
  });

  it("renders 'Compliance' for source=product_compliance", () => {
    render(<AuditEventBadge source="product_compliance" />);
    expect(screen.getByText("Compliance")).toBeInTheDocument();
    expect(
      screen.getByTestId("audit-event-badge-product_compliance"),
    ).toHaveAttribute("data-source", "product_compliance");
  });

  it("does not render the raw enum value as visible text", () => {
    render(<AuditEventBadge source="product_compliance" />);
    // The badge body shows the humanized label, not the wire token.
    const badge = screen.getByTestId("audit-event-badge-product_compliance");
    expect(badge.textContent).toBe("Compliance");
    expect(badge.textContent).not.toMatch(/product_compliance/);
  });

  it("forwards a className to the badge element", () => {
    render(
      <AuditEventBadge source="inventory" className="custom-extra" />,
    );
    expect(
      screen.getByTestId("audit-event-badge-inventory"),
    ).toHaveClass("custom-extra");
  });

  it("exposes an aria-label for assistive tech", () => {
    render(<AuditEventBadge source="order" />);
    expect(
      screen.getByLabelText("Audit source: Order"),
    ).toBeInTheDocument();
  });
});
