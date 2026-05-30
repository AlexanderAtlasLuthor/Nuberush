// F2.20.3: read-hook tests for the admin-products module.
//
// Strategy: stub `../../api` so the queryFn never touches the real
// transport. Render the hook inside a fresh QueryClient so cache
// state is isolated between cases. We assert:
//
//   - which API function the hook calls
//   - what arguments it forwards
//   - the canonical cache key the result lands under
//   - that the hook needs no auth / store context
//   - that the hook never generates fake fallback data

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useAdminProductsQuery } from "../useAdminProductsQuery";
import { adminProductsQueryKeys } from "../queryKeys";
import * as adminProductsApi from "../../api";
import type { AdminProductsListResponse } from "../../types";

vi.mock("../../api", () => ({
  getAdminProducts: vi.fn(),
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

const EMPTY_RESPONSE: AdminProductsListResponse = {
  items: [],
  total: 0,
  limit: 50,
  offset: 0,
};

beforeEach(() => {
  vi.mocked(adminProductsApi.getAdminProducts).mockReset();
  vi.mocked(adminProductsApi.getAdminProducts).mockResolvedValue(
    EMPTY_RESPONSE,
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useAdminProductsQuery", () => {
  it("calls getAdminProducts with the filters and lands the result on the canonical key", async () => {
    const client = makeQueryClient();
    const filters = {
      limit: 25,
      offset: 0,
      compliance_status: "restricted" as const,
    };

    const { result } = renderHook(() => useAdminProductsQuery(filters), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(adminProductsApi.getAdminProducts).toHaveBeenCalledTimes(1);
    const [forwardedFilters, signal] = vi.mocked(
      adminProductsApi.getAdminProducts,
    ).mock.calls[0];
    expect(forwardedFilters).toEqual(filters);
    // TanStack provides an AbortSignal on the queryFn context; the
    // hook MUST thread it through to enable cancellation on unmount.
    expect(signal).toBeInstanceOf(AbortSignal);

    const expectedKey = adminProductsQueryKeys.list(filters);
    expect(expectedKey).toEqual(["admin-products", "list", filters]);
    expect(client.getQueryData(expectedKey)).toEqual(EMPTY_RESPONSE);
  });

  it("defaults to an empty filters object when called with no args", async () => {
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminProductsQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const expectedKey = adminProductsQueryKeys.list();
    expect(expectedKey).toEqual(["admin-products", "list", {}]);
    expect(client.getQueryData(expectedKey)).toEqual(EMPTY_RESPONSE);
  });

  it("exposes the successful response data verbatim", async () => {
    const payload: AdminProductsListResponse = {
      items: [
        {
          id: "11111111-1111-1111-1111-111111111111",
          name: "Mango Ice",
          brand: "NubeBrand",
          category: "vape",
          description: null,
          compliance_status: "allowed",
          allowed_for_sale: true,
          is_active: true,
          hold_reason: null,
          jurisdiction: "FL",
          last_compliance_check: null,
          approval_status: "approved",
          proposed_by_store_id: null,
          proposed_by_user_id: null,
          reviewed_by_user_id: null,
          reviewed_at: null,
          rejection_reason: null,
          created_at: "2026-05-13T12:00:00Z",
          updated_at: "2026-05-13T12:00:00Z",
        },
      ],
      total: 1,
      limit: 50,
      offset: 0,
    };
    vi.mocked(adminProductsApi.getAdminProducts).mockResolvedValue(
      payload,
    );

    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminProductsQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(payload);
  });

  it("renders without an AuthProvider or StoreProvider in the tree", async () => {
    // The wrapper only mounts QueryClientProvider — no AuthProvider,
    // no StoreProvider. If the hook accidentally read either context
    // via `useAuth` / `useStoreContext`, this test would throw at
    // render time. We assert it does not.
    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminProductsQuery(), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(EMPTY_RESPONSE);
  });

  it("never generates fake fallback rows when the API resolves to an empty list", async () => {
    vi.mocked(adminProductsApi.getAdminProducts).mockResolvedValue({
      items: [],
      total: 0,
      limit: 50,
      offset: 0,
    });

    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminProductsQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items).toEqual([]);
    expect(result.current.data?.total).toBe(0);
  });

  it("surfaces API errors via result.error (no client-side rewrite)", async () => {
    const apiError = new Error("403 Forbidden");
    vi.mocked(adminProductsApi.getAdminProducts).mockRejectedValue(
      apiError,
    );

    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminProductsQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(apiError);
  });
});
