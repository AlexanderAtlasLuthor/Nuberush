// Query-key factory unit tests for admin-earnings.
//
// Pure unit tests on the key factory — no React, no QueryClient.

import { describe, expect, it } from "vitest";

import { adminEarningsKeys } from "../queryKeys";

describe("adminEarningsKeys", () => {
  it("anchors every key under the 'admin-earnings' root", () => {
    expect(adminEarningsKeys.all).toEqual(["admin-earnings"]);
  });

  it("summary() returns ['admin-earnings', 'summary']", () => {
    expect(adminEarningsKeys.summary()).toEqual([
      "admin-earnings",
      "summary",
    ]);
  });

  it("summary() is a prefix of itself (idempotent shape)", () => {
    const a = adminEarningsKeys.summary();
    const b = adminEarningsKeys.summary();
    expect(b.slice(0, a.length)).toEqual([...a]);
  });

  it("all is a prefix of summary()", () => {
    const prefix = adminEarningsKeys.all;
    const concrete = adminEarningsKeys.summary();
    expect(concrete.slice(0, prefix.length)).toEqual([...prefix]);
  });
});
