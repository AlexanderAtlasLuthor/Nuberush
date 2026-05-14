// API-layer unit tests for store-earnings.
//
// Same strategy as features/admin-earnings/api.test.ts: stub `@/api`,
// assert the path / method / signal, and confirm storeId is
// URL-encoded into the path.

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";

import { getStoreEarnings } from "./api";
import type { StoreEarningsSummary } from "./types";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";

const EMPTY_RESPONSE: StoreEarningsSummary = {
  delivered_orders: 0,
  total_items_sold: 0,
  product_revenue: "0.00",
  top_products: [],
};

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(EMPTY_RESPONSE);
});

describe("getStoreEarnings", () => {
  it("calls GET /stores/{storeId}/earnings", async () => {
    await getStoreEarnings({ storeId: STORE_ID });

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/earnings`);
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("URL-encodes the storeId path segment", async () => {
    // Defense in depth: even though UUIDs don't carry slashes, the
    // wrapper still runs encodeURIComponent so a misbuilt id can't
    // escape the path.
    await getStoreEarnings({ storeId: "spaces and/slashes" });
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/stores/spaces%20and%2Fslashes/earnings");
  });

  it("forwards the AbortSignal", async () => {
    const controller = new AbortController();
    await getStoreEarnings({ storeId: STORE_ID }, controller.signal);

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("returns the response body verbatim", async () => {
    const populated: StoreEarningsSummary = {
      delivered_orders: 4,
      total_items_sold: 7,
      product_revenue: "105.00",
      top_products: [
        {
          variant_id: "22222222-2222-2222-2222-222222222222",
          product_name: "Pricey",
          variant_label: "Mango · 5000 puffs",
          quantity_sold: 2,
          revenue: "100.00",
        },
      ],
    };
    vi.mocked(apiRequest).mockResolvedValue(populated);

    const result = await getStoreEarnings({ storeId: STORE_ID });
    expect(result).toBe(populated);
  });
});
