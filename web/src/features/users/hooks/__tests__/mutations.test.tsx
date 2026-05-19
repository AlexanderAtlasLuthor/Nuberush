// F2.9.2 + F2.15.4: mutation-hook tests for the users module.
//
// Pattern mirrors features/products/hooks/__tests__/mutations.test.tsx
// and features/orders/hooks/__tests__/mutations.test.tsx: stub the
// feature's api module, render the hook under a fresh QueryClient,
// drive it via mutate / mutateAsync, and assert the api function was
// called with the variables verbatim. We additionally spy on
// `queryClient.invalidateQueries` to lock in the per-mutation cache
// contract.
//
// Regression invariant: useCreateUserMutation MUST NOT touch the
// QueryClient cache. Today it has no list/detail to invalidate at the
// time of the create call (the list cache, if any, is already
// covered by the list refetch when the user is rendered). Inventing
// an invalidation here would only paper over a divergence between
// "what the create response carries" and "what the list query needs
// to refetch."

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { useCreateUserMutation } from "../useCreateUserMutation";
import { useUpdateUserMutation } from "../useUpdateUserMutation";
import { useDeactivateUserMutation } from "../useDeactivateUserMutation";
import { useReactivateUserMutation } from "../useReactivateUserMutation";
import { useChangeUserRoleMutation } from "../useChangeUserRoleMutation";
import { useAssignUserStoreMutation } from "../useAssignUserStoreMutation";
import { usersQueryKeys } from "../queryKeys";
import * as usersHooks from "../index";
import * as usersApi from "../../api";
import type { CreateUserRequest, UserRead } from "../../types";

vi.mock("../../api", () => ({
  createUser: vi.fn(),
  listUsers: vi.fn(),
  getUser: vi.fn(),
  updateUser: vi.fn(),
  deactivateUser: vi.fn(),
  reactivateUser: vi.fn(),
  changeUserRole: vi.fn(),
  assignUserStore: vi.fn(),
}));

const STORE_ID = "33333333-3333-3333-3333-333333333333";
const NEW_USER_ID = "11111111-1111-1111-1111-111111111111";
const TARGET_ID = "22222222-2222-2222-2222-222222222222";

const SAMPLE_USER: UserRead = {
  id: TARGET_ID,
  full_name: "Sample User",
  email: "sample@example.com",
  role: "staff",
  store_id: STORE_ID,
  is_active: true,
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

function makeBody(overrides: Partial<CreateUserRequest> = {}): CreateUserRequest {
  return {
    full_name: "Jane Operator",
    email: "jane@example.com",
    password: "supersecret123",
    role: "staff",
    store_id: STORE_ID,
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(usersApi.createUser).mockReset();
  vi.mocked(usersApi.updateUser).mockReset();
  vi.mocked(usersApi.deactivateUser).mockReset();
  vi.mocked(usersApi.reactivateUser).mockReset();
  vi.mocked(usersApi.changeUserRole).mockReset();
  vi.mocked(usersApi.assignUserStore).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// useCreateUserMutation — regression (F2.9.2 contract preserved)
// --------------------------------------------------------------------- //

describe("useCreateUserMutation", () => {
  it("calls createUser with the variables passed to mutate()", async () => {
    vi.mocked(usersApi.createUser).mockResolvedValue({
      id: NEW_USER_ID,
    } as never);

    const client = makeQueryClient();
    const { result } = renderHook(() => useCreateUserMutation(), {
      wrapper: makeWrapper(client),
    });

    const body = makeBody();
    result.current.mutate({ body });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(usersApi.createUser).toHaveBeenCalledTimes(1);
    expect(usersApi.createUser).toHaveBeenCalledWith({ body });
  });

  it("resolves mutateAsync with the UserRead response from createUser", async () => {
    const response: UserRead = {
      id: NEW_USER_ID,
      full_name: "Jane Operator",
      email: "jane@example.com",
      role: "staff",
      store_id: STORE_ID,
      is_active: true,
    };
    vi.mocked(usersApi.createUser).mockResolvedValue(response);

    const client = makeQueryClient();
    const { result } = renderHook(() => useCreateUserMutation(), {
      wrapper: makeWrapper(client),
    });

    const returned = await result.current.mutateAsync({ body: makeBody() });
    expect(returned).toEqual(response);
    expect(returned).toBe(response);
  });

  it("propagates errors from createUser unchanged (no transformation)", async () => {
    const boom = new Error("boom-from-api");
    vi.mocked(usersApi.createUser).mockRejectedValue(boom);

    const client = makeQueryClient();
    const { result } = renderHook(() => useCreateUserMutation(), {
      wrapper: makeWrapper(client),
    });

    await expect(
      result.current.mutateAsync({ body: makeBody() }),
    ).rejects.toBe(boom);

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBe(boom);
  });

  it("does NOT invalidate any queries on success (F2.9.2 contract)", async () => {
    vi.mocked(usersApi.createUser).mockResolvedValue({
      id: NEW_USER_ID,
    } as never);

    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");
    const removeSpy = vi.spyOn(client, "removeQueries");
    const setSpy = vi.spyOn(client, "setQueryData");

    const { result } = renderHook(() => useCreateUserMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ body: makeBody() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(invalidateSpy).not.toHaveBeenCalled();
    expect(removeSpy).not.toHaveBeenCalled();
    expect(setSpy).not.toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------- //
// useUpdateUserMutation
// --------------------------------------------------------------------- //

describe("useUpdateUserMutation", () => {
  it("calls updateUser with variables and invalidates lists() + detail(userId)", async () => {
    vi.mocked(usersApi.updateUser).mockResolvedValue(SAMPLE_USER);
    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useUpdateUserMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      userId: TARGET_ID,
      body: { full_name: "Renamed" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(usersApi.updateUser).toHaveBeenCalledWith({
      userId: TARGET_ID,
      body: { full_name: "Renamed" },
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: usersQueryKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: usersQueryKeys.detail(TARGET_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// useDeactivateUserMutation
// --------------------------------------------------------------------- //

describe("useDeactivateUserMutation", () => {
  it("calls deactivateUser and invalidates lists() + detail(userId)", async () => {
    vi.mocked(usersApi.deactivateUser).mockResolvedValue({
      ...SAMPLE_USER,
      is_active: false,
    });
    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useDeactivateUserMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ userId: TARGET_ID });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(usersApi.deactivateUser).toHaveBeenCalledWith({
      userId: TARGET_ID,
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: usersQueryKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: usersQueryKeys.detail(TARGET_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// useReactivateUserMutation
// --------------------------------------------------------------------- //

describe("useReactivateUserMutation", () => {
  it("calls reactivateUser and invalidates lists() + detail(userId)", async () => {
    vi.mocked(usersApi.reactivateUser).mockResolvedValue(SAMPLE_USER);
    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useReactivateUserMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({ userId: TARGET_ID });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(usersApi.reactivateUser).toHaveBeenCalledWith({
      userId: TARGET_ID,
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: usersQueryKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: usersQueryKeys.detail(TARGET_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// useChangeUserRoleMutation
// --------------------------------------------------------------------- //

describe("useChangeUserRoleMutation", () => {
  it("calls changeUserRole and invalidates lists() + detail(userId)", async () => {
    vi.mocked(usersApi.changeUserRole).mockResolvedValue({
      ...SAMPLE_USER,
      role: "manager",
    });
    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useChangeUserRoleMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      userId: TARGET_ID,
      body: { role: "manager" },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(usersApi.changeUserRole).toHaveBeenCalledWith({
      userId: TARGET_ID,
      body: { role: "manager" },
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: usersQueryKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: usersQueryKeys.detail(TARGET_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// useAssignUserStoreMutation
// --------------------------------------------------------------------- //

describe("useAssignUserStoreMutation", () => {
  it("calls assignUserStore and invalidates lists() + detail(userId)", async () => {
    vi.mocked(usersApi.assignUserStore).mockResolvedValue(SAMPLE_USER);
    const client = makeQueryClient();
    const invalidateSpy = vi.spyOn(client, "invalidateQueries");

    const { result } = renderHook(() => useAssignUserStoreMutation(), {
      wrapper: makeWrapper(client),
    });

    result.current.mutate({
      userId: TARGET_ID,
      body: { store_id: STORE_ID },
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(usersApi.assignUserStore).toHaveBeenCalledWith({
      userId: TARGET_ID,
      body: { store_id: STORE_ID },
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: usersQueryKeys.lists(),
    });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: usersQueryKeys.detail(TARGET_ID),
    });
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });
});

// --------------------------------------------------------------------- //
// Cross-feature invalidation guard
// --------------------------------------------------------------------- //

describe("cross-feature invalidation guard", () => {
  // Every users mutation must touch ONLY the users query namespace.
  // A future contributor copy-pasting from products/orders should not
  // be tempted to invalidate "everything".

  it.each([
    ["useUpdateUserMutation", useUpdateUserMutation, "updateUser"],
    ["useDeactivateUserMutation", useDeactivateUserMutation, "deactivateUser"],
    ["useReactivateUserMutation", useReactivateUserMutation, "reactivateUser"],
    [
      "useChangeUserRoleMutation",
      useChangeUserRoleMutation,
      "changeUserRole",
    ],
    [
      "useAssignUserStoreMutation",
      useAssignUserStoreMutation,
      "assignUserStore",
    ],
  ] as const)(
    "%s only invalidates keys under usersQueryKeys.all",
    async (_label, useHook, apiFnName) => {
      vi.mocked(
        usersApi[apiFnName as keyof typeof usersApi] as never,
      ).mockResolvedValue?.(SAMPLE_USER as never);
      const client = makeQueryClient();
      const invalidateSpy = vi.spyOn(client, "invalidateQueries");

      const { result } = renderHook(() => useHook(), {
        wrapper: makeWrapper(client),
      });

      // Each mutation accepts at minimum a userId; pass a generic body
      // shape that satisfies every signature (extra keys are ignored
      // by the mock).
      // Cast to `never` to bypass per-hook variable typing in this
      // generic loop; the per-hook tests above lock in the precise
      // variable shapes already.
      (result.current.mutate as (vars: unknown) => void)({
        userId: TARGET_ID,
        body: {
          role: "staff",
          store_id: STORE_ID,
          new_password: "fresh-secret-1234",
          full_name: "x",
        },
      });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));

      // Every observed invalidation must start with ["users", ...].
      for (const call of invalidateSpy.mock.calls) {
        const arg = call[0] as { queryKey?: readonly unknown[] } | undefined;
        const key = arg?.queryKey ?? [];
        expect(key[0]).toBe("users");
      }
    },
  );
});

// --------------------------------------------------------------------- //
// usersQueryKeys — regression on the factory shape
// --------------------------------------------------------------------- //

describe("usersQueryKeys", () => {
  it("exposes all/lists/list/details/detail (F2.15.4 shape)", () => {
    expect(usersQueryKeys.all).toEqual(["users"]);
    expect(usersQueryKeys.lists()).toEqual(["users", "list"]);
    expect(usersQueryKeys.list({ q: "x" })).toEqual([
      "users",
      "list",
      { q: "x" },
    ]);
    expect(usersQueryKeys.details()).toEqual(["users", "detail"]);
    expect(usersQueryKeys.detail("u-1")).toEqual([
      "users",
      "detail",
      "u-1",
    ]);
  });
});

// --------------------------------------------------------------------- //
// Public surface — guard against accidental over-build
// --------------------------------------------------------------------- //

describe("users hooks public surface", () => {
  it("exports the users hooks surface", () => {
    expect(Object.keys(usersHooks).sort()).toEqual(
      [
        "useAssignUserStoreMutation",
        "useChangeUserRoleMutation",
        "useCreateUserMutation",
        "useDeactivateUserMutation",
        "useReactivateUserMutation",
        "useUpdateUserMutation",
        "useUserQuery",
        "useUsersQuery",
        "usersQueryKeys",
      ].sort(),
    );
  });

  it.each([
    "useDeleteUserMutation",
    "useRolesQuery",
    "usePermissionsQuery",
    "useStoresQuery",
    "useInviteUserMutation",
    "useSendPasswordResetMutation",
  ] as const)(
    "does not export `%s` (no matching backend endpoint)",
    (name) => {
      expect(usersHooks).not.toHaveProperty(name);
    },
  );
});
