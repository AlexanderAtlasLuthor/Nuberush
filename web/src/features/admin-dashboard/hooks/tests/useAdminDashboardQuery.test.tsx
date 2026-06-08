// F2.19.3: tests for useAdminDashboardQuery.
//
// Pattern mirrors useAdminAuditQuery.test.tsx: stub `../../api` so
// the hook resolves against a controlled `getAdminDashboard` mock;
// render the hook under a fresh QueryClient; assert (a) the api
// function is called with a signal, (b) the cache key shape matches
// `adminDashboardKeys.summary()`, (c) the hook is always enabled
// (no store context required), (d) loading + error states surface,
// (e) the hook exposes no mutation API.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useAdminDashboardQuery } from "../useAdminDashboardQuery";
import { adminDashboardKeys } from "../queryKeys";
import * as adminDashboardApi from "../../api";
import type { AdminDashboardSummary } from "../../types";

vi.mock("../../api", () => ({
  getAdminDashboard: vi.fn(),
}));

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
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

function emptySummary(): AdminDashboardSummary {
  return {
    stores: { total: 0, active: 0, inactive: 0 },
    users: { total: 0, active: 0 },
    inventory: { low_stock_count: 0 },
    orders: {
      open_count: 0,
      by_status: {
        pending: 0,
        accepted: 0,
        preparing: 0,
        ready: 0,
        out_for_delivery: 0,
        delivered: 0,
        canceled: 0,
        returned: 0,
      },
      recent: [],
    },
    compliance: { blocked_count: 0 },
    products: { pending_approvals_count: 0 },
    regulatory: {
      total_alerts: 0,
      open_count: 0,
      high_or_critical_count: 0,
      hold_or_ban_count: 0,
    },
    recent_audit: [],
  };
}

beforeEach(() => {
  vi.mocked(adminDashboardApi.getAdminDashboard).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Happy path
// --------------------------------------------------------------------- //

describe("useAdminDashboardQuery — happy path", () => {
  it("calls getAdminDashboard with an AbortSignal and caches under adminDashboardKeys.summary()", async () => {
    const response: AdminDashboardSummary = {
      stores: { total: 3, active: 2, inactive: 1 },
      users: { total: 5, active: 4 },
      inventory: { low_stock_count: 1 },
      orders: {
        open_count: 2,
        by_status: {
          pending: 1,
          accepted: 1,
          preparing: 0,
          ready: 0,
          out_for_delivery: 0,
          delivered: 0,
          canceled: 0,
          returned: 0,
        },
        recent: [],
      },
      compliance: { blocked_count: 0 },
      products: { pending_approvals_count: 0 },
      regulatory: {
        total_alerts: 0,
        open_count: 0,
        high_or_critical_count: 0,
        hold_or_ban_count: 0,
      },
      recent_audit: [],
    };
    vi.mocked(adminDashboardApi.getAdminDashboard).mockResolvedValue(
      response,
    );
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminDashboardQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(adminDashboardApi.getAdminDashboard).toHaveBeenCalledTimes(1);
    const [signal] = vi.mocked(adminDashboardApi.getAdminDashboard).mock
      .calls[0];
    expect(signal).toBeInstanceOf(AbortSignal);

    expect(client.getQueryData(adminDashboardKeys.summary())).toBe(
      response,
    );
  });

  it("returns the AdminDashboardSummary unchanged (no transformation)", async () => {
    const response = emptySummary();
    vi.mocked(adminDashboardApi.getAdminDashboard).mockResolvedValue(
      response,
    );
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminDashboardQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBe(response);
  });
});

// --------------------------------------------------------------------- //
// Loading / error states
// --------------------------------------------------------------------- //

describe("useAdminDashboardQuery — pending state", () => {
  it("exposes the pending/loading state before the API resolves", async () => {
    let resolveFn: (value: AdminDashboardSummary) => void = () => {};
    const pending = new Promise<AdminDashboardSummary>((resolve) => {
      resolveFn = resolve;
    });
    vi.mocked(adminDashboardApi.getAdminDashboard).mockReturnValue(pending);

    const client = makeQueryClient();
    const { result } = renderHook(() => useAdminDashboardQuery(), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.isPending).toBe(true);
    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();

    resolveFn(emptySummary());
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe("useAdminDashboardQuery — error state", () => {
  it("propagates errors from getAdminDashboard unchanged", async () => {
    const boom = new Error("boom-from-admin-dashboard-hook");
    vi.mocked(adminDashboardApi.getAdminDashboard).mockRejectedValue(boom);
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminDashboardQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(boom);
    expect(result.current.data).toBeUndefined();
  });
});

// --------------------------------------------------------------------- //
// No store context dependency
// --------------------------------------------------------------------- //

describe("useAdminDashboardQuery — no store / auth context required", () => {
  it("fires immediately without a storeId argument or store context provider", async () => {
    vi.mocked(adminDashboardApi.getAdminDashboard).mockResolvedValue(
      emptySummary(),
    );
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminDashboardQuery(), {
      wrapper: makeWrapper(client),
    });

    // No idle state — admin dashboard has no path id and is always
    // enabled.
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(adminDashboardApi.getAdminDashboard).toHaveBeenCalledTimes(1);
  });

  it("renders without an auth/role provider (backend is the authority)", async () => {
    vi.mocked(adminDashboardApi.getAdminDashboard).mockResolvedValue(
      emptySummary(),
    );
    const client = makeQueryClient();

    // Wrapper has ONLY QueryClientProvider — no AuthProvider, no
    // StoreContext. If the hook required either, this render would
    // throw before the fetch could fire.
    const { result } = renderHook(() => useAdminDashboardQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

// --------------------------------------------------------------------- //
// Query-key wiring
// --------------------------------------------------------------------- //

describe("useAdminDashboardQuery — query key wiring", () => {
  it("uses adminDashboardKeys.summary() (two-segment, stable)", async () => {
    vi.mocked(adminDashboardApi.getAdminDashboard).mockResolvedValue(
      emptySummary(),
    );
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminDashboardQuery(), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(client.getQueryData(adminDashboardKeys.summary())).toEqual(
      emptySummary(),
    );
    // Sanity: no rogue key collides under the same cache slot.
    expect(
      client.getQueryData([
        "admin-dashboard",
        "summary",
        "unexpected-segment",
      ]),
    ).toBeUndefined();
  });
});

// --------------------------------------------------------------------- //
// No mutation surface
// --------------------------------------------------------------------- //

describe("useAdminDashboardQuery — read-only contract", () => {
  it("the returned UseQueryResult has no mutate / mutateAsync function", async () => {
    vi.mocked(adminDashboardApi.getAdminDashboard).mockResolvedValue(
      emptySummary(),
    );
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminDashboardQuery(), {
      wrapper: makeWrapper(client),
    });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // `useQuery` results never expose `mutate` / `mutateAsync` (those
    // belong to `useMutation`). The assertion is a guard against an
    // accidental future addition of a write surface to this hook.
    expect(
      (result.current as unknown as { mutate?: unknown }).mutate,
    ).toBeUndefined();
    expect(
      (result.current as unknown as { mutateAsync?: unknown }).mutateAsync,
    ).toBeUndefined();
  });
});
