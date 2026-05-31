// F2.24.C7: navigation config assertions for the admin Applications item.
//
// Navigation is UX-only (it grants no access), but the C7 contract
// requires the admin "Applications" entry to exist and the store nav to
// stay free of it. These are pure data assertions over the exported nav
// arrays.

import { describe, expect, it } from "vitest";

import { ADMIN_NAV_ITEMS, STORE_NAV_ITEMS } from "../navigation";

describe("admin navigation — Applications", () => {
  it("includes an Applications item pointing at /app/admin/applications", () => {
    const item = ADMIN_NAV_ITEMS.find((i) => i.label === "Applications");
    expect(item).toBeDefined();
    expect(item?.href).toBe("/app/admin/applications");
  });
});

describe("store navigation — Applications", () => {
  it("does NOT include an Applications item", () => {
    expect(
      STORE_NAV_ITEMS.some((i) => i.label === "Applications"),
    ).toBe(false);
    expect(
      STORE_NAV_ITEMS.some((i) => i.href.includes("/applications")),
    ).toBe(false);
  });
});
