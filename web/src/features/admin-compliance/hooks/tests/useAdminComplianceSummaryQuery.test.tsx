// F2.20.4: read-hook tests for the admin-compliance summary hook.
//
// Strategy: stub `../../api` so the queryFn never touches the real
// transport. Render the hook inside a fresh QueryClient so cache
// state is isolated between cases. We assert:
//
//   - which API function the hook calls
//   - that it forwards TanStack's AbortSignal
//   - the canonical cache key the result lands under
//   - that the hook needs no auth / store context
//   - that the hook never generates fake fallback KPI data
//   - that API errors propagate to result.error

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useAdminComplianceSummaryQuery } from "../useAdminComplianceSummaryQuery";
import { adminComplianceQueryKeys } from "../queryKeys";
import * as adminComplianceApi from "../../api";
import type { AdminComplianceSummary } from "../../types";

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

const EMPTY_SUMMARY: AdminComplianceSummary = {
  products: {
    total: 0,
    allowed: 0,
    restricted: 0,
    banned: 0,
    blocked: 0,
    allowed_for_sale: 0,
    not_allowed_for_sale: 0,
    inactive: 0,
  },
  reviews: { recent_count: 0, recent: [] },
  queue: { total: 0, banned: 0, restricted: 0, not_allowed_for_sale: 0 },
};

beforeEach(() => {
  vi.mocked(adminComplianceApi.getAdminComplianceSummary).mockReset();
  vi.mocked(adminComplianceApi.getAdminComplianceSummary).mockResolvedValue(
    EMPTY_SUMMARY,
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("useAdminComplianceSummaryQuery", () => {
  it("calls getAdminComplianceSummary and lands the result on the canonical key", async () => {
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminComplianceSummaryQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(adminComplianceApi.getAdminComplianceSummary).toHaveBeenCalledTimes(
      1,
    );
    const [signal] = vi.mocked(
      adminComplianceApi.getAdminComplianceSummary,
    ).mock.calls[0];
    // TanStack provides an AbortSignal on the queryFn context; the
    // hook MUST thread it through to enable cancellation on unmount.
    expect(signal).toBeInstanceOf(AbortSignal);

    const expectedKey = adminComplianceQueryKeys.summary();
    expect(expectedKey).toEqual(["admin-compliance", "summary"]);
    expect(client.getQueryData(expectedKey)).toEqual(EMPTY_SUMMARY);
  });

  it("exposes the successful response data verbatim", async () => {
    const seeded: AdminComplianceSummary = {
      products: {
        total: 12,
        allowed: 7,
        restricted: 3,
        banned: 2,
        blocked: 5,
        allowed_for_sale: 8,
        not_allowed_for_sale: 4,
        inactive: 1,
      },
      reviews: {
        recent_count: 1,
        recent: [
          {
            id: "33333333-3333-3333-3333-333333333333",
            product_id: "11111111-1111-1111-1111-111111111111",
            previous_compliance_status: "allowed",
            new_compliance_status: "restricted",
            previous_allowed_for_sale: true,
            new_allowed_for_sale: true,
            reason: "routine review",
            changed_by_user_id: null,
            created_at: "2026-05-13T12:00:00Z",
          },
        ],
      },
      queue: {
        total: 5,
        banned: 2,
        restricted: 3,
        not_allowed_for_sale: 4,
      },
    };
    vi.mocked(
      adminComplianceApi.getAdminComplianceSummary,
    ).mockResolvedValue(seeded);

    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminComplianceSummaryQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(seeded);
  });

  it("renders without an AuthProvider or StoreProvider in the tree", async () => {
    // The wrapper only mounts QueryClientProvider — no AuthProvider,
    // no StoreProvider. If the hook accidentally read either context
    // via `useAuth` / `useStoreContext`, this test would throw at
    // render time. We assert it does not.
    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminComplianceSummaryQuery(), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(EMPTY_SUMMARY);
  });

  it("never generates fake fallback KPI data when the API resolves to zeros", async () => {
    vi.mocked(
      adminComplianceApi.getAdminComplianceSummary,
    ).mockResolvedValue(EMPTY_SUMMARY);

    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminComplianceSummaryQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.products.total).toBe(0);
    expect(result.current.data?.products.blocked).toBe(0);
    expect(result.current.data?.queue.total).toBe(0);
    expect(result.current.data?.reviews.recent).toEqual([]);
  });

  it("surfaces API errors via result.error (no client-side rewrite)", async () => {
    const apiError = new Error("403 Forbidden");
    vi.mocked(
      adminComplianceApi.getAdminComplianceSummary,
    ).mockRejectedValue(apiError);

    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminComplianceSummaryQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(apiError);
  });
});
