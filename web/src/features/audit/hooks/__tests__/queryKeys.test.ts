// F2.16.4: dedicated query-key tests for the audit module.
//
// `useStoreInventoryLogsQuery.test.tsx` already covers a subset of
// key-shape assertions for the legacy surface; this file is the
// canonical place for query-key contract tests now that the
// feature exposes two namespaces (legacy `storeInventoryLogs` +
// unified `storeFeed`).
//
// What we lock in:
//   - `all` root is `["audit"]`.
//   - Legacy keys still produce the same shape they did in F2.10.
//   - `storeFeeds()` is the cross-store prefix for the unified
//     feed (and is a prefix of `storeFeed(...)`).
//   - `storeFeed(storeId, filters)` keys per (store, filters); the
//     filters object is always present.
//   - Legacy and unified namespaces do NOT collide (different
//     segment), so prefix-invalidating one does not flush the
//     other.
//   - Different filter snapshots produce different keys.
//   - Empty filters still produce a stable tuple shape.

import { describe, expect, it } from "vitest";

import { auditKeys } from "../queryKeys";
import type { AdminAuditFilters, StoreAuditFilters } from "../../types";

const STORE_ID = "11111111-1111-1111-1111-111111111111";
const OTHER_STORE_ID = "22222222-2222-2222-2222-222222222222";

describe("auditKeys — root namespace", () => {
  it("auditKeys.all equals ['audit']", () => {
    expect(auditKeys.all).toEqual(["audit"]);
  });

  it("exposes the three-surface factory (legacy + store feed + admin feed)", () => {
    expect(Object.keys(auditKeys).sort()).toEqual(
      [
        "all",
        "adminFeed",
        "adminFeeds",
        "storeFeed",
        "storeFeeds",
        "storeInventoryLogs",
      ].sort(),
    );
  });
});

describe("auditKeys.storeInventoryLogs (legacy, F2.10)", () => {
  it("defaults params to {} when omitted", () => {
    expect(auditKeys.storeInventoryLogs(STORE_ID)).toEqual([
      "audit",
      "store-inventory-logs",
      STORE_ID,
      {},
    ]);
  });

  it("includes the limit on the key when provided", () => {
    expect(
      auditKeys.storeInventoryLogs(STORE_ID, { limit: 50 }),
    ).toEqual(["audit", "store-inventory-logs", STORE_ID, { limit: 50 }]);
  });
});

describe("auditKeys.storeFeeds (F2.16 unified feed prefix)", () => {
  it("returns the cross-store prefix tuple", () => {
    expect(auditKeys.storeFeeds()).toEqual(["audit", "store-feed"]);
  });

  it("is a prefix of every storeFeed(...) key", () => {
    const prefix = auditKeys.storeFeeds();
    const full = auditKeys.storeFeed(STORE_ID, { limit: 50 });
    expect(full.slice(0, prefix.length)).toEqual(prefix);
  });
});

describe("auditKeys.storeFeed (F2.16 unified feed concrete key)", () => {
  it("defaults filters to {} when omitted", () => {
    expect(auditKeys.storeFeed(STORE_ID)).toEqual([
      "audit",
      "store-feed",
      STORE_ID,
      {},
    ]);
  });

  it("includes storeId and filters verbatim in the tuple", () => {
    const filters: StoreAuditFilters = {
      limit: 25,
      offset: 0,
      source: "inventory",
      action: "receipt",
    };
    expect(auditKeys.storeFeed(STORE_ID, filters)).toEqual([
      "audit",
      "store-feed",
      STORE_ID,
      filters,
    ]);
  });

  it("produces different keys for different filter snapshots", () => {
    const a = auditKeys.storeFeed(STORE_ID, { limit: 25 });
    const b = auditKeys.storeFeed(STORE_ID, { limit: 50 });
    expect(a).not.toEqual(b);
  });

  it("produces different keys for different store ids", () => {
    const a = auditKeys.storeFeed(STORE_ID);
    const b = auditKeys.storeFeed(OTHER_STORE_ID);
    expect(a).not.toEqual(b);
  });
});

describe("auditKeys — legacy / unified isolation", () => {
  it("storeInventoryLogs and storeFeed do not collide for the same storeId", () => {
    const legacy = auditKeys.storeInventoryLogs(STORE_ID);
    const feed = auditKeys.storeFeed(STORE_ID);
    expect(legacy).not.toEqual(feed);
    // Distinct second segment is the load-bearing piece of the
    // isolation contract.
    expect(legacy[1]).toBe("store-inventory-logs");
    expect(feed[1]).toBe("store-feed");
  });

  it("the legacy prefix is not a prefix of the unified concrete key", () => {
    const legacyPrefix = auditKeys.storeInventoryLogs(STORE_ID);
    const feedFull = auditKeys.storeFeed(STORE_ID);
    expect(feedFull.slice(0, legacyPrefix.length)).not.toEqual(
      legacyPrefix,
    );
  });
});

// --------------------------------------------------------------------- //
// F2.18.2B: admin global feed (GET /admin/audit)
// --------------------------------------------------------------------- //

describe("auditKeys.adminFeeds (F2.18.2B prefix)", () => {
  it("returns the admin-feed prefix tuple", () => {
    expect(auditKeys.adminFeeds()).toEqual(["audit", "admin-feed"]);
  });

  it("is a prefix of every adminFeed(...) key", () => {
    const prefix = auditKeys.adminFeeds();
    const full = auditKeys.adminFeed({ limit: 50 });
    expect(full.slice(0, prefix.length)).toEqual(prefix);
  });
});

describe("auditKeys.adminFeed (F2.18.2B concrete key)", () => {
  it("defaults filters to {} when omitted", () => {
    expect(auditKeys.adminFeed()).toEqual(["audit", "admin-feed", {}]);
  });

  it("includes the filters object verbatim in the tuple", () => {
    const filters: AdminAuditFilters = {
      limit: 25,
      offset: 0,
      store_id: STORE_ID,
      source: "inventory",
    };
    expect(auditKeys.adminFeed(filters)).toEqual([
      "audit",
      "admin-feed",
      filters,
    ]);
  });

  it("produces different keys for different filter snapshots", () => {
    const a = auditKeys.adminFeed({ limit: 25 });
    const b = auditKeys.adminFeed({ limit: 50 });
    expect(a).not.toEqual(b);
  });

  it("produces different keys for different store_id filter values", () => {
    const a = auditKeys.adminFeed({ store_id: STORE_ID });
    const b = auditKeys.adminFeed({ store_id: OTHER_STORE_ID });
    expect(a).not.toEqual(b);
  });

  it("has no storeId path segment (admin feed has no path id)", () => {
    // The tuple should be exactly ["audit", "admin-feed", filters]
    // — three elements, never four. Compare to storeFeed which is
    // four elements (...., storeId, filters).
    expect(auditKeys.adminFeed({ store_id: STORE_ID })).toHaveLength(3);
    expect(auditKeys.storeFeed(STORE_ID)).toHaveLength(4);
  });
});

describe("auditKeys — admin / store-scoped isolation", () => {
  it("adminFeed and storeFeed never collide", () => {
    const admin = auditKeys.adminFeed({ store_id: STORE_ID });
    const store = auditKeys.storeFeed(STORE_ID);
    expect(admin).not.toEqual(store);
    expect(admin[1]).toBe("admin-feed");
    expect(store[1]).toBe("store-feed");
  });

  it("invalidating adminFeeds() prefix does not match a storeFeed key", () => {
    const adminPrefix = auditKeys.adminFeeds();
    const storeFull = auditKeys.storeFeed(STORE_ID, { limit: 10 });
    // A prefix match would mean storeFull.startsWith(adminPrefix);
    // confirm the second segment is different so prefix-invalidation
    // on admin-feed never flushes store-feed slots.
    expect(storeFull.slice(0, adminPrefix.length)).not.toEqual(adminPrefix);
  });

  it("admin and store-scoped feeds share only the 'audit' root", () => {
    const admin = auditKeys.adminFeed();
    const store = auditKeys.storeFeed(STORE_ID);
    expect(admin[0]).toBe("audit");
    expect(store[0]).toBe("audit");
    expect(admin[1]).not.toBe(store[1]);
  });
});
