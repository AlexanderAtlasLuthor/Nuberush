// F2.26.4.D copy guardrails: order-status display labels.
//
// Locks the humanized display labels for the order-status enum and the
// raw-value fallback, so a regression that re-exposes a snake_case token
// (e.g. `out_for_delivery`) as visible operator copy fails here. This is
// the shared helper behind every Store + Admin order-status surface.

import { describe, expect, it } from "vitest";

import { orderStatusLabel } from "../labels";

describe("orderStatusLabel (F2.26.4.D)", () => {
  it("humanizes out_for_delivery to 'Out for delivery'", () => {
    expect(orderStatusLabel("out_for_delivery")).toBe("Out for delivery");
  });

  it("title-cases the other order statuses", () => {
    expect(orderStatusLabel("pending")).toBe("Pending");
    expect(orderStatusLabel("accepted")).toBe("Accepted");
    expect(orderStatusLabel("preparing")).toBe("Preparing");
    expect(orderStatusLabel("ready")).toBe("Ready");
    expect(orderStatusLabel("delivered")).toBe("Delivered");
    expect(orderStatusLabel("canceled")).toBe("Canceled");
    expect(orderStatusLabel("returned")).toBe("Returned");
  });

  it("never renders a raw snake_case token for a known status", () => {
    expect(orderStatusLabel("out_for_delivery")).not.toContain("_");
  });

  it("falls back to the raw value for an unknown status (drift-safe)", () => {
    // A future backend status renders verbatim rather than blank.
    expect(orderStatusLabel("some_future_status" as never)).toBe(
      "some_future_status",
    );
  });

  it("returns an empty string for null/undefined without throwing", () => {
    expect(orderStatusLabel(null)).toBe("");
    expect(orderStatusLabel(undefined)).toBe("");
  });
});
