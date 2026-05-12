// F2.15.4: read-hook tests for the users module.
//
// Pattern mirrors features/products/hooks/__tests__/queries.test.tsx:
// stub the api module so the queryFn never touches the real transport,
// render each hook inside a fresh QueryClient, assert the API call,
// the cache key, and the `enabled` guard.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useUsersQuery } from "../useUsersQuery";
import { useUserQuery } from "../useUserQuery";
import { usersQueryKeys } from "../queryKeys";
import * as usersApi from "../../api";
import type { UserListResponse, UserRead } from "../../types";

vi.mock("../../api", () => ({
  listUsers: vi.fn(),
  getUser: vi.fn(),
}));

const USER_ID = "11111111-1111-1111-1111-111111111111";
const STORE_ID = "33333333-3333-3333-3333-333333333333";

const SAMPLE_USER: UserRead = {
  id: USER_ID,
  full_name: "Sample User",
  email: "sample@example.com",
  role: "staff",
  store_id: STORE_ID,
  is_active: true,
};

const SAMPLE_LIST: UserListResponse = {
  items: [SAMPLE_USER],
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
  vi.mocked(usersApi.listUsers).mockReset();
  vi.mocked(usersApi.getUser).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// useUsersQuery
// --------------------------------------------------------------------- //

describe("useUsersQuery", () => {
  it("calls listUsers with the filters and lands the result on the canonical key", async () => {
    vi.mocked(usersApi.listUsers).mockResolvedValue(SAMPLE_LIST);
    const client = makeQueryClient();
    const filters = { role: "staff" as const, limit: 25 };

    const { result } = renderHook(() => useUsersQuery(filters), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(usersApi.listUsers).toHaveBeenCalledTimes(1);
    const [args] = vi.mocked(usersApi.listUsers).mock.calls[0];
    expect(args).toEqual(filters);

    const expectedKey = usersQueryKeys.list(filters);
    expect(client.getQueryData(expectedKey)).toEqual(SAMPLE_LIST);
  });

  it("defaults to an empty filters object when called with no args", async () => {
    vi.mocked(usersApi.listUsers).mockResolvedValue(SAMPLE_LIST);
    const client = makeQueryClient();

    const { result } = renderHook(() => useUsersQuery(), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const [args] = vi.mocked(usersApi.listUsers).mock.calls[0];
    expect(args).toEqual({});
    expect(client.getQueryData(usersQueryKeys.list())).toEqual(SAMPLE_LIST);
  });
});

// --------------------------------------------------------------------- //
// useUserQuery
// --------------------------------------------------------------------- //

describe("useUserQuery", () => {
  it("is disabled when no userId is provided (does not call getUser)", async () => {
    vi.mocked(usersApi.getUser).mockResolvedValue(SAMPLE_USER);
    const client = makeQueryClient();

    const { result } = renderHook(() => useUserQuery(undefined), {
      wrapper: makeWrapper(client),
    });

    // Give React Query a tick to potentially fire — it should not.
    await waitFor(() => {
      expect(result.current.fetchStatus).toBe("idle");
    });
    expect(usersApi.getUser).not.toHaveBeenCalled();
  });

  it("calls getUser with the userId when provided and lands the result on the canonical key", async () => {
    vi.mocked(usersApi.getUser).mockResolvedValue(SAMPLE_USER);
    const client = makeQueryClient();

    const { result } = renderHook(() => useUserQuery(USER_ID), {
      wrapper: makeWrapper(client),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(usersApi.getUser).toHaveBeenCalledTimes(1);
    const [args] = vi.mocked(usersApi.getUser).mock.calls[0];
    expect(args).toEqual({ userId: USER_ID });

    expect(client.getQueryData(usersQueryKeys.detail(USER_ID))).toEqual(
      SAMPLE_USER,
    );
  });
});
