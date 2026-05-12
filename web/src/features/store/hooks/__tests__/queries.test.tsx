// F2.14.4: read-hook tests for the store-profile module.
//
// Strategy mirrors features/products/hooks/__tests__/queries.test.tsx:
// stub the api module so the queryFn never touches the real transport.
// Render each hook inside a fresh QueryClient so cache state is
// isolated between cases.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useStoreQuery } from "../useStoreQuery";
import { storeKeys } from "../queryKeys";
import * as storeApi from "../../api";
import type { StoreProfile } from "../../types";

vi.mock("../../api", () => ({
  getStore: vi.fn(),
  updateStore: vi.fn(),
}));

const STORE_ID = "22222222-2222-2222-2222-222222222222";

const STORE_RESPONSE: StoreProfile = {
  id: STORE_ID,
  name: "Acme HQ",
  code: "ACME-HQ",
  is_active: true,
  timezone: "America/New_York",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-02T00:00:00Z",
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
  vi.mocked(storeApi.getStore).mockReset();
  vi.mocked(storeApi.updateStore).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// useStoreQuery — disabled paths
// --------------------------------------------------------------------- //

describe("useStoreQuery disabled paths", () => {
  it("does not call getStore when storeId is null", () => {
    const client = makeQueryClient();

    const { result } = renderHook(() => useStoreQuery(null), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(storeApi.getStore).not.toHaveBeenCalled();
  });

  it("does not call getStore when storeId is undefined", () => {
    const client = makeQueryClient();

    const { result } = renderHook(() => useStoreQuery(undefined), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(storeApi.getStore).not.toHaveBeenCalled();
  });

  it("does not call getStore when storeId is the empty string", () => {
    const client = makeQueryClient();

    const { result } = renderHook(() => useStoreQuery(""), {
      wrapper: makeWrapper(client),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(storeApi.getStore).not.toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------- //
// useStoreQuery — happy path
// --------------------------------------------------------------------- //

describe("useStoreQuery happy path", () => {
  it("calls getStore with the storeId and lands the result on the canonical key", async () => {
    vi.mocked(storeApi.getStore).mockResolvedValue(STORE_RESPONSE);
    const client = makeQueryClient();

    const { result } = renderHook(() => useStoreQuery(STORE_ID), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(storeApi.getStore).toHaveBeenCalledTimes(1);
    const [calledStoreId] = vi.mocked(storeApi.getStore).mock.calls[0];
    expect(calledStoreId).toBe(STORE_ID);

    const expectedKey = storeKeys.detail(STORE_ID);
    expect(expectedKey).toEqual(["store", "detail", STORE_ID]);
    expect(client.getQueryData(expectedKey)).toEqual(STORE_RESPONSE);
  });

  it("exposes the StoreProfile data once the query resolves", async () => {
    vi.mocked(storeApi.getStore).mockResolvedValue(STORE_RESPONSE);
    const client = makeQueryClient();

    const { result } = renderHook(() => useStoreQuery(STORE_ID), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toEqual(STORE_RESPONSE);
  });
});
