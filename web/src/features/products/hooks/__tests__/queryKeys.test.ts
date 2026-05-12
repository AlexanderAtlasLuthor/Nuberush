// F2.8.2: query-key factory unit tests.
//
// Pure unit tests on the key factory — no React, no QueryClient. We
// assert the shape of every key the brief calls out and the prefix
// relationships used by mutation invalidations.

import { describe, expect, it } from "vitest";

import { productsKeys } from "../queryKeys";

const PRODUCT_ID = "11111111-1111-1111-1111-111111111111";

describe("productsKeys", () => {
  it("anchors every key under the 'products' root", () => {
    expect(productsKeys.all).toEqual(["products"]);
  });

  it("lists() returns the prefix shared by every list call", () => {
    expect(productsKeys.lists()).toEqual(["products", "list"]);
  });

  it("list(filters) appends the filters object verbatim", () => {
    expect(productsKeys.list({ only_active: true, limit: 25 })).toEqual([
      "products",
      "list",
      { only_active: true, limit: 25 },
    ]);
  });

  it("list() with no args defaults to an empty filters object", () => {
    expect(productsKeys.list()).toEqual(["products", "list", {}]);
  });

  it("lists() is a prefix of list(filters)", () => {
    const prefix = productsKeys.lists();
    const concrete = productsKeys.list({ category: "vape" });
    expect(concrete.slice(0, prefix.length)).toEqual([...prefix]);
  });

  it("detail(productId) returns ['products','detail', id]", () => {
    expect(productsKeys.detail(PRODUCT_ID)).toEqual([
      "products",
      "detail",
      PRODUCT_ID,
    ]);
  });

  it("details() is a prefix of detail(id)", () => {
    const prefix = productsKeys.details();
    const concrete = productsKeys.detail(PRODUCT_ID);
    expect(concrete.slice(0, prefix.length)).toEqual([...prefix]);
  });

  it("variants(productId) returns the prefix used by mutation invalidations", () => {
    expect(productsKeys.variants(PRODUCT_ID)).toEqual([
      "products",
      "variants",
      PRODUCT_ID,
    ]);
  });

  it("variantsList(productId, params) extends variants(id) with the params object", () => {
    expect(
      productsKeys.variantsList(PRODUCT_ID, { only_active: true }),
    ).toEqual([
      "products",
      "variants",
      PRODUCT_ID,
      { only_active: true },
    ]);
  });

  it("variants(productId) is a prefix of variantsList(productId, params)", () => {
    const prefix = productsKeys.variants(PRODUCT_ID);
    const concrete = productsKeys.variantsList(PRODUCT_ID, {
      only_active: false,
    });
    expect(concrete.slice(0, prefix.length)).toEqual([...prefix]);
  });

  it("sellable(productId) returns ['products','sellable', id]", () => {
    expect(productsKeys.sellable(PRODUCT_ID)).toEqual([
      "products",
      "sellable",
      PRODUCT_ID,
    ]);
  });

  it("complianceAudit(productId) returns ['products','complianceAudit', id]", () => {
    expect(productsKeys.complianceAudit(PRODUCT_ID)).toEqual([
      "products",
      "complianceAudit",
      PRODUCT_ID,
    ]);
  });

  it("keeps every namespace disjoint at index 1 so unrelated invalidations cannot collide", () => {
    expect(productsKeys.lists()[1]).toBe("list");
    expect(productsKeys.details()[1]).toBe("detail");
    expect(productsKeys.variants(PRODUCT_ID)[1]).toBe("variants");
    expect(productsKeys.sellable(PRODUCT_ID)[1]).toBe("sellable");
    expect(productsKeys.complianceAudit(PRODUCT_ID)[1]).toBe(
      "complianceAudit",
    );
  });
});
