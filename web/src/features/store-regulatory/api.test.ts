import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";

import {
  getStoreRegulatoryAlertDetail,
  getStoreRegulatoryAlerts,
} from "./api";
import type { StoreRegulatoryAlertsResponse } from "./types";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";
const ALERT_ID = "22222222-2222-2222-2222-222222222222";

const EMPTY: StoreRegulatoryAlertsResponse = {
  items: [],
  total: 0,
  limit: 25,
  offset: 0,
};

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(EMPTY);
});

describe("getStoreRegulatoryAlerts", () => {
  it("calls GET /stores/{storeId}/regulatory/alerts", async () => {
    await getStoreRegulatoryAlerts(STORE_ID);

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(`/stores/${STORE_ID}/regulatory/alerts`);
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("encodes all filters as query params", async () => {
    await getStoreRegulatoryAlerts(STORE_ID, {
      status: "open",
      severity: "high",
      recommended_action: "ban",
      product_id: "33333333-3333-3333-3333-333333333333",
      limit: 10,
      offset: 20,
    });

    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toContain("status=open");
    expect(path).toContain("severity=high");
    expect(path).toContain("recommended_action=ban");
    expect(path).toContain(
      "product_id=33333333-3333-3333-3333-333333333333",
    );
    expect(path).toContain("limit=10");
    expect(path).toContain("offset=20");
  });

  it("omits the query string when no filters are passed", async () => {
    await getStoreRegulatoryAlerts(STORE_ID, {});
    const [path] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).not.toContain("?");
  });

  it("propagates errors from apiRequest", async () => {
    vi.mocked(apiRequest).mockRejectedValueOnce(new Error("boom"));
    await expect(getStoreRegulatoryAlerts(STORE_ID)).rejects.toThrow("boom");
  });
});

describe("getStoreRegulatoryAlertDetail", () => {
  it("calls GET /stores/{storeId}/regulatory/alerts/{alertId}", async () => {
    await getStoreRegulatoryAlertDetail(STORE_ID, ALERT_ID);

    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe(
      `/stores/${STORE_ID}/regulatory/alerts/${ALERT_ID}`,
    );
    expect(options?.method).toBe("GET");
  });

  it("propagates errors from apiRequest", async () => {
    vi.mocked(apiRequest).mockRejectedValueOnce(new Error("nope"));
    await expect(
      getStoreRegulatoryAlertDetail(STORE_ID, ALERT_ID),
    ).rejects.toThrow("nope");
  });
});

describe("store-regulatory api surface", () => {
  it("exposes no mutation functions", async () => {
    const mod = await import("./api");
    const names = Object.keys(mod).sort();
    expect(names).toEqual([
      "getStoreRegulatoryAlertDetail",
      "getStoreRegulatoryAlerts",
    ]);
    for (const name of names) {
      expect(name).not.toMatch(/acknowledge|dismiss|resolve|mutat/i);
    }
  });
});
