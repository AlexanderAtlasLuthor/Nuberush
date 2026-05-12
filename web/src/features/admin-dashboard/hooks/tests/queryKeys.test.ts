// F2.19.3: query-key tests for the admin dashboard module.
//
// What we lock in (per F2.19.0 §3.1 + §5):
//   - `all` root is `["admin-dashboard"]`.
//   - `summary()` is `["admin-dashboard", "summary"]`.
//   - The summary key is stable across calls.
//   - No storeId / role / user value leaks into the key — the
//     admin dashboard endpoint has no such inputs by contract.
//   - The namespace does NOT collide with the store-scoped
//     `dashboardKeys` (per-store dashboard).

import { describe, expect, it } from "vitest";

import { adminDashboardKeys } from "../queryKeys";

describe("adminDashboardKeys — root namespace", () => {
  it("adminDashboardKeys.all equals ['admin-dashboard']", () => {
    expect(adminDashboardKeys.all).toEqual(["admin-dashboard"]);
  });

  it("exposes exactly the locked factory surface (all + summary)", () => {
    expect(Object.keys(adminDashboardKeys).sort()).toEqual(
      ["all", "summary"].sort(),
    );
  });
});

describe("adminDashboardKeys.summary", () => {
  it("equals ['admin-dashboard', 'summary']", () => {
    expect(adminDashboardKeys.summary()).toEqual([
      "admin-dashboard",
      "summary",
    ]);
  });

  it("is a two-segment tuple (no storeId / role / user / filters)", () => {
    const key = adminDashboardKeys.summary();
    expect(key).toHaveLength(2);
  });

  it("is stable across calls (value equality)", () => {
    const a = adminDashboardKeys.summary();
    const b = adminDashboardKeys.summary();
    expect(a).toEqual(b);
  });

  it("starts with the `all` root namespace", () => {
    const root = adminDashboardKeys.all;
    const summary = adminDashboardKeys.summary();
    expect(summary.slice(0, root.length)).toEqual(root);
  });
});

describe("adminDashboardKeys — guard against forbidden inputs", () => {
  it("contains no store id segment", () => {
    const key: readonly unknown[] = adminDashboardKeys.summary();
    for (const segment of key) {
      // Bare two-segment string tuple — no UUID-shaped strings, no
      // arbitrary objects. This is a sanity check against a future
      // accidental signature like `summary(storeId: string)`.
      expect(typeof segment).toBe("string");
    }
  });

  it("contains no role or user marker", () => {
    const key = adminDashboardKeys.summary();
    expect(key).not.toContain("admin");
    expect(key).not.toContain("owner");
    expect(key).not.toContain("manager");
    expect(key).not.toContain("staff");
    expect(key).not.toContain("driver");
  });

  it("namespace does not collide with the per-store 'dashboard' namespace", () => {
    // The store-scoped per-store dashboard lives under a `dashboard`
    // root; admin dashboard is intentionally under `admin-dashboard`
    // so prefix-invalidation of one never flushes the other.
    expect(adminDashboardKeys.all[0]).toBe("admin-dashboard");
    expect(adminDashboardKeys.all[0]).not.toBe("dashboard");
  });
});
