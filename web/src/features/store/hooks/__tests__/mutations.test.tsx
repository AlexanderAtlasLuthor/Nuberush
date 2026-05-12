// F2.14.4: mutation-hook tests for the store-profile module.
//
// We spy on `queryClient.invalidateQueries` rather than seeding the
// cache and re-checking `isInvalidated`, because the spy expresses the
// hook's actual contract — *which keys did onSuccess invalidate* — in
// the assertions, not implicitly through cache state. Mirrors the
// pattern in features/products/hooks/__tests__/mutations.test.tsx.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useUpdateStoreMutation } from "../useUpdateStoreMutation";
import { storeKeys } from "../queryKeys";
import * as storeApi from "../../api";
import type { StoreProfile } from "../../types";

vi.mock("../../api", () => ({
  getStore: vi.fn(),
  updateStore: vi.fn(),
}));

const STORE_ID = "22222222-2222-2222-2222-222222222222";
const OTHER_STORE_ID = "33333333-3333-3333-3333-333333333333";

const STORE_RESPONSE: StoreProfile = {
  id: STORE_ID,
  name: "Updated Acme",
  code: "ACME-HQ",
  is_active: true,
  timezone: "America/Chicago",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-03T00:00:00Z",
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
  vi.mocked(storeApi.updateStore).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// useUpdateStoreMutation — call shape
// --------------------------------------------------------------------- //

describe("useUpdateStoreMutation call shape", () => {
  it("calls updateStore with the bound storeId and the payload verbatim", async () => {
    vi.mocked(storeApi.updateStore).mockResolvedValue(STORE_RESPONSE);

    const client = makeQueryClient();
    const { result } = renderHook(() => useUpdateStoreMutation(STORE_ID), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      name: "Updated Acme",
      timezone: "America/Chicago",
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(storeApi.updateStore).toHaveBeenCalledTimes(1);
    expect(storeApi.updateStore).toHaveBeenCalledWith(STORE_ID, {
      name: "Updated Acme",
      timezone: "America/Chicago",
    });
  });

  it("supports a partial payload (name only)", async () => {
    vi.mocked(storeApi.updateStore).mockResolvedValue(STORE_RESPONSE);

    const client = makeQueryClient();
    const { result } = renderHook(() => useUpdateStoreMutation(STORE_ID), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ name: "Solo Name" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(storeApi.updateStore).toHaveBeenCalledWith(STORE_ID, {
      name: "Solo Name",
    });
  });
});

// --------------------------------------------------------------------- //
// useUpdateStoreMutation — invalidation contract
// --------------------------------------------------------------------- //

describe("useUpdateStoreMutation invalidation contract", () => {
  it("invalidates exactly storeKeys.detail(storeId) on success", async () => {
    vi.mocked(storeApi.updateStore).mockResolvedValue(STORE_RESPONSE);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateStoreMutation(STORE_ID), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ name: "Anything" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).toHaveBeenCalledTimes(1);
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: storeKeys.detail(STORE_ID),
    });
  });

  it("does not invalidate the bound storeId's detail for a different storeId", async () => {
    vi.mocked(storeApi.updateStore).mockResolvedValue(STORE_RESPONSE);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateStoreMutation(STORE_ID), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ name: "Anything" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // The hook is bound to STORE_ID; nothing should target OTHER_STORE_ID.
    expect(invalidateSpy).not.toHaveBeenCalledWith({
      queryKey: storeKeys.detail(OTHER_STORE_ID),
    });
  });

  it("does not invalidate keys outside the store feature module", async () => {
    vi.mocked(storeApi.updateStore).mockResolvedValue(STORE_RESPONSE);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateStoreMutation(STORE_ID), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ name: "Anything" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    // Defensive: every invalidate call must target a key whose root
    // segment is "store". A regression that pulled in dashboard /
    // products / inventory / orders keys would be caught by this
    // assertion regardless of which exact key it picked.
    for (const call of invalidateSpy.mock.calls) {
      const arg = call[0] as { queryKey?: readonly unknown[] };
      expect(arg.queryKey?.[0]).toBe("store");
    }
  });
});
