// F2.19.4: query-key tests for the admin operations module.
//
// What we lock in (per F2.19.0 §3.2 + §5):
//   - `all` root is `["admin-operations"]`.
//   - `alertLists()` is `["admin-operations", "alerts", "list"]`.
//   - `alertList(filters)` carries the filters object verbatim, or
//     `{}` when omitted, so different snapshots get distinct slots.
//   - Explicit `offset=0` and `aging_minutes` values survive into
//     the key (no silent dropping).
//   - No storeId path segment, no role/user value.
//   - Namespace does NOT collide with the F2.19.3
//     `adminDashboardKeys` (`"admin-dashboard"`).

import { describe, expect, it } from "vitest";

import { adminOperationsKeys } from "../queryKeys";
import type { AdminOperationsAlertsFilters } from "../../types";

const STORE_ID = "11111111-1111-1111-1111-111111111111";
const OTHER_STORE_ID = "22222222-2222-2222-2222-222222222222";

describe("adminOperationsKeys — root namespace", () => {
  it("adminOperationsKeys.all equals ['admin-operations']", () => {
    expect(adminOperationsKeys.all).toEqual(["admin-operations"]);
  });

  it("exposes exactly the locked factory surface (all + alertLists + alertList)", () => {
    expect(Object.keys(adminOperationsKeys).sort()).toEqual(
      ["all", "alertList", "alertLists"].sort(),
    );
  });
});

describe("adminOperationsKeys.alertLists (prefix)", () => {
  it("returns the cross-filter prefix tuple", () => {
    expect(adminOperationsKeys.alertLists()).toEqual([
      "admin-operations",
      "alerts",
      "list",
    ]);
  });

  it("is a prefix of every alertList(...) key", () => {
    const prefix = adminOperationsKeys.alertLists();
    const full = adminOperationsKeys.alertList({ limit: 50 });
    expect(full.slice(0, prefix.length)).toEqual(prefix);
  });
});

describe("adminOperationsKeys.alertList (concrete key)", () => {
  it("defaults filters to {} when omitted", () => {
    expect(adminOperationsKeys.alertList()).toEqual([
      "admin-operations",
      "alerts",
      "list",
      {},
    ]);
  });

  it("includes the filters object verbatim in the tuple", () => {
    const filters: AdminOperationsAlertsFilters = {
      limit: 25,
      offset: 0,
      category: "low_stock",
      severity: "high",
      store_id: STORE_ID,
      aging_minutes: 60,
    };
    expect(adminOperationsKeys.alertList(filters)).toEqual([
      "admin-operations",
      "alerts",
      "list",
      filters,
    ]);
  });

  it("preserves an explicit offset=0 inside the filters slot", () => {
    const key = adminOperationsKeys.alertList({ offset: 0 });
    expect(key).toEqual([
      "admin-operations",
      "alerts",
      "list",
      { offset: 0 },
    ]);
  });

  it("preserves aging_minutes inside the filters slot", () => {
    const key = adminOperationsKeys.alertList({ aging_minutes: 1440 });
    expect(key).toEqual([
      "admin-operations",
      "alerts",
      "list",
      { aging_minutes: 1440 },
    ]);
  });

  it("produces different keys for different filter snapshots", () => {
    const a = adminOperationsKeys.alertList({ limit: 25 });
    const b = adminOperationsKeys.alertList({ limit: 50 });
    expect(a).not.toEqual(b);
  });

  it("produces different keys for different store_id filter values", () => {
    const a = adminOperationsKeys.alertList({ store_id: STORE_ID });
    const b = adminOperationsKeys.alertList({
      store_id: OTHER_STORE_ID,
    });
    expect(a).not.toEqual(b);
  });

  it("produces different keys for different category values", () => {
    const a = adminOperationsKeys.alertList({ category: "low_stock" });
    const b = adminOperationsKeys.alertList({ category: "aging_order" });
    expect(a).not.toEqual(b);
  });

  it("is stable across calls with equivalent input", () => {
    const a = adminOperationsKeys.alertList({ limit: 50 });
    const b = adminOperationsKeys.alertList({ limit: 50 });
    expect(a).toEqual(b);
  });

  it("starts with the `all` root namespace", () => {
    const root = adminOperationsKeys.all;
    const key = adminOperationsKeys.alertList();
    expect(key.slice(0, root.length)).toEqual(root);
  });
});

describe("adminOperationsKeys — guard against forbidden inputs", () => {
  it("contains no role or user marker", () => {
    const key = adminOperationsKeys.alertList({ store_id: STORE_ID });
    // The key must not include UserRole values or auth markers.
    expect(key).not.toContain("admin");
    expect(key).not.toContain("owner");
    expect(key).not.toContain("manager");
    expect(key).not.toContain("staff");
    expect(key).not.toContain("driver");
  });

  it("namespace does not collide with admin-dashboard namespace", () => {
    expect(adminOperationsKeys.all[0]).toBe("admin-operations");
    expect(adminOperationsKeys.all[0]).not.toBe("admin-dashboard");
  });

  it("first segment never equals 'dashboard' (per-store namespace)", () => {
    expect(adminOperationsKeys.all[0]).not.toBe("dashboard");
  });
});
