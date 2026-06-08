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

// F2.26.6.F: admin Regulatory nav item is global-admin only and sits
// alongside Compliance; the store nav never receives it.
describe("admin navigation — Regulatory", () => {
  it("includes a Regulatory item pointing at /app/admin/regulatory", () => {
    const item = ADMIN_NAV_ITEMS.find((i) => i.label === "Regulatory");
    expect(item).toBeDefined();
    expect(item?.href).toBe("/app/admin/regulatory");
  });

  it("keeps the existing Compliance item present", () => {
    const compliance = ADMIN_NAV_ITEMS.find((i) => i.label === "Compliance");
    expect(compliance).toBeDefined();
    expect(compliance?.href).toBe("/app/admin/compliance");
  });

  it("places Regulatory immediately after Compliance", () => {
    const complianceIdx = ADMIN_NAV_ITEMS.findIndex(
      (i) => i.label === "Compliance",
    );
    const regulatoryIdx = ADMIN_NAV_ITEMS.findIndex(
      (i) => i.label === "Regulatory",
    );
    expect(complianceIdx).toBeGreaterThanOrEqual(0);
    expect(regulatoryIdx).toBe(complianceIdx + 1);
  });
});

// F2.27.6: the store nav now exposes a read-only, store-scoped Regulatory
// surface at /app/store/regulatory (distinct from the admin one). This flips
// the prior "store has no Regulatory item" assertion.
describe("store navigation — Regulatory", () => {
  it("includes a Regulatory item pointing at /app/store/regulatory", () => {
    const item = STORE_NAV_ITEMS.find((i) => i.label === "Regulatory");
    expect(item).toBeDefined();
    expect(item?.href).toBe("/app/store/regulatory");
  });

  it("keeps the existing Audit item present", () => {
    const audit = STORE_NAV_ITEMS.find((i) => i.label === "Audit");
    expect(audit).toBeDefined();
    expect(audit?.href).toBe("/app/store/audit");
  });

  it("places Regulatory immediately after Audit", () => {
    const auditIdx = STORE_NAV_ITEMS.findIndex((i) => i.label === "Audit");
    const regulatoryIdx = STORE_NAV_ITEMS.findIndex(
      (i) => i.label === "Regulatory",
    );
    expect(auditIdx).toBeGreaterThanOrEqual(0);
    expect(regulatoryIdx).toBe(auditIdx + 1);
  });

  it("points the store Regulatory item at the store surface, not admin", () => {
    const item = STORE_NAV_ITEMS.find((i) => i.label === "Regulatory");
    expect(item?.href.startsWith("/app/store")).toBe(true);
  });
});
