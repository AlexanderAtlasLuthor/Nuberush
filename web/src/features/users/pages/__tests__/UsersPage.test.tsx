// F2.15.7: tests for the real UsersPage.
//
// Strategy mirrors features/products/pages/__tests__/ProductsPage.test.tsx:
// stub `../../hooks` so the page renders the mocked `useUsersQuery`
// result without touching TanStack Query, the api layer or the
// network. Stub `@/auth` so `useStoreContext()` returns a controllable
// `currentStoreId`. Render through a `MemoryRouter` so the page can
// read its pathname via `useLocation()` to flip between store and
// admin scopes.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import type { ReactNode } from "react";
import type {
  UseMutationResult,
  UseQueryResult,
} from "@tanstack/react-query";

import UsersPage from "../UsersPage";
import * as usersHooks from "../../hooks";
import type {
  AdminSetUserPasswordParams,
  AssignUserStoreParams,
  ChangeUserRoleParams,
  CreateUserParams,
  DeactivateUserParams,
  ReactivateUserParams,
  UpdateUserParams,
} from "../../api";
import type { UserListResponse, UserRead } from "../../types";

// --------------------------------------------------------------------- //
// Hook + auth mocks
// --------------------------------------------------------------------- //

const mockStoreContext = vi.hoisted(
  (): { current: { currentStoreId: string | null } } => ({
    current: { currentStoreId: "22222222-2222-2222-2222-222222222222" },
  }),
);

vi.mock("@/auth", () => ({
  useStoreContext: () => ({
    currentStoreId: mockStoreContext.current.currentStoreId,
    hasStoreContext: mockStoreContext.current.currentStoreId !== null,
    isStoreRequired: false,
    storeError: null,
  }),
}));

vi.mock("../../hooks", () => ({
  useUsersQuery: vi.fn(),
  useCreateUserMutation: vi.fn(),
  useUpdateUserMutation: vi.fn(),
  useDeactivateUserMutation: vi.fn(),
  useReactivateUserMutation: vi.fn(),
  useChangeUserRoleMutation: vi.fn(),
  useAssignUserStoreMutation: vi.fn(),
  useAdminSetPasswordMutation: vi.fn(),
}));

// Mock dropdown-menu inline so the row's DropdownMenuItems are
// queryable without opening Radix portals (same pattern as
// inventory/UserActionsMenu tests).
vi.mock("@/components/ui/dropdown-menu", () => {
  const Pass = ({ children }: { children?: ReactNode }) => <>{children}</>;
  const Wrap = ({
    children,
    ...rest
  }: { children?: ReactNode } & Record<string, unknown>) => (
    <div {...rest}>{children}</div>
  );
  return {
    DropdownMenu: Pass,
    DropdownMenuTrigger: Pass,
    DropdownMenuContent: Wrap,
    DropdownMenuLabel: Wrap,
    DropdownMenuSeparator: () => <hr />,
    DropdownMenuItem: ({
      children,
      onSelect,
      ...rest
    }: {
      children?: ReactNode;
      onSelect?: () => void;
    } & Record<string, unknown>) => (
      <button type="button" {...rest} onClick={() => onSelect?.()}>
        {children}
      </button>
    ),
  };
});

// --------------------------------------------------------------------- //
// Helpers
// --------------------------------------------------------------------- //

const STORE_ID = "22222222-2222-2222-2222-222222222222";
const NEW_USER_ID = "11111111-1111-1111-1111-111111111111";

function makeUser(overrides: Partial<UserRead> = {}): UserRead {
  return {
    id: NEW_USER_ID,
    full_name: "Alice Operator",
    email: "alice@example.com",
    role: "manager",
    store_id: STORE_ID,
    is_active: true,
    ...overrides,
  };
}

function asQueryResult<TData>(
  partial: Partial<UseQueryResult<TData>>,
): UseQueryResult<TData> {
  return partial as UseQueryResult<TData>;
}

function makeMutation<P>(
  o: { isSuccess?: boolean; isPending?: boolean; data?: UserRead | null } = {},
) {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    reset: vi.fn(),
    isPending: o.isPending ?? false,
    isSuccess: o.isSuccess ?? false,
    isError: false,
    error: null,
    data: o.data ?? undefined,
  } as unknown as UseMutationResult<UserRead, Error, P> & {
    mutate: ReturnType<typeof vi.fn>;
    reset: ReturnType<typeof vi.fn>;
  };
}

function setStoreContext(currentStoreId: string | null) {
  mockStoreContext.current = { currentStoreId };
}

function withRouter(node: ReactNode, path = "/app/store/users") {
  return <MemoryRouter initialEntries={[path]}>{node}</MemoryRouter>;
}

function setupDefaultMutations() {
  vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(
    makeMutation<CreateUserParams>(),
  );
  vi.mocked(usersHooks.useUpdateUserMutation).mockReturnValue(
    makeMutation<UpdateUserParams>(),
  );
  vi.mocked(usersHooks.useDeactivateUserMutation).mockReturnValue(
    makeMutation<DeactivateUserParams>(),
  );
  vi.mocked(usersHooks.useReactivateUserMutation).mockReturnValue(
    makeMutation<ReactivateUserParams>(),
  );
  vi.mocked(usersHooks.useChangeUserRoleMutation).mockReturnValue(
    makeMutation<ChangeUserRoleParams>(),
  );
  vi.mocked(usersHooks.useAssignUserStoreMutation).mockReturnValue(
    makeMutation<AssignUserStoreParams>(),
  );
  vi.mocked(usersHooks.useAdminSetPasswordMutation).mockReturnValue(
    makeMutation<AdminSetUserPasswordParams>(),
  );
}

beforeEach(() => {
  vi.mocked(usersHooks.useUsersQuery).mockReset();
  setStoreContext(STORE_ID);
  setupDefaultMutations();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Page chrome and scope copy
// --------------------------------------------------------------------- //

describe("UsersPage — store scope", () => {
  beforeEach(() => {
    vi.mocked(usersHooks.useUsersQuery).mockReturnValue(
      asQueryResult<UserListResponse>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: { items: [], total: 0, limit: 25, offset: 0 },
      }),
    );
  });

  it("renders the page title 'Users'", () => {
    render(withRouter(<UsersPage />, "/app/store/users"));
    expect(
      screen.getByRole("heading", { level: 1, name: "Users" }),
    ).toBeInTheDocument();
  });

  it("renders the store-scope description", () => {
    render(withRouter(<UsersPage />, "/app/store/users"));
    expect(
      screen.getByText("Manage team members who can operate this store."),
    ).toBeInTheDocument();
  });

  it("calls useUsersQuery with the current store_id forced", () => {
    render(withRouter(<UsersPage />, "/app/store/users"));
    expect(usersHooks.useUsersQuery).toHaveBeenCalled();
    const lastCall = vi.mocked(usersHooks.useUsersQuery).mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({ store_id: STORE_ID });
  });

  it("hides the store filter input on the store route", () => {
    render(withRouter(<UsersPage />, "/app/store/users"));
    expect(
      screen.queryByTestId("users-filter-store-id"),
    ).not.toBeInTheDocument();
  });

  it("hides admin actions on the store route", () => {
    vi.mocked(usersHooks.useUsersQuery).mockReturnValue(
      asQueryResult<UserListResponse>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: { items: [makeUser()], total: 1, limit: 25, offset: 0 },
      }),
    );
    render(withRouter(<UsersPage />, "/app/store/users"));
    expect(
      screen.queryByTestId("user-action-assign-store"),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByTestId("user-action-set-password"),
    ).not.toBeInTheDocument();
  });
});

describe("UsersPage — admin scope", () => {
  beforeEach(() => {
    vi.mocked(usersHooks.useUsersQuery).mockReturnValue(
      asQueryResult<UserListResponse>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: { items: [makeUser()], total: 1, limit: 25, offset: 0 },
      }),
    );
  });

  it("renders the page title 'Users'", () => {
    render(withRouter(<UsersPage />, "/app/admin/users"));
    expect(
      screen.getByRole("heading", { level: 1, name: "Users" }),
    ).toBeInTheDocument();
  });

  it("renders the admin/global description", () => {
    render(withRouter(<UsersPage />, "/app/admin/users"));
    expect(
      screen.getByText("Manage users across the NubeRush platform."),
    ).toBeInTheDocument();
  });

  it("calls useUsersQuery without forcing a store_id", () => {
    setStoreContext(null);
    render(withRouter(<UsersPage />, "/app/admin/users"));
    const lastCall = vi.mocked(usersHooks.useUsersQuery).mock.calls.at(-1);
    expect(lastCall?.[0]?.store_id).toBeUndefined();
  });

  it("shows the store filter input on the admin route", () => {
    render(withRouter(<UsersPage />, "/app/admin/users"));
    expect(
      screen.getByTestId("users-filter-store-id"),
    ).toBeInTheDocument();
  });

  it("shows admin actions on the admin route", () => {
    render(withRouter(<UsersPage />, "/app/admin/users"));
    expect(
      screen.getByTestId("user-action-assign-store"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("user-action-set-password"),
    ).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Loading / error / empty / data states
// --------------------------------------------------------------------- //

describe("UsersPage — query states", () => {
  it("renders the loading state", () => {
    vi.mocked(usersHooks.useUsersQuery).mockReturnValue(
      asQueryResult<UserListResponse>({
        isLoading: true,
        isError: false,
        isSuccess: false,
        data: undefined,
      }),
    );
    render(withRouter(<UsersPage />, "/app/store/users"));
    expect(screen.getByText(/loading users/i)).toBeInTheDocument();
  });

  it("renders the error state and retry button", () => {
    const refetch = vi.fn();
    vi.mocked(usersHooks.useUsersQuery).mockReturnValue(
      asQueryResult<UserListResponse>({
        isLoading: false,
        isError: true,
        isSuccess: false,
        data: undefined,
        error: new Error("network down"),
        refetch,
      }),
    );
    render(withRouter(<UsersPage />, "/app/store/users"));
    expect(screen.getByText("Could not load users")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(refetch).toHaveBeenCalled();
  });

  it("renders the empty state when items is empty", () => {
    vi.mocked(usersHooks.useUsersQuery).mockReturnValue(
      asQueryResult<UserListResponse>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: { items: [], total: 0, limit: 25, offset: 0 },
      }),
    );
    render(withRouter(<UsersPage />, "/app/store/users"));
    expect(screen.getByText("No users found")).toBeInTheDocument();
  });

  it("renders rows when items is non-empty", () => {
    const user = makeUser();
    vi.mocked(usersHooks.useUsersQuery).mockReturnValue(
      asQueryResult<UserListResponse>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: { items: [user], total: 1, limit: 25, offset: 0 },
      }),
    );
    render(withRouter(<UsersPage />, "/app/store/users"));
    const rows = screen.getAllByTestId("users-row");
    expect(rows).toHaveLength(1);
    expect(within(rows[0]).getByText(user.full_name)).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Filters
// --------------------------------------------------------------------- //

describe("UsersPage — filters", () => {
  beforeEach(() => {
    vi.mocked(usersHooks.useUsersQuery).mockReturnValue(
      asQueryResult<UserListResponse>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: { items: [], total: 0, limit: 25, offset: 0 },
      }),
    );
  });

  it("typing in search updates the query filter", () => {
    render(withRouter(<UsersPage />, "/app/store/users"));
    fireEvent.change(screen.getByTestId("users-filter-q"), {
      target: { value: "alice" },
    });
    const lastCall = vi.mocked(usersHooks.useUsersQuery).mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({ q: "alice" });
  });

  it("admin route preserves the typed store_id when not forced", () => {
    setStoreContext(null);
    render(withRouter(<UsersPage />, "/app/admin/users"));
    fireEvent.change(screen.getByTestId("users-filter-store-id"), {
      target: { value: STORE_ID },
    });
    const lastCall = vi.mocked(usersHooks.useUsersQuery).mock.calls.at(-1);
    expect(lastCall?.[0]).toMatchObject({ store_id: STORE_ID });
  });

  it("store route ignores any typed store_id (forced filter wins)", () => {
    // Even if a curious operator could type into a hidden field
    // (they can't — the input isn't rendered), the forced merge in
    // the page would replace it with the caller's currentStoreId.
    render(withRouter(<UsersPage />, "/app/store/users"));
    const lastCall = vi.mocked(usersHooks.useUsersQuery).mock.calls.at(-1);
    expect(lastCall?.[0]?.store_id).toBe(STORE_ID);
  });
});

// --------------------------------------------------------------------- //
// Create user
// --------------------------------------------------------------------- //

describe("UsersPage — create user", () => {
  beforeEach(() => {
    vi.mocked(usersHooks.useUsersQuery).mockReturnValue(
      asQueryResult<UserListResponse>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: { items: [], total: 0, limit: 25, offset: 0 },
      }),
    );
  });

  it("renders the Create user button", () => {
    render(withRouter(<UsersPage />, "/app/store/users"));
    expect(screen.getByTestId("users-create-button")).toBeInTheDocument();
  });

  it("opens CreateUserModal when the Create user button is clicked", () => {
    render(withRouter(<UsersPage />, "/app/store/users"));
    expect(screen.queryByTestId("create-user-modal")).not.toBeInTheDocument();
    fireEvent.click(screen.getByTestId("users-create-button"));
    expect(screen.getByTestId("create-user-modal")).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Action menu wiring
// --------------------------------------------------------------------- //

describe("UsersPage — action menu wiring", () => {
  beforeEach(() => {
    vi.mocked(usersHooks.useUsersQuery).mockReturnValue(
      asQueryResult<UserListResponse>({
        isLoading: false,
        isError: false,
        isSuccess: true,
        data: { items: [makeUser()], total: 1, limit: 25, offset: 0 },
      }),
    );
  });

  it("clicking Edit opens EditUserModal", () => {
    render(withRouter(<UsersPage />, "/app/store/users"));
    fireEvent.click(screen.getByTestId("user-action-edit"));
    expect(screen.getByTestId("edit-user-modal")).toBeInTheDocument();
  });

  it("clicking Deactivate opens DeactivateUserDialog", () => {
    render(withRouter(<UsersPage />, "/app/store/users"));
    fireEvent.click(screen.getByTestId("user-action-deactivate"));
    expect(
      screen.getByTestId("deactivate-user-dialog"),
    ).toBeInTheDocument();
  });

  it("clicking Change role opens ChangeUserRoleModal", () => {
    render(withRouter(<UsersPage />, "/app/store/users"));
    fireEvent.click(screen.getByTestId("user-action-change-role"));
    expect(
      screen.getByTestId("change-user-role-modal"),
    ).toBeInTheDocument();
  });

  it("admin route — clicking Assign store opens AssignUserStoreModal", () => {
    render(withRouter(<UsersPage />, "/app/admin/users"));
    fireEvent.click(screen.getByTestId("user-action-assign-store"));
    expect(
      screen.getByTestId("assign-user-store-modal"),
    ).toBeInTheDocument();
  });

  it("admin route — clicking Set password opens AdminSetPasswordModal", () => {
    render(withRouter(<UsersPage />, "/app/admin/users"));
    fireEvent.click(screen.getByTestId("user-action-set-password"));
    expect(
      screen.getByTestId("admin-set-password-modal"),
    ).toBeInTheDocument();
  });
});

// --------------------------------------------------------------------- //
// Architecture guard — no fake users, no backend-required copy, no
// frontend permission authority.
// --------------------------------------------------------------------- //

describe("UsersPage — architecture", () => {
  it("does NOT import or reference frontend permission authority", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "UsersPage.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\bcurrentUser\b/);
    expect(code).not.toMatch(/\bcanCreate\b/);
    expect(code).not.toMatch(/\bcanManage\b/);
    expect(code).not.toMatch(/\bhasPermission\b/);
    expect(code).not.toMatch(/\ballowedRoles\b/);
    expect(code).not.toMatch(/\bUSER_CREATION_MATRIX\b/);
    expect(code).not.toMatch(/\.role\s*===\s*["']/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
  });

  it("source no longer contains backend-required placeholder copy", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "UsersPage.tsx");
    const source = fs.readFileSync(here, "utf-8");
    expect(source).not.toMatch(/Create-only store users/);
    expect(source).not.toMatch(/POST \/auth\/users.+only/);
    expect(source).not.toMatch(/No user list is available/);
    expect(source).not.toMatch(/Recently created/);
  });

  it("router maps both /app/store/users and /app/admin/users to UsersPage", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(
      __dirname,
      "..",
      "..",
      "..",
      "..",
      "app",
      "router.tsx",
    );
    const source = fs.readFileSync(here, "utf-8");
    expect(source).toMatch(
      /import\s+UsersPage\s+from\s+["']@\/features\/users\/pages\/UsersPage["']/,
    );
    // Both routes point at <UsersPage /> after F2.15.7.
    const usersPageMatches = source.match(/<UsersPage\s*\/>/g) ?? [];
    expect(usersPageMatches.length).toBeGreaterThanOrEqual(2);
    // AdminUsersPlaceholder is no longer wired in the router.
    expect(source).not.toMatch(/<AdminUsersPlaceholder\s*\/>/);
  });
});
