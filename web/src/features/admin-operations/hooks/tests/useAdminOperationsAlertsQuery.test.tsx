// F2.19.4: tests for useAdminOperationsAlertsQuery.
//
// Pattern mirrors useAdminDashboardQuery.test.tsx and
// useAdminAuditQuery.test.tsx: stub `../../api` so the hook
// resolves against a controlled `getAdminOperationsAlerts` mock;
// render the hook under a fresh QueryClient; assert (a) the api
// function is called with the right filters + signal, (b) the
// cache key shape matches `adminOperationsKeys.alertList(...)`,
// (c) the hook is always enabled (no store context required),
// (d) loading + error states surface, (e) the hook exposes no
// mutation API, (f) changing filters routes to a distinct cache
// slot.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useAdminOperationsAlertsQuery } from "../useAdminOperationsAlertsQuery";
import { adminOperationsKeys } from "../queryKeys";
import * as adminOperationsApi from "../../api";
import type {
  AdminOperationsAlertsFilters,
  AdminOperationsAlertsListResponse,
} from "../../types";

vi.mock("../../api", () => ({
  getAdminOperationsAlerts: vi.fn(),
}));

const STORE_ID = "11111111-1111-1111-1111-111111111111";

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

function emptyResponse(): AdminOperationsAlertsListResponse {
  return { items: [], total: 0, limit: 50, offset: 0 };
}

beforeEach(() => {
  vi.mocked(adminOperationsApi.getAdminOperationsAlerts).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Happy path
// --------------------------------------------------------------------- //

describe("useAdminOperationsAlertsQuery — happy path", () => {
  it("calls getAdminOperationsAlerts with filters and caches under adminOperationsKeys.alertList(...)", async () => {
    const response: AdminOperationsAlertsListResponse = {
      items: [
        {
          id: `low_stock:${STORE_ID}`,
          category: "low_stock",
          severity: "high",
          store_id: STORE_ID,
          entity_type: "inventory_item",
          entity_id: "44444444-4444-4444-4444-444444444444",
          summary: "Low stock: available 0 <= reorder threshold 0",
          created_at: "2026-05-12T08:00:00Z",
        },
      ],
      total: 1,
      limit: 25,
      offset: 0,
    };
    vi.mocked(
      adminOperationsApi.getAdminOperationsAlerts,
    ).mockResolvedValue(response);

    const filters: AdminOperationsAlertsFilters = {
      limit: 25,
      category: "low_stock",
    };
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useAdminOperationsAlertsQuery(filters),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(
      adminOperationsApi.getAdminOperationsAlerts,
    ).toHaveBeenCalledTimes(1);
    const [filtersArg, signal] = vi.mocked(
      adminOperationsApi.getAdminOperationsAlerts,
    ).mock.calls[0];
    expect(filtersArg).toBe(filters);
    expect(signal).toBeInstanceOf(AbortSignal);

    const expectedKey = adminOperationsKeys.alertList(filters);
    expect(client.getQueryData(expectedKey)).toBe(response);
  });

  it("defaults filters to {} when omitted (stable cache key)", async () => {
    vi.mocked(
      adminOperationsApi.getAdminOperationsAlerts,
    ).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useAdminOperationsAlertsQuery(),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const [filtersArg] = vi.mocked(
      adminOperationsApi.getAdminOperationsAlerts,
    ).mock.calls[0];
    expect(filtersArg).toEqual({});
    expect(client.getQueryData(adminOperationsKeys.alertList())).toEqual(
      emptyResponse(),
    );
  });

  it("returns the alerts payload unchanged (no transformation)", async () => {
    const response = emptyResponse();
    vi.mocked(
      adminOperationsApi.getAdminOperationsAlerts,
    ).mockResolvedValue(response);
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useAdminOperationsAlertsQuery(),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toBe(response);
  });
});

// --------------------------------------------------------------------- //
// Loading / error states
// --------------------------------------------------------------------- //

describe("useAdminOperationsAlertsQuery — pending state", () => {
  it("exposes the pending/loading state before the API resolves", async () => {
    let resolveFn: (value: AdminOperationsAlertsListResponse) => void =
      () => {};
    const pending = new Promise<AdminOperationsAlertsListResponse>(
      (resolve) => {
        resolveFn = resolve;
      },
    );
    vi.mocked(
      adminOperationsApi.getAdminOperationsAlerts,
    ).mockReturnValue(pending);

    const client = makeQueryClient();
    const { result } = renderHook(
      () => useAdminOperationsAlertsQuery(),
      { wrapper: makeWrapper(client) },
    );

    expect(result.current.isPending).toBe(true);
    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();

    resolveFn(emptyResponse());
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

describe("useAdminOperationsAlertsQuery — error state", () => {
  it("propagates errors from getAdminOperationsAlerts unchanged", async () => {
    const boom = new Error("boom-from-admin-operations-hook");
    vi.mocked(
      adminOperationsApi.getAdminOperationsAlerts,
    ).mockRejectedValue(boom);
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useAdminOperationsAlertsQuery(),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(boom);
    expect(result.current.data).toBeUndefined();
  });
});

// --------------------------------------------------------------------- //
// No store / auth context dependency
// --------------------------------------------------------------------- //

describe("useAdminOperationsAlertsQuery — no store / auth context required", () => {
  it("fires immediately without a storeId argument or store context provider", async () => {
    vi.mocked(
      adminOperationsApi.getAdminOperationsAlerts,
    ).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useAdminOperationsAlertsQuery(),
      { wrapper: makeWrapper(client) },
    );

    // No idle state — operations alerts has no path id and is
    // always enabled. `store_id` (when set) lives inside filters.
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(
      adminOperationsApi.getAdminOperationsAlerts,
    ).toHaveBeenCalledTimes(1);
  });

  it("renders without an auth/role provider (backend is the authority)", async () => {
    vi.mocked(
      adminOperationsApi.getAdminOperationsAlerts,
    ).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    // Wrapper has ONLY QueryClientProvider — no AuthProvider, no
    // StoreContext. If the hook required either, this render would
    // throw before the fetch could fire.
    const { result } = renderHook(
      () => useAdminOperationsAlertsQuery(),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
  });
});

// --------------------------------------------------------------------- //
// Query-key wiring + filter-distinct cache slots
// --------------------------------------------------------------------- //

describe("useAdminOperationsAlertsQuery — query key wiring", () => {
  it("uses adminOperationsKeys.alertList(filters), never adminDashboard keys", async () => {
    vi.mocked(
      adminOperationsApi.getAdminOperationsAlerts,
    ).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const filters: AdminOperationsAlertsFilters = {
      store_id: STORE_ID,
      limit: 10,
    };
    const { result } = renderHook(
      () => useAdminOperationsAlertsQuery(filters),
      { wrapper: makeWrapper(client) },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // The operations key has data.
    expect(
      client.getQueryData(adminOperationsKeys.alertList(filters)),
    ).toEqual(emptyResponse());
    // The dashboard key with no data must remain untouched.
    expect(
      client.getQueryData(["admin-dashboard", "summary"]),
    ).toBeUndefined();
  });

  it("changing filters routes to a distinct cache slot (separate fetch)", async () => {
    vi.mocked(
      adminOperationsApi.getAdminOperationsAlerts,
    ).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const filtersA: AdminOperationsAlertsFilters = { limit: 25 };
    const filtersB: AdminOperationsAlertsFilters = { limit: 50 };

    const { result: resA } = renderHook(
      () => useAdminOperationsAlertsQuery(filtersA),
      { wrapper: makeWrapper(client) },
    );
    const { result: resB } = renderHook(
      () => useAdminOperationsAlertsQuery(filtersB),
      { wrapper: makeWrapper(client) },
    );

    await waitFor(() => expect(resA.current.isSuccess).toBe(true));
    await waitFor(() => expect(resB.current.isSuccess).toBe(true));

    // Two distinct cache slots populated; two API calls fired.
    expect(
      adminOperationsApi.getAdminOperationsAlerts,
    ).toHaveBeenCalledTimes(2);
    expect(
      client.getQueryData(adminOperationsKeys.alertList(filtersA)),
    ).toEqual(emptyResponse());
    expect(
      client.getQueryData(adminOperationsKeys.alertList(filtersB)),
    ).toEqual(emptyResponse());
    expect(adminOperationsKeys.alertList(filtersA)).not.toEqual(
      adminOperationsKeys.alertList(filtersB),
    );
  });
});

// --------------------------------------------------------------------- //
// No mutation surface
// --------------------------------------------------------------------- //

describe("useAdminOperationsAlertsQuery — read-only contract", () => {
  it("the returned UseQueryResult has no mutate / mutateAsync function", async () => {
    vi.mocked(
      adminOperationsApi.getAdminOperationsAlerts,
    ).mockResolvedValue(emptyResponse());
    const client = makeQueryClient();

    const { result } = renderHook(
      () => useAdminOperationsAlertsQuery(),
      { wrapper: makeWrapper(client) },
    );
    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // `useQuery` results never expose `mutate` / `mutateAsync` (those
    // belong to `useMutation`). The assertion is a guard against an
    // accidental future addition of an alert mutation surface
    // (acknowledge / dismiss / resolve are non-goals).
    expect(
      (result.current as unknown as { mutate?: unknown }).mutate,
    ).toBeUndefined();
    expect(
      (result.current as unknown as { mutateAsync?: unknown }).mutateAsync,
    ).toBeUndefined();
  });
});
