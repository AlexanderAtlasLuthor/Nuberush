// Read-hook tests for the admin-earnings snapshot hook.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useAdminEarningsQuery } from "../useAdminEarningsQuery";
import { adminEarningsKeys } from "../queryKeys";
import * as adminEarningsApi from "../../api";
import type { AdminEarningsSummary } from "../../types";

vi.mock("../../api", () => ({
  getAdminEarnings: vi.fn(),
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

const RESPONSE: AdminEarningsSummary = {
  delivered_orders: 2,
  subtotal_total: "100.00",
  delivery_total: "20.00",
  tip_total: "0.00",
  tax_total: "8.00",
  gross_base_total: "128.00",
  commission_total: "25.60",
  customer_paid_total: "153.60",
  commission_rate: "0.20",
  delivery_fee: "10.00",
  by_store: [],
};

beforeEach(() => {
  vi.mocked(adminEarningsApi.getAdminEarnings).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useAdminEarningsQuery", () => {
  it("invokes getAdminEarnings exactly once on mount", async () => {
    vi.mocked(adminEarningsApi.getAdminEarnings).mockResolvedValue(
      RESPONSE,
    );
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminEarningsQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(adminEarningsApi.getAdminEarnings).toHaveBeenCalledTimes(1);
  });

  it("exposes the wire body verbatim through data", async () => {
    vi.mocked(adminEarningsApi.getAdminEarnings).mockResolvedValue(
      RESPONSE,
    );
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminEarningsQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(RESPONSE);
  });

  it("mounts the query under adminEarningsKeys.summary()", async () => {
    vi.mocked(adminEarningsApi.getAdminEarnings).mockResolvedValue(
      RESPONSE,
    );
    const client = makeQueryClient();

    renderHook(() => useAdminEarningsQuery(), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() =>
      expect(
        client.getQueryData(adminEarningsKeys.summary()),
      ).toBeDefined(),
    );
    expect(client.getQueryData(adminEarningsKeys.summary())).toEqual(
      RESPONSE,
    );
  });

  it("surfaces ApiError as isError", async () => {
    const failure = new Error("forbidden");
    vi.mocked(adminEarningsApi.getAdminEarnings).mockRejectedValue(
      failure,
    );
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminEarningsQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(failure);
  });

  it("forwards the React Query AbortSignal", async () => {
    vi.mocked(adminEarningsApi.getAdminEarnings).mockResolvedValue(
      RESPONSE,
    );
    const client = makeQueryClient();

    renderHook(() => useAdminEarningsQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() =>
      expect(adminEarningsApi.getAdminEarnings).toHaveBeenCalledTimes(1),
    );
    const arg = vi.mocked(adminEarningsApi.getAdminEarnings).mock
      .calls[0][0];
    // queryFn is invoked with a real AbortSignal supplied by RQ.
    expect(arg).toBeInstanceOf(AbortSignal);
  });
});
