// F2.18.2A: read-hook tests for the admin stores module.
//
// Pattern mirrors features/users/hooks/__tests__/queries.test.tsx:
// stub the api module so the queryFn never touches the real transport,
// render each hook inside a fresh QueryClient, assert the API call,
// the cache key, and the `enabled` guard.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useAdminStoresQuery } from "../useAdminStoresQuery";
import { useAdminStoreQuery } from "../useAdminStoreQuery";
import { adminStoresKeys } from "../queryKeys";
import * as storesApi from "../../api";
import type {
  StoreListResponse,
  StoreProfile,
} from "../../types";

vi.mock("../../api", () => ({
  listStores: vi.fn(),
  getStore: vi.fn(),
  createStore: vi.fn(),
  updateStore: vi.fn(),
  deactivateStore: vi.fn(),
  reactivateStore: vi.fn(),
}));

const STORE_ID = "33333333-3333-3333-3333-333333333333";

const SAMPLE_STORE: StoreProfile = {
  id: STORE_ID,
  name: "Sample Store",
  code: "smpl",
  is_active: true,
  timezone: "America/New_York",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const SAMPLE_LIST: StoreListResponse = {
  items: [SAMPLE_STORE],
  total: 1,
  limit: 25,
  offset: 0,
};

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

beforeEach(() => {
  vi.mocked(storesApi.listStores).mockReset();
  vi.mocked(storesApi.getStore).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// useAdminStoresQuery
// --------------------------------------------------------------------- //

describe("useAdminStoresQuery", () => {
  it("calls listStores with the filters and lands the result on the canonical key", async () => {
    vi.mocked(storesApi.listStores).mockResolvedValue(SAMPLE_LIST);
    const client = makeQueryClient();
    const filters = { limit: 25, is_active: true };

    const { result } = renderHook(() => useAdminStoresQuery(filters), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(storesApi.listStores).toHaveBeenCalledTimes(1);
    const [args] = vi.mocked(storesApi.listStores).mock.calls[0];
    expect(args).toEqual(filters);

    const expectedKey = adminStoresKeys.list(filters);
    expect(client.getQueryData(expectedKey)).toEqual(SAMPLE_LIST);
  });

  it("defaults to an empty filters object when called with no args", async () => {
    vi.mocked(storesApi.listStores).mockResolvedValue(SAMPLE_LIST);
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminStoresQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const [args] = vi.mocked(storesApi.listStores).mock.calls[0];
    expect(args).toEqual({});
    expect(client.getQueryData(adminStoresKeys.list())).toEqual(SAMPLE_LIST);
  });
});

// --------------------------------------------------------------------- //
// useAdminStoreQuery
// --------------------------------------------------------------------- //

describe("useAdminStoreQuery", () => {
  it("is disabled when no storeId is provided (does not call getStore)", async () => {
    vi.mocked(storesApi.getStore).mockResolvedValue(SAMPLE_STORE);
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminStoreQuery(undefined), {
      wrapper: makeWrapper(client),
    });

    // Give the scheduler a tick; the query must remain idle.
    await new Promise((r) => setTimeout(r, 0));
    expect(storesApi.getStore).not.toHaveBeenCalled();
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("is disabled when storeId is an empty string", async () => {
    vi.mocked(storesApi.getStore).mockResolvedValue(SAMPLE_STORE);
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminStoreQuery(""), {
      wrapper: makeWrapper(client),
    });

    await new Promise((r) => setTimeout(r, 0));
    expect(storesApi.getStore).not.toHaveBeenCalled();
    expect(result.current.fetchStatus).toBe("idle");
  });

  it("calls getStore with the storeId and lands the result on the detail key", async () => {
    vi.mocked(storesApi.getStore).mockResolvedValue(SAMPLE_STORE);
    const client = makeQueryClient();

    const { result } = renderHook(() => useAdminStoreQuery(STORE_ID), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(storesApi.getStore).toHaveBeenCalledTimes(1);
    const [idArg] = vi.mocked(storesApi.getStore).mock.calls[0];
    expect(idArg).toBe(STORE_ID);

    const expectedKey = adminStoresKeys.detail(STORE_ID);
    expect(client.getQueryData(expectedKey)).toEqual(SAMPLE_STORE);
  });
});
