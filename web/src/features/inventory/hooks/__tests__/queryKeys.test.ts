// F2.18.2C: query-key factory tests for the inventory module.
//
// Locks down both the existing store-scoped key shapes (so admin
// additions are provably additive) and the new admin keys
// (`adminLists`, `adminList`). No React, no QueryClient.

import { describe, expect, it } from "vitest";

import { inventoryKeys } from "../queryKeys";
import type { AdminInventoryFilters } from "../../types";

const STORE_ID = "11111111-1111-1111-1111-111111111111";
const OTHER_STORE_ID = "22222222-2222-2222-2222-222222222222";
const ITEM_ID = "33333333-3333-3333-3333-333333333333";

// --------------------------------------------------------------------- //
// Root + existing surface (regression — must stay unchanged)
// --------------------------------------------------------------------- //

describe("inventoryKeys — root + existing surface", () => {
  it("anchors every key under the 'inventory' root", () => {
    expect(inventoryKeys.all).toEqual(["inventory"]);
  });

  it("exposes the F2.6.0 + F2.18.2C surface", () => {
    expect(Object.keys(inventoryKeys).sort()).toEqual(
      [
        "all",
        "adminList",
        "adminLists",
        "item",
        "itemLogs",
        "items",
        "list",
        "lists",
      ].sort(),
    );
  });

  it("store-scoped lists() unchanged", () => {
    expect(inventoryKeys.lists()).toEqual(["inventory", "list"]);
  });

  it("store-scoped list(storeId, params) unchanged", () => {
    expect(
      inventoryKeys.list(STORE_ID, { limit: 25, offset: 0 }),
    ).toEqual(["inventory", "list", STORE_ID, { limit: 25, offset: 0 }]);
  });

  it("items() / item(itemId) unchanged", () => {
    expect(inventoryKeys.items()).toEqual(["inventory", "item"]);
    expect(inventoryKeys.item(ITEM_ID)).toEqual([
      "inventory",
      "item",
      ITEM_ID,
    ]);
  });

  it("itemLogs(itemId) defaults params to {}", () => {
    expect(inventoryKeys.itemLogs(ITEM_ID)).toEqual([
      "inventory",
      "item",
      ITEM_ID,
      "logs",
      {},
    ]);
  });
});

// --------------------------------------------------------------------- //
// F2.18.2C: admin global feed
// --------------------------------------------------------------------- //

describe("inventoryKeys.adminLists (F2.18.2C prefix)", () => {
  it("returns the admin prefix tuple", () => {
    expect(inventoryKeys.adminLists()).toEqual([
      "inventory",
      "admin",
      "list",
    ]);
  });

  it("is a prefix of every adminList(...) key", () => {
    const prefix = inventoryKeys.adminLists();
    const full = inventoryKeys.adminList({ limit: 50 });
    expect(full.slice(0, prefix.length)).toEqual(prefix);
  });
});

describe("inventoryKeys.adminList (F2.18.2C concrete key)", () => {
  it("defaults filters to {} when omitted", () => {
    expect(inventoryKeys.adminList()).toEqual([
      "inventory",
      "admin",
      "list",
      {},
    ]);
  });

  it("includes the filters object verbatim in the tuple", () => {
    const filters: AdminInventoryFilters = {
      limit: 25,
      offset: 0,
      store_id: STORE_ID,
      low_stock: true,
      status: "available",
    };
    expect(inventoryKeys.adminList(filters)).toEqual([
      "inventory",
      "admin",
      "list",
      filters,
    ]);
  });

  it("produces different keys for different filter snapshots", () => {
    const a = inventoryKeys.adminList({ limit: 25 });
    const b = inventoryKeys.adminList({ limit: 50 });
    expect(a).not.toEqual(b);
  });

  it("produces different keys for different store_id filter values", () => {
    const a = inventoryKeys.adminList({ store_id: STORE_ID });
    const b = inventoryKeys.adminList({ store_id: OTHER_STORE_ID });
    expect(a).not.toEqual(b);
  });

  it("treats store_id as a filter, never as a path segment", () => {
    // admin tuple length = 4 (root + "admin" + "list" + filters)
    // store-scoped list tuple length = 4 too but second segment is
    // "list", not "admin", so they cannot collide.
    expect(inventoryKeys.adminList({ store_id: STORE_ID })).toHaveLength(4);
    expect(inventoryKeys.adminList({ store_id: STORE_ID })[1]).toBe(
      "admin",
    );
  });
});

// --------------------------------------------------------------------- //
// Admin / store-scoped isolation
// --------------------------------------------------------------------- //

describe("inventoryKeys — admin / store-scoped isolation", () => {
  it("adminList and store-scoped list never collide", () => {
    const admin = inventoryKeys.adminList({ store_id: STORE_ID });
    const store = inventoryKeys.list(STORE_ID, { limit: 100, offset: 0 });
    expect(admin).not.toEqual(store);
    expect(admin[1]).toBe("admin");
    expect(store[1]).toBe("list");
  });

  it("invalidating store-scoped lists() does not prefix-match the admin key", () => {
    const storeListsPrefix = inventoryKeys.lists();
    const adminFull = inventoryKeys.adminList({ store_id: STORE_ID });
    expect(adminFull.slice(0, storeListsPrefix.length)).not.toEqual(
      storeListsPrefix,
    );
  });

  it("invalidating adminLists() does not prefix-match a store-scoped list key", () => {
    const adminListsPrefix = inventoryKeys.adminLists();
    const storeFull = inventoryKeys.list(STORE_ID, {
      limit: 100,
      offset: 0,
    });
    expect(storeFull.slice(0, adminListsPrefix.length)).not.toEqual(
      adminListsPrefix,
    );
  });
});
