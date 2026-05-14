// API-layer unit tests for admin-earnings.
//
// Strategy mirrors features/admin-settings/api.test.ts: stub `@/api`
// so every call resolves against a controlled `apiRequest` mock.
// Assert URL, HTTP method, and AbortSignal forwarding — exactly what
// the wire contract guarantees. No fetch, no React, no QueryClient.

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";

import { getAdminEarnings } from "./api";
import type { AdminEarningsSummary } from "./types";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const EMPTY_RESPONSE: AdminEarningsSummary = {
  delivered_orders: 0,
  subtotal_total: "0.00",
  delivery_total: "0.00",
  tip_total: "0.00",
  tax_total: "0.00",
  gross_base_total: "0.00",
  commission_total: "0.00",
  customer_paid_total: "0.00",
  commission_rate: "0.20",
  delivery_fee: "10.00",
  by_store: [],
};

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(EMPTY_RESPONSE);
});

describe("getAdminEarnings", () => {
  it("calls GET /admin/earnings with no query string", async () => {
    await getAdminEarnings();

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/earnings");
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getAdminEarnings(controller.signal);

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("returns the response body verbatim", async () => {
    const populated: AdminEarningsSummary = {
      ...EMPTY_RESPONSE,
      delivered_orders: 3,
      subtotal_total: "300.00",
      commission_total: "66.00",
      by_store: [
        {
          store_id: "00000000-0000-0000-0000-000000000001",
          store_name: "Big",
          delivered_orders: 2,
          gross_base: "220.00",
          commission: "44.00",
        },
      ],
    };
    vi.mocked(apiRequest).mockResolvedValue(populated);

    const result = await getAdminEarnings();
    expect(result).toEqual(populated);
    // Reference equality keeps the contract explicit: nothing wraps
    // or reshapes the body in the api layer.
    expect(result).toBe(populated);
  });
});
