// F2.20.4: read-hook tests for the admin-compliance products queue
// hook.
//
// Strategy mirrors the summary-hook tests: stub the api layer, mount
// only a QueryClientProvider, assert call args + AbortSignal +
// canonical cache key + error propagation + no fake fallback.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useAdminComplianceProductsQuery } from "../useAdminComplianceProductsQuery";
import { adminComplianceQueryKeys } from "../queryKeys";
import * as adminComplianceApi from "../../api";
import type { AdminComplianceProductsListResponse } from "../../types";

vi.mock("../../api", () => ({
  getAdminComplianceSummary: vi.fn(),
  getAdminComplianceProducts: vi.fn(),
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

const EMPTY_QUEUE: AdminComplianceProductsListResponse = {
  items: [],
  total: 0,
  limit: 50,
  offset: 0,
};

beforeEach(() => {
  vi.mocked(adminComplianceApi.getAdminComplianceProducts).mockReset();
  vi.mocked(
    adminComplianceApi.getAdminComplianceProducts,
  ).mockResolvedValue(EMPTY_QUEUE);
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useAdminComplianceProductsQuery", () => {
  it("calls getAdminComplianceProducts with the filters and lands the result on the canonical key", async () => {
    const client = makeQueryClient();
    const filters = {
      limit: 25,
      offset: 0,
      compliance_status: "restricted" as const,
    };

    const { result } = renderHook(
      () => useAdminComplianceProductsQuery(filters),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(
      adminComplianceApi.getAdminComplianceProducts,
    ).toHaveBeenCalledTimes(1);
    const [forwardedFilters, signal] = vi.mocked(
      adminComplianceApi.getAdminComplianceProducts,
    ).mock.calls[0];
    expect(forwardedFilters).toEqual(filters);
    // TanStack provides an AbortSignal on the queryFn context; the
    // hook MUST thread it through to enable cancellation on unmount.
    expect(signal).toBeInstanceOf(AbortSignal);

    const expectedKey = adminComplianceQueryKeys.productsList(filters);
    expect(expectedKey).toEqual([
      "admin-compliance",
      "products",
      "list",
      filters,
    ]);
    expect(client.getQueryData(expectedKey)).toEqual(EMPTY_QUEUE);
  });

  it("defaults to an empty filters object when called with no args", async () => {
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useAdminComplianceProductsQuery(),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const expectedKey = adminComplianceQueryKeys.productsList();
    expect(expectedKey).toEqual([
      "admin-compliance",
      "products",
      "list",
      {},
    ]);
    expect(client.getQueryData(expectedKey)).toEqual(EMPTY_QUEUE);
  });

  it("exposes the successful response data verbatim", async () => {
    const payload: AdminComplianceProductsListResponse = {
      items: [
        {
          id: "11111111-1111-1111-1111-111111111111",
          name: "Restricted Vape",
          brand: "NubeBrand",
          category: "vape",
          description: null,
          compliance_status: "restricted",
          allowed_for_sale: true,
          is_active: true,
          hold_reason: null,
          jurisdiction: "FL",
          last_compliance_check: "2026-05-12T18:00:00Z",
          approval_status: "approved",
          proposed_by_store_id: null,
          proposed_by_user_id: null,
          reviewed_by_user_id: null,
          reviewed_at: null,
          rejection_reason: null,
          created_at: "2026-05-10T12:00:00Z",
          updated_at: "2026-05-12T18:00:00Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    };
    vi.mocked(
      adminComplianceApi.getAdminComplianceProducts,
    ).mockResolvedValue(payload);

    const client = makeQueryClient();
    const { result } = renderHook(
      () => useAdminComplianceProductsQuery(),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(payload);
  });

  it("renders without an AuthProvider or StoreProvider in the tree", async () => {
    const client = makeQueryClient();
    const { result } = renderHook(
      () => useAdminComplianceProductsQuery(),
      { wrapper: makeWrapper(client) },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(EMPTY_QUEUE);
  });

  it("never generates fake queue rows when the API resolves to an empty list", async () => {
    vi.mocked(
      adminComplianceApi.getAdminComplianceProducts,
    ).mockResolvedValue(EMPTY_QUEUE);

    const client = makeQueryClient();
    const { result } = renderHook(
      () => useAdminComplianceProductsQuery(),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toEqual([]);
    expect(result.current.data?.total).toBe(0);
  });

  it("surfaces API errors via result.error (no client-side rewrite)", async () => {
    const apiError = new Error("403 Forbidden");
    vi.mocked(
      adminComplianceApi.getAdminComplianceProducts,
    ).mockRejectedValue(apiError);

    const client = makeQueryClient();
    const { result } = renderHook(
      () => useAdminComplianceProductsQuery(),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(apiError);
  });
});
