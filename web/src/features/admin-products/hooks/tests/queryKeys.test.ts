// F2.20.3: query-key factory unit tests for admin-products.
//
// Pure unit tests on the key factory — no React, no QueryClient. We
// assert the shape of every key the brief calls out and the prefix
// relationships used by future invalidations.

import { describe, expect, it } from "vitest";

import { adminProductsQueryKeys } from "../queryKeys";

describe("adminProductsQueryKeys", () => {
  it("anchors every key under the 'admin-products' root", () => {
    expect(adminProductsQueryKeys.all).toEqual(["admin-products"]);
  });

  it("lists() returns the prefix shared by every list call", () => {
    expect(adminProductsQueryKeys.lists()).toEqual([
      "admin-products",
      "list",
    ]);
  });

  it("list(filters) appends the filters object verbatim", () => {
    expect(
      adminProductsQueryKeys.list({
        compliance_status: "restricted",
        limit: 25,
      }),
    ).toEqual([
      "admin-products",
      "list",
      { compliance_status: "restricted", limit: 25 },
    ]);
  });

  it("list() with no args defaults to an empty filters object", () => {
    expect(adminProductsQueryKeys.list()).toEqual([
      "admin-products",
      "list",
      {},
    ]);
  });

  it("list(undefined) is stable and equal to list()", () => {
    expect(adminProductsQueryKeys.list(undefined)).toEqual(
      adminProductsQueryKeys.list(),
    );
  });

  it("lists() is a prefix of list(filters)", () => {
    const prefix = adminProductsQueryKeys.lists();
    const concrete = adminProductsQueryKeys.list({ category: "vape" });
    expect(concrete.slice(0, prefix.length)).toEqual([...prefix]);
  });

  it("produces the same key shape across calls with the same filters", () => {
    const filters = { compliance_status: "banned" as const, offset: 0 };
    expect(adminProductsQueryKeys.list(filters)).toEqual(
      adminProductsQueryKeys.list(filters),
    );
  });

  it("does not include store context, user context, role, or route path", () => {
    // Pin the exact tuple shape so a future drift that smuggles in
    // contextual fields is caught here.
    const key = adminProductsQueryKeys.list({ q: "milk" });
    expect(key).toEqual(["admin-products", "list", { q: "milk" }]);
    // None of the elements may carry contextual smuggling.
    for (const segment of key) {
      const json = JSON.stringify(segment);
      expect(json).not.toMatch(/store_id|storeId|user|role|pathname|route/i);
    }
  });
});
