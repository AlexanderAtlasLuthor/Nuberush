// API-layer unit tests for admin-settings.
//
// Strategy: stub `@/api` so every call resolves against a controlled
// `apiRequest` mock. Assert URL, HTTP method, and AbortSignal
// forwarding — exactly what the wire contract guarantees. No fetch,
// no React, no QueryClient.

import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiRequest } from "@/api";
import { getAdminSettings } from "./api";
import type { AdminSettingsResponse } from "./types";

vi.mock("@/api", () => ({
  apiRequest: vi.fn(),
}));

const EMPTY_RESPONSE: AdminSettingsResponse = {
  platform: {
    app_name: "NubeRush API",
    app_env: "development",
    app_debug: true,
    version: "0.1.0",
    default_jurisdiction: "FL",
    default_store_timezone: "America/New_York",
  },
  billing: {
    commission_rate_basis_points: 500,
    currency: "USD",
    delivered_orders_count: 0,
    delivered_orders_total_amount: "0.00",
  },
  compliance: {
    default_jurisdiction: "FL",
    allowed_count: 0,
    restricted_count: 0,
    banned_count: 0,
    blocked_count: 0,
  },
  operations: {
    default_alert_page_size: 50,
    max_alert_page_size: 200,
    default_aging_minutes: 1440,
    open_order_statuses: [
      "pending",
      "accepted",
      "preparing",
      "ready",
      "out_for_delivery",
    ],
  },
  notifications: { event_types: [] },
  admin_preferences: {
    admin_total: 0,
    admin_active: 0,
    default_locale: "en-US",
    default_timezone: "America/New_York",
  },
};

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockResolvedValue(EMPTY_RESPONSE);
});

describe("getAdminSettings", () => {
  it("calls GET /admin/settings with no query string", async () => {
    await getAdminSettings();

    expect(apiRequest).toHaveBeenCalledTimes(1);
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/admin/settings");
    expect(options?.method).toBe("GET");
    expect(options?.body).toBeUndefined();
  });

  it("forwards the AbortSignal to apiRequest", async () => {
    const controller = new AbortController();
    await getAdminSettings(controller.signal);

    const [, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(options?.signal).toBe(controller.signal);
  });

  it("returns the response body verbatim", async () => {
    const result = await getAdminSettings();
    expect(result).toEqual(EMPTY_RESPONSE);
  });
});
