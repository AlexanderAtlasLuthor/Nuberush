// F2.26.4.D copy guardrails: inventory + compliance display labels.
//
// Locks the humanized display labels and the raw-value fallback for the
// inventory-status and compliance-status enums, so a regression that
// re-exposes a snake_case token as visible operator copy fails here.
// These are the shared helpers behind the Store inventory list and the
// order-creation variant picker.

import { describe, expect, it } from "vitest";

import { complianceStatusLabel, inventoryStatusLabel } from "../labels";

describe("inventoryStatusLabel (F2.26.4.D)", () => {
  it("title-cases the inventory statuses", () => {
    expect(inventoryStatusLabel("available")).toBe("Available");
    expect(inventoryStatusLabel("reserved")).toBe("Reserved");
    expect(inventoryStatusLabel("sold")).toBe("Sold");
    expect(inventoryStatusLabel("flagged")).toBe("Flagged");
    expect(inventoryStatusLabel("quarantined")).toBe("Quarantined");
  });

  it("falls back to the raw value for an unknown status (drift-safe)", () => {
    expect(inventoryStatusLabel("some_future_status" as never)).toBe(
      "some_future_status",
    );
  });
});

describe("complianceStatusLabel (F2.26.4.D)", () => {
  it("title-cases the compliance statuses used in the Store variant picker", () => {
    expect(complianceStatusLabel("allowed")).toBe("Allowed");
    expect(complianceStatusLabel("restricted")).toBe("Restricted");
    expect(complianceStatusLabel("banned")).toBe("Banned");
  });

  it("falls back to the raw value for an unknown status (drift-safe)", () => {
    expect(complianceStatusLabel("some_future_status")).toBe(
      "some_future_status",
    );
  });
});
