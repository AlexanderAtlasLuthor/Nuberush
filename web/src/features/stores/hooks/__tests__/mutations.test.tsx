// F2.18.2A: mutation-hook tests for the admin stores module.
//
// Pattern mirrors features/users/hooks/__tests__/mutations.test.tsx:
// stub the feature's api module, render the hook under a fresh
// QueryClient, drive it via mutate / mutateAsync, and assert the api
// function was called with the variables verbatim. We additionally
// spy on `queryClient.invalidateQueries` to lock in the per-mutation
// cache contract.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useCreateStoreMutation } from "../useCreateStoreMutation";
import { useUpdateStoreMutation } from "../useUpdateStoreMutation";
import { useDeactivateStoreMutation } from "../useDeactivateStoreMutation";
import { useReactivateStoreMutation } from "../useReactivateStoreMutation";
import { adminStoresKeys } from "../queryKeys";
import * as storesApi from "../../api";
import type { StoreCreateRequest, StoreProfile } from "../../types";

vi.mock("../../api", () => ({
  listStores: vi.fn(),
  getStore: vi.fn(),
  createStore: vi.fn(),
  updateStore: vi.fn(),
  deactivateStore: vi.fn(),
  reactivateStore: vi.fn(),
}));

const STORE_ID = "33333333-3333-3333-3333-333333333333";
const NEW_STORE_ID = "11111111-1111-1111-1111-111111111111";

const SAMPLE_STORE: StoreProfile = {
  id: STORE_ID,
  name: "Sample Store",
  code: "smpl",
  is_active: true,
  timezone: "America/New_York",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
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

function makeCreateBody(
  overrides: Partial<StoreCreateRequest> = {},
): StoreCreateRequest {
  return {
    name: "Brooklyn Hub",
    code: "bk-001",
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(storesApi.createStore).mockReset();
  vi.mocked(storesApi.updateStore).mockReset();
  vi.mocked(storesApi.deactivateStore).mockReset();
  vi.mocked(storesApi.reactivateStore).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// useCreateStoreMutation
// --------------------------------------------------------------------- //

describe("useCreateStoreMutation", () => {
  it("calls createStore with the variables passed to mutate()", async () => {
    vi.mocked(storesApi.createStore).mockResolvedValue({
      ...SAMPLE_STORE,
      id: NEW_STORE_ID,
    });
    const client = makeQueryClient();

    const { result } = renderHook(() => useCreateStoreMutation(), {
      wrapper: makeWrapper(client),
    });

    const body = makeCreateBody();
    result.current.mutate({ body });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(storesApi.createStore).toHaveBeenCalledTimes(1);
    expect(storesApi.createStore).toHaveBeenCalledWith({ body });
  });

  it("invalidates only the lists() prefix on success (not detail keys)", async () => {
    vi.mocked(storesApi.createStore).mockResolvedValue({
      ...SAMPLE_STORE,
      id: NEW_STORE_ID,
    });
    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useCreateStoreMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ body: makeCreateBody() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: adminStoresKeys.lists(),
    });
    // No detail invalidation for a brand-new row.
    expect(invalidateSpy).toHaveBeenCalledTimes(1);
  });

  it("propagates errors from createStore unchanged", async () => {
    const boom = new Error("boom-from-api");
    vi.mocked(storesApi.createStore).mockRejectedValue(boom);

    const client = makeQueryClient();
    const { result } = renderHook(() => useCreateStoreMutation(), {
      wrapper: makeWrapper(client),
    });

    await expect(
      result.current.mutateAsync({ body: makeCreateBody() }),
    ).rejects.toBe(boom);

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(boom);
  });
});

// --------------------------------------------------------------------- //
// useUpdateStoreMutation (admin variant — takes storeId per-mutate)
// --------------------------------------------------------------------- //

describe("useUpdateStoreMutation (admin)", () => {
  it("calls updateStore with (storeId, body) and invalidates lists() + detail(storeId)", async () => {
    vi.mocked(storesApi.updateStore).mockResolvedValue({
      ...SAMPLE_STORE,
      name: "Renamed",
    });
    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateStoreMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      storeId: STORE_ID,
      body: { name: "Renamed" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(storesApi.updateStore).toHaveBeenCalledWith(STORE_ID, {
      name: "Renamed",
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: adminStoresKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: adminStoresKeys.detail(STORE_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// useDeactivateStoreMutation
// --------------------------------------------------------------------- //

describe("useDeactivateStoreMutation", () => {
  it("calls deactivateStore and invalidates lists() + detail(storeId)", async () => {
    vi.mocked(storesApi.deactivateStore).mockResolvedValue({
      ...SAMPLE_STORE,
      is_active: false,
    });
    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useDeactivateStoreMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ storeId: STORE_ID });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(storesApi.deactivateStore).toHaveBeenCalledWith({
      storeId: STORE_ID,
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: adminStoresKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: adminStoresKeys.detail(STORE_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// useReactivateStoreMutation
// --------------------------------------------------------------------- //

describe("useReactivateStoreMutation", () => {
  it("calls reactivateStore and invalidates lists() + detail(storeId)", async () => {
    vi.mocked(storesApi.reactivateStore).mockResolvedValue(SAMPLE_STORE);
    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useReactivateStoreMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ storeId: STORE_ID });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(storesApi.reactivateStore).toHaveBeenCalledWith({
      storeId: STORE_ID,
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: adminStoresKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: adminStoresKeys.detail(STORE_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});
