// F2.20.4: query-key factory unit tests for admin-compliance.
//
// Pure unit tests on the key factory — no React, no QueryClient. We
// assert the shape of every key the brief calls out and the
// distinctness of the summary vs. products list slots.

import { describe, expect, it } from "vitest";

import { adminComplianceQueryKeys } from "../queryKeys";

describe("adminComplianceQueryKeys", () => {
  it("anchors every key under the 'admin-compliance' root", () => {
    expect(adminComplianceQueryKeys.all).toEqual(["admin-compliance"]);
  });

  it("summary() returns ['admin-compliance', 'summary']", () => {
    expect(adminComplianceQueryKeys.summary()).toEqual([
      "admin-compliance",
      "summary",
    ]);
  });

  it("products() returns ['admin-compliance', 'products']", () => {
    expect(adminComplianceQueryKeys.products()).toEqual([
      "admin-compliance",
      "products",
    ]);
  });

  it("productsList(filters) appends 'list' + filters object verbatim", () => {
    expect(
      adminComplianceQueryKeys.productsList({
        compliance_status: "restricted",
        limit: 25,
      }),
    ).toEqual([
      "admin-compliance",
      "products",
      "list",
      { compliance_status: "restricted", limit: 25 },
    ]);
  });

  it("productsList() with no args defaults to an empty filters object", () => {
    expect(adminComplianceQueryKeys.productsList()).toEqual([
      "admin-compliance",
      "products",
      "list",
      {},
    ]);
  });

  it("productsList(undefined) is stable and equal to productsList()", () => {
    expect(adminComplianceQueryKeys.productsList(undefined)).toEqual(
      adminComplianceQueryKeys.productsList(),
    );
  });

  it("products() is a prefix of productsList(filters)", () => {
    const prefix = adminComplianceQueryKeys.products();
    const concrete = adminComplianceQueryKeys.productsList({ q: "milk" });
    expect(concrete.slice(0, prefix.length)).toEqual([...prefix]);
  });

  it("summary() and productsList() keys are distinct (no prefix collision)", () => {
    const summary = adminComplianceQueryKeys.summary();
    const products = adminComplianceQueryKeys.productsList();
    // Neither key may be a prefix of the other beyond the shared root.
    expect(summary).not.toEqual(products);
    // After the shared root, the two surfaces diverge at index 1.
    expect(summary[1]).toBe("summary");
    expect(products[1]).toBe("products");
  });

  it("all keys share the 'admin-compliance' root so a single invalidation nukes both surfaces", () => {
    const summary = adminComplianceQueryKeys.summary();
    const products = adminComplianceQueryKeys.productsList();
    const root = adminComplianceQueryKeys.all;
    expect(summary.slice(0, root.length)).toEqual([...root]);
    expect(products.slice(0, root.length)).toEqual([...root]);
  });

  it("does not include store context, user context, role, or route path in any key", () => {
    const keys = [
      adminComplianceQueryKeys.all,
      adminComplianceQueryKeys.summary(),
      adminComplianceQueryKeys.products(),
      adminComplianceQueryKeys.productsList({ q: "milk" }),
    ];
    for (const key of keys) {
      for (const segment of key) {
        const json = JSON.stringify(segment);
        expect(json).not.toMatch(
          /store_id|storeId|user|role|pathname|route/i,
        );
      }
    }
  });
});
