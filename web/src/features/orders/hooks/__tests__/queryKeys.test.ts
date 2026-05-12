// F2.18.2C: query-key factory tests for the orders module.
//
// Locks down both the existing store-scoped key shapes (so admin
// additions are provably additive) and the new admin keys
// (`adminLists`, `adminList`).

import { describe, expect, it } from "vitest";

import { ordersKeys } from "../queryKeys";
import type { AdminOrdersFilters } from "../../types";

const STORE_ID = "11111111-1111-1111-1111-111111111111";
const OTHER_STORE_ID = "22222222-2222-2222-2222-222222222222";
const ORDER_ID = "33333333-3333-3333-3333-333333333333";

// --------------------------------------------------------------------- //
// Root + existing surface (regression — must stay unchanged)
// --------------------------------------------------------------------- //

describe("ordersKeys — root + existing surface", () => {
  it("anchors every key under the 'orders' root", () => {
    expect(ordersKeys.all).toEqual(["orders"]);
  });

  it("exposes the F2.7.0 + F2.18.2C surface", () => {
    expect(Object.keys(ordersKeys).sort()).toEqual(
      [
        "all",
        "adminList",
        "adminLists",
        "auditLogs",
        "item",
        "items",
        "list",
        "lists",
      ].sort(),
    );
  });

  it("store-scoped lists() unchanged", () => {
    expect(ordersKeys.lists()).toEqual(["orders", "list"]);
  });

  it("store-scoped list(storeId, params) unchanged", () => {
    expect(
      ordersKeys.list(STORE_ID, { limit: 25, offset: 0 }),
    ).toEqual(["orders", "list", STORE_ID, { limit: 25, offset: 0 }]);
  });

  it("items() / item(orderId) unchanged", () => {
    expect(ordersKeys.items()).toEqual(["orders", "item"]);
    expect(ordersKeys.item(ORDER_ID)).toEqual([
      "orders",
      "item",
      ORDER_ID,
    ]);
  });

  it("auditLogs(orderId) unchanged", () => {
    expect(ordersKeys.auditLogs(ORDER_ID)).toEqual([
      "orders",
      "auditLogs",
      ORDER_ID,
    ]);
  });
});

// --------------------------------------------------------------------- //
// F2.18.2C: admin global feed
// --------------------------------------------------------------------- //

describe("ordersKeys.adminLists (F2.18.2C prefix)", () => {
  it("returns the admin prefix tuple", () => {
    expect(ordersKeys.adminLists()).toEqual(["orders", "admin", "list"]);
  });

  it("is a prefix of every adminList(...) key", () => {
    const prefix = ordersKeys.adminLists();
    const full = ordersKeys.adminList({ limit: 50 });
    expect(full.slice(0, prefix.length)).toEqual(prefix);
  });
});

describe("ordersKeys.adminList (F2.18.2C concrete key)", () => {
  it("defaults filters to {} when omitted", () => {
    expect(ordersKeys.adminList()).toEqual([
      "orders",
      "admin",
      "list",
      {},
    ]);
  });

  it("includes the filters object verbatim in the tuple", () => {
    const filters: AdminOrdersFilters = {
      limit: 25,
      offset: 0,
      store_id: STORE_ID,
      status: "pending",
      date_from: "2026-01-01T00:00:00Z",
      date_to: "2026-12-31T23:59:59Z",
    };
    expect(ordersKeys.adminList(filters)).toEqual([
      "orders",
      "admin",
      "list",
      filters,
    ]);
  });

  it("produces different keys for different filter snapshots", () => {
    const a = ordersKeys.adminList({ limit: 25 });
    const b = ordersKeys.adminList({ limit: 50 });
    expect(a).not.toEqual(b);
  });

  it("produces different keys for different store_id filter values", () => {
    const a = ordersKeys.adminList({ store_id: STORE_ID });
    const b = ordersKeys.adminList({ store_id: OTHER_STORE_ID });
    expect(a).not.toEqual(b);
  });

  it("treats store_id as a filter, never as a path segment", () => {
    expect(ordersKeys.adminList({ store_id: STORE_ID })).toHaveLength(4);
    expect(ordersKeys.adminList({ store_id: STORE_ID })[1]).toBe("admin");
  });
});

// --------------------------------------------------------------------- //
// Admin / store-scoped isolation
// --------------------------------------------------------------------- //

describe("ordersKeys — admin / store-scoped isolation", () => {
  it("adminList and store-scoped list never collide", () => {
    const admin = ordersKeys.adminList({ store_id: STORE_ID });
    const store = ordersKeys.list(STORE_ID, { limit: 100, offset: 0 });
    expect(admin).not.toEqual(store);
    expect(admin[1]).toBe("admin");
    expect(store[1]).toBe("list");
  });

  it("invalidating store-scoped lists() does not prefix-match the admin key", () => {
    const storeListsPrefix = ordersKeys.lists();
    const adminFull = ordersKeys.adminList({ store_id: STORE_ID });
    expect(adminFull.slice(0, storeListsPrefix.length)).not.toEqual(
      storeListsPrefix,
    );
  });

  it("invalidating adminLists() does not prefix-match a store-scoped list key", () => {
    const adminListsPrefix = ordersKeys.adminLists();
    const storeFull = ordersKeys.list(STORE_ID, {
      limit: 100,
      offset: 0,
    });
    expect(storeFull.slice(0, adminListsPrefix.length)).not.toEqual(
      adminListsPrefix,
    );
  });
});
