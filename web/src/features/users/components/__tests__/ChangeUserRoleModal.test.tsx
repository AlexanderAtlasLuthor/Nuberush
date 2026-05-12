// F2.15.6: ChangeUserRoleModal tests.
//
// Asserts payload composition (`{role}`), the auto-close on success,
// inline error rendering, and the absence of frontend authorization
// (every role option is shown — backend rejects illegal transitions).

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { ChangeUserRoleModal } from "../ChangeUserRoleModal";
import * as usersHooks from "../../hooks";
import type { ChangeUserRoleParams } from "../../api";
import type { UserRead } from "../../types";

vi.mock("../../hooks", () => ({
  useChangeUserRoleMutation: vi.fn(),
}));

const STORE_ID = "33333333-3333-3333-3333-333333333333";

function makeUser(overrides: Partial<UserRead> = {}): UserRead {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    full_name: "Alice Operator",
    email: "alice@example.com",
    role: "staff",
    store_id: STORE_ID,
    is_active: true,
    ...overrides,
  };
}

interface MutationOverrides {
  isPending?: boolean;
  isSuccess?: boolean;
  isError?: boolean;
  error?: Error | null;
  data?: UserRead | null;
}

function makeMutation(o: MutationOverrides = {}): UseMutationResult<
  UserRead,
  Error,
  ChangeUserRoleParams
> & { mutate: ReturnType<typeof vi.fn>; reset: ReturnType<typeof vi.fn> } {
  return {
    mutate: vi.fn(),
    reset: vi.fn(),
    isPending: o.isPending ?? false,
    isSuccess: o.isSuccess ?? false,
    isError: o.isError ?? false,
    error: o.error ?? null,
    data: o.data ?? undefined,
  } as unknown as UseMutationResult<
    UserRead,
    Error,
    ChangeUserRoleParams
  > & {
    mutate: ReturnType<typeof vi.fn>;
    reset: ReturnType<typeof vi.fn>;
  };
}

beforeEach(() => {
  vi.mocked(usersHooks.useChangeUserRoleMutation).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("ChangeUserRoleModal", () => {
  it("renders the user's current role", () => {
    vi.mocked(usersHooks.useChangeUserRoleMutation).mockReturnValue(
      makeMutation(),
    );
    render(
      <ChangeUserRoleModal
        user={makeUser({ role: "staff" })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    expect(
      screen.getByTestId("change-user-role-current"),
    ).toHaveTextContent(/staff/i);
  });

  it("submits the picked role", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useChangeUserRoleMutation).mockReturnValue(
      mutation,
    );
    const user = makeUser({ role: "staff" });
    render(
      <ChangeUserRoleModal user={user} open={true} onOpenChange={vi.fn()} />,
    );
    fireEvent.click(screen.getByTestId("change-user-role-trigger"));
    fireEvent.click(screen.getByRole("option", { name: "Manager" }));
    fireEvent.click(screen.getByTestId("change-user-role-submit"));
    expect(mutation.mutate).toHaveBeenCalledWith({
      userId: user.id,
      body: { role: "manager" },
    });
  });

  it("disables submit when the role is unchanged", () => {
    vi.mocked(usersHooks.useChangeUserRoleMutation).mockReturnValue(
      makeMutation(),
    );
    render(
      <ChangeUserRoleModal
        user={makeUser({ role: "staff" })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("change-user-role-submit")).toBeDisabled();
  });

  it("disables submit while pending", () => {
    vi.mocked(usersHooks.useChangeUserRoleMutation).mockReturnValue(
      makeMutation({ isPending: true }),
    );
    render(
      <ChangeUserRoleModal
        user={makeUser()}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("change-user-role-submit")).toBeDisabled();
    expect(screen.getByTestId("change-user-role-submit")).toHaveTextContent(
      /saving/i,
    );
  });

  it("renders backend error inline without closing", () => {
    const onOpenChange = vi.fn();
    vi.mocked(usersHooks.useChangeUserRoleMutation).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 403,
          message: "You cannot assign role 'admin'.",
        }),
      }),
    );
    render(
      <ChangeUserRoleModal
        user={makeUser()}
        open={true}
        onOpenChange={onOpenChange}
      />,
    );
    expect(
      screen.getByTestId("change-user-role-error"),
    ).toHaveTextContent(/cannot assign role 'admin'/i);
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it("auto-closes and calls onSuccess on success", async () => {
    const onOpenChange = vi.fn();
    const onSuccess = vi.fn();
    const updated = makeUser({ role: "manager" });
    vi.mocked(usersHooks.useChangeUserRoleMutation).mockReturnValue(
      makeMutation({ isSuccess: true, data: updated }),
    );
    render(
      <ChangeUserRoleModal
        user={makeUser({ role: "staff" })}
        open={true}
        onOpenChange={onOpenChange}
        onSuccess={onSuccess}
      />,
    );
    await waitFor(() => {
      expect(onSuccess).toHaveBeenCalledWith(updated);
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });

  it("does not hardcode permission filtering — every role is in the picker", () => {
    vi.mocked(usersHooks.useChangeUserRoleMutation).mockReturnValue(
      makeMutation(),
    );
    render(
      <ChangeUserRoleModal
        user={makeUser({ role: "staff" })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("change-user-role-trigger"));
    for (const label of ["Admin", "Owner", "Manager", "Staff", "Driver"]) {
      expect(screen.getByRole("option", { name: label })).toBeInTheDocument();
    }
  });

  it("shows a fallback when user is null", () => {
    vi.mocked(usersHooks.useChangeUserRoleMutation).mockReturnValue(
      makeMutation(),
    );
    render(
      <ChangeUserRoleModal user={null} open={true} onOpenChange={vi.fn()} />,
    );
    expect(
      screen.getByTestId("change-user-role-no-target"),
    ).toBeInTheDocument();
  });
});
