// F2.18.2A: query-key factory unit tests for the admin stores module.
//
// Pure unit tests on the key factory — no React, no QueryClient. We
// assert the shape of every key the brief calls out and the prefix
// relationships used by mutation invalidations.

import { describe, expect, it } from "vitest";

import { adminStoresKeys } from "../queryKeys";

const STORE_ID = "11111111-1111-1111-1111-111111111111";
const OTHER_ID = "22222222-2222-2222-2222-222222222222";

describe("adminStoresKeys", () => {
  it("anchors every key under the 'stores' root", () => {
    expect(adminStoresKeys.all).toEqual(["stores"]);
  });

  it("lists() returns the prefix shared by every list call", () => {
    expect(adminStoresKeys.lists()).toEqual(["stores", "list"]);
  });

  it("list(filters) appends the filters object verbatim", () => {
    expect(
      adminStoresKeys.list({ limit: 25, is_active: false, q: "x" }),
    ).toEqual([
      "stores",
      "list",
      { limit: 25, is_active: false, q: "x" },
    ]);
  });

  it("list() with no args defaults to an empty filters object", () => {
    expect(adminStoresKeys.list()).toEqual(["stores", "list", {}]);
  });

  it("lists() is a prefix of list(filters)", () => {
    const prefix = adminStoresKeys.lists();
    const concrete = adminStoresKeys.list({ q: "warehouse" });
    expect(concrete.slice(0, prefix.length)).toEqual([...prefix]);
  });

  it("detail(storeId) returns ['stores','detail', id]", () => {
    expect(adminStoresKeys.detail(STORE_ID)).toEqual([
      "stores",
      "detail",
      STORE_ID,
    ]);
  });

  it("details() is a prefix of detail(id)", () => {
    const prefix = adminStoresKeys.details();
    const concrete = adminStoresKeys.detail(STORE_ID);
    expect(concrete.slice(0, prefix.length)).toEqual([...prefix]);
  });

  it("list and detail keys never collide (different root segments)", () => {
    expect(adminStoresKeys.list({ q: "x" })[1]).toBe("list");
    expect(adminStoresKeys.detail(STORE_ID)[1]).toBe("detail");
    expect(adminStoresKeys.list({ q: STORE_ID })).not.toEqual(
      adminStoresKeys.detail(STORE_ID),
    );
  });

  it("two detail keys for different ids are distinct", () => {
    expect(adminStoresKeys.detail(STORE_ID)).not.toEqual(
      adminStoresKeys.detail(OTHER_ID),
    );
  });

  it("namespace is disjoint from the singular `store` feature cache root", () => {
    // The own-store feature uses ['store', ...]; the admin feature
    // uses ['stores', ...]. They share no prefix so an invalidation
    // on one cannot accidentally hit the other.
    expect(adminStoresKeys.all).not.toEqual(["store"]);
    expect(adminStoresKeys.all[0]).toBe("stores");
  });
});
