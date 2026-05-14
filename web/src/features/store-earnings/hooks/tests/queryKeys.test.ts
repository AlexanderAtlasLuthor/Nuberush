// Query-key factory unit tests for store-earnings.

import { describe, expect, it } from "vitest";

import { storeEarningsKeys } from "../queryKeys";

const STORE_ID = "11111111-1111-1111-1111-111111111111";

describe("storeEarningsKeys", () => {
  it("anchors every key under the 'store-earnings' root", () => {
    expect(storeEarningsKeys.all).toEqual(["store-earnings"]);
  });

  it("summary(storeId) keys are scoped per store", () => {
    expect(storeEarningsKeys.summary(STORE_ID)).toEqual([
      "store-earnings",
      "summary",
      STORE_ID,
    ]);
  });

  it("different storeIds produce different keys", () => {
    expect(storeEarningsKeys.summary("a")).not.toEqual(
      storeEarningsKeys.summary("b"),
    );
  });

  it("all is a prefix of every summary key", () => {
    const prefix = storeEarningsKeys.all;
    const concrete = storeEarningsKeys.summary(STORE_ID);
    expect(concrete.slice(0, prefix.length)).toEqual([...prefix]);
  });
});
