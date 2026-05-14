// Read-hook tests for the admin-settings snapshot hook.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useAdminSettingsQuery } from "../useAdminSettingsQuery";
import { adminSettingsKeys } from "../queryKeys";
import * as adminSettingsApi from "../../api";
import type { AdminSettingsResponse } from "../../types";

vi.mock("../../api", () => ({
  getAdminSettings: vi.fn(),
}));

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });
}

function makeWrapper(client: QueryClient) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>{children}</QueryClientProvider>
    );
  };
}

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
  notifications: { event_types: ["order.created"] },
  admin_preferences: {
    admin_total: 0,
    admin_active: 0,
    default_locale: "en-US",
    default_timezone: "America/New_York",
  },
};

beforeEach(() => {
  vi.mocked(adminSettingsApi.getAdminSettings).mockReset();
  vi.mocked(adminSettingsApi.getAdminSettings).mockResolvedValue(
    EMPTY_RESPONSE,
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useAdminSettingsQuery", () => {
  it("calls getAdminSettings and lands the result on the canonical key", async () => {
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminSettingsQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(adminSettingsApi.getAdminSettings).toHaveBeenCalledTimes(1);
    const [signal] = vi.mocked(adminSettingsApi.getAdminSettings).mock
      .calls[0];
    expect(signal).toBeInstanceOf(AbortSignal);

    const expectedKey = adminSettingsKeys.snapshot();
    expect(expectedKey).toEqual(["admin-settings", "snapshot"]);
    expect(client.getQueryData(expectedKey)).toEqual(EMPTY_RESPONSE);
  });

  it("exposes the successful response data verbatim", async () => {
    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminSettingsQuery(), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(EMPTY_RESPONSE);
  });

  it("renders without an AuthProvider or StoreProvider in the tree", async () => {
    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminSettingsQuery(), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(EMPTY_RESPONSE);
  });

  it("surfaces API errors via result.error (no client-side rewrite)", async () => {
    const apiError = new Error("403 Forbidden");
    vi.mocked(adminSettingsApi.getAdminSettings).mockRejectedValue(apiError);

    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminSettingsQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(apiError);
  });
});
