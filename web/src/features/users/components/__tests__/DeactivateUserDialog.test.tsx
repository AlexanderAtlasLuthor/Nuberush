// F2.15.6: DeactivateUserDialog tests.
//
// Pins the two-mutation contract: active user → deactivate mutation,
// inactive user → reactivate mutation. We mock both hooks and assert
// only the right one fires, plus the standard auto-close + inline
// error invariants.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { DeactivateUserDialog } from "../DeactivateUserDialog";
import * as usersHooks from "../../hooks";
import type {
  DeactivateUserParams,
  ReactivateUserParams,
} from "../../api";
import type { UserRead } from "../../types";

vi.mock("../../hooks", () => ({
  useDeactivateUserMutation: vi.fn(),
  useReactivateUserMutation: vi.fn(),
}));

const STORE_ID = "33333333-3333-3333-3333-333333333333";

function makeUser(overrides: Partial<UserRead> = {}): UserRead {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    full_name: "Alice Operator",
    email: "alice@example.com",
    role: "manager",
    store_id: STORE_ID,
    is_active: true,
    ...overrides,
  };
}

interface MutationOverrides<T> {
  isPending?: boolean;
  isSuccess?: boolean;
  isError?: boolean;
  error?: Error | null;
  data?: T | null;
}

function makeMutation<P>(o: MutationOverrides<UserRead> = {}): UseMutationResult<
  UserRead,
  Error,
  P
> & { mutate: ReturnType<typeof vi.fn>; reset: ReturnType<typeof vi.fn> } {
  return {
    mutate: vi.fn(),
    reset: vi.fn(),
    isPending: o.isPending ?? false,
    isSuccess: o.isSuccess ?? false,
    isError: o.isError ?? false,
    error: o.error ?? null,
    data: o.data ?? undefined,
  } as unknown as UseMutationResult<UserRead, Error, P> & {
    mutate: ReturnType<typeof vi.fn>;
    reset: ReturnType<typeof vi.fn>;
  };
}

beforeEach(() => {
  vi.mocked(usersHooks.useDeactivateUserMutation).mockReset();
  vi.mocked(usersHooks.useReactivateUserMutation).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("DeactivateUserDialog", () => {
  it("renders Deactivate copy when the user is active", () => {
    vi.mocked(usersHooks.useDeactivateUserMutation).mockReturnValue(
      makeMutation<DeactivateUserParams>(),
    );
    vi.mocked(usersHooks.useReactivateUserMutation).mockReturnValue(
      makeMutation<ReactivateUserParams>(),
    );
    render(
      <DeactivateUserDialog
        user={makeUser({ is_active: true })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    expect(screen.getByText("Deactivate user")).toBeInTheDocument();
    expect(
      screen.getByTestId("deactivate-user-confirm"),
    ).toHaveTextContent(/^deactivate$/i);
  });

  it("renders Reactivate copy when the user is inactive", () => {
    vi.mocked(usersHooks.useDeactivateUserMutation).mockReturnValue(
      makeMutation<DeactivateUserParams>(),
    );
    vi.mocked(usersHooks.useReactivateUserMutation).mockReturnValue(
      makeMutation<ReactivateUserParams>(),
    );
    render(
      <DeactivateUserDialog
        user={makeUser({ is_active: false })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    expect(screen.getByText("Reactivate user")).toBeInTheDocument();
    expect(
      screen.getByTestId("deactivate-user-confirm"),
    ).toHaveTextContent(/^reactivate$/i);
  });

  it("calls deactivate mutation when active user confirms", () => {
    const deactivate = makeMutation<DeactivateUserParams>();
    const reactivate = makeMutation<ReactivateUserParams>();
    vi.mocked(usersHooks.useDeactivateUserMutation).mockReturnValue(
      deactivate,
    );
    vi.mocked(usersHooks.useReactivateUserMutation).mockReturnValue(
      reactivate,
    );
    const user = makeUser({ is_active: true });
    render(
      <DeactivateUserDialog
        user={user}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("deactivate-user-confirm"));
    expect(deactivate.mutate).toHaveBeenCalledWith({ userId: user.id });
    expect(reactivate.mutate).not.toHaveBeenCalled();
  });

  it("calls reactivate mutation when inactive user confirms", () => {
    const deactivate = makeMutation<DeactivateUserParams>();
    const reactivate = makeMutation<ReactivateUserParams>();
    vi.mocked(usersHooks.useDeactivateUserMutation).mockReturnValue(
      deactivate,
    );
    vi.mocked(usersHooks.useReactivateUserMutation).mockReturnValue(
      reactivate,
    );
    const user = makeUser({ is_active: false });
    render(
      <DeactivateUserDialog
        user={user}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("deactivate-user-confirm"));
    expect(reactivate.mutate).toHaveBeenCalledWith({ userId: user.id });
    expect(deactivate.mutate).not.toHaveBeenCalled();
  });

  it("renders user full_name and email", () => {
    vi.mocked(usersHooks.useDeactivateUserMutation).mockReturnValue(
      makeMutation<DeactivateUserParams>(),
    );
    vi.mocked(usersHooks.useReactivateUserMutation).mockReturnValue(
      makeMutation<ReactivateUserParams>(),
    );
    render(
      <DeactivateUserDialog
        user={makeUser()}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    expect(
      screen.getByTestId("deactivate-user-name"),
    ).toHaveTextContent("Alice Operator");
    expect(
      screen.getByTestId("deactivate-user-email"),
    ).toHaveTextContent("alice@example.com");
  });

  it("disables confirm while pending (active path)", () => {
    vi.mocked(usersHooks.useDeactivateUserMutation).mockReturnValue(
      makeMutation<DeactivateUserParams>({ isPending: true }),
    );
    vi.mocked(usersHooks.useReactivateUserMutation).mockReturnValue(
      makeMutation<ReactivateUserParams>(),
    );
    render(
      <DeactivateUserDialog
        user={makeUser({ is_active: true })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("deactivate-user-confirm")).toBeDisabled();
    expect(screen.getByTestId("deactivate-user-confirm")).toHaveTextContent(
      /deactivating/i,
    );
  });

  it("renders backend error inline without closing", () => {
    const onOpenChange = vi.fn();
    vi.mocked(usersHooks.useDeactivateUserMutation).mockReturnValue(
      makeMutation<DeactivateUserParams>({
        isError: true,
        error: new ApiError({
          status: 422,
          message: "Cannot deactivate the last active admin.",
        }),
      }),
    );
    vi.mocked(usersHooks.useReactivateUserMutation).mockReturnValue(
      makeMutation<ReactivateUserParams>(),
    );
    render(
      <DeactivateUserDialog
        user={makeUser({ is_active: true })}
        open={true}
        onOpenChange={onOpenChange}
      />,
    );
    expect(
      screen.getByTestId("deactivate-user-error"),
    ).toHaveTextContent(/last active admin/i);
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it("auto-closes and calls onSuccess on success", async () => {
    const onOpenChange = vi.fn();
    const onSuccess = vi.fn();
    const updated = makeUser({ is_active: false });
    vi.mocked(usersHooks.useDeactivateUserMutation).mockReturnValue(
      makeMutation<DeactivateUserParams>({
        isSuccess: true,
        data: updated,
      }),
    );
    vi.mocked(usersHooks.useReactivateUserMutation).mockReturnValue(
      makeMutation<ReactivateUserParams>(),
    );
    render(
      <DeactivateUserDialog
        user={makeUser({ is_active: true })}
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

  it("user=null shows fallback and confirm button is disabled", () => {
    vi.mocked(usersHooks.useDeactivateUserMutation).mockReturnValue(
      makeMutation<DeactivateUserParams>(),
    );
    vi.mocked(usersHooks.useReactivateUserMutation).mockReturnValue(
      makeMutation<ReactivateUserParams>(),
    );
    render(
      <DeactivateUserDialog
        user={null}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    expect(
      screen.getByTestId("deactivate-user-no-target"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("deactivate-user-confirm")).toBeDisabled();
  });
});
