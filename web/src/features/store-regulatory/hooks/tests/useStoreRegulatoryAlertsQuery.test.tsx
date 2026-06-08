import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useStoreRegulatoryAlertsQuery } from "../useStoreRegulatoryAlertsQuery";
import { useStoreRegulatoryAlertDetailQuery } from "../useStoreRegulatoryAlertDetailQuery";
import { storeRegulatoryKeys } from "../queryKeys";
import * as api from "../../api";
import type {
  StoreRegulatoryAlert,
  StoreRegulatoryAlertsResponse,
} from "../../types";

vi.mock("../../api", () => ({
  getStoreRegulatoryAlerts: vi.fn(),
  getStoreRegulatoryAlertDetail: vi.fn(),
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

const STORE_ID = "11111111-1111-1111-1111-111111111111";
const ALERT_ID = "22222222-2222-2222-2222-222222222222";

const RESPONSE: StoreRegulatoryAlertsResponse = {
  items: [
    {
      id: ALERT_ID,
      notice_id: "44444444-4444-4444-4444-444444444444",
      product_id: "33333333-3333-3333-3333-333333333333",
      severity: "high",
      status: "open",
      recommended_action: "hold",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-02T00:00:00Z",
      notice_title: "Recall",
      notice_type: "enforcement_notice",
      notice_published_at: "2025-12-31T00:00:00Z",
      product_name: "Mango Vape",
    },
  ],
  total: 1,
  limit: 25,
  offset: 0,
};

const DETAIL: StoreRegulatoryAlert = RESPONSE.items[0];

beforeEach(() => {
  vi.mocked(api.getStoreRegulatoryAlerts).mockReset();
  vi.mocked(api.getStoreRegulatoryAlertDetail).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useStoreRegulatoryAlertsQuery", () => {
  it("fetches with the correct key when storeId is present", async () => {
    vi.mocked(api.getStoreRegulatoryAlerts).mockResolvedValue(RESPONSE);
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useStoreRegulatoryAlertsQuery(`  ${STORE_ID}  `, { status: "open" }),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.getStoreRegulatoryAlerts).toHaveBeenCalledWith(
      STORE_ID,
      { status: "open" },
      expect.any(AbortSignal),
    );
    expect(result.current.data).toEqual(RESPONSE);

    const cached = client.getQueryData(
      storeRegulatoryKeys.alerts(STORE_ID, { status: "open" }),
    );
    expect(cached).toEqual(RESPONSE);
  });

  it("is disabled when storeId is missing", () => {
    const client = makeQueryClient();
    const { result } = renderHook(
      () => useStoreRegulatoryAlertsQuery(null),
      { wrapper: makeWrapper(client) },
    );

    expect(result.current.fetchStatus).toBe("idle");
    expect(api.getStoreRegulatoryAlerts).not.toHaveBeenCalled();
  });
});

describe("useStoreRegulatoryAlertDetailQuery", () => {
  it("fetches when both ids are present", async () => {
    vi.mocked(api.getStoreRegulatoryAlertDetail).mockResolvedValue(DETAIL);
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useStoreRegulatoryAlertDetailQuery(STORE_ID, ALERT_ID),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(api.getStoreRegulatoryAlertDetail).toHaveBeenCalledWith(
      STORE_ID,
      ALERT_ID,
      expect.any(AbortSignal),
    );
    expect(result.current.data).toEqual(DETAIL);
  });

  it("is disabled when storeId or alertId is missing", () => {
    const client = makeQueryClient();
    const { result } = renderHook(
      () => useStoreRegulatoryAlertDetailQuery(STORE_ID, null),
      { wrapper: makeWrapper(client) },
    );

    expect(result.current.fetchStatus).toBe("idle");
    expect(api.getStoreRegulatoryAlertDetail).not.toHaveBeenCalled();
  });
});
