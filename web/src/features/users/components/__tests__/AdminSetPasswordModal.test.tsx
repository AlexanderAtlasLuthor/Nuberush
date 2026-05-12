// F2.15.6: AdminSetPasswordModal tests.
//
// Pins the wire and copy contracts:
//   - body sends only `{ new_password }` — never `password_hash`.
//   - copy mentions "Set a new password directly" and rules out
//     reset emails, reset tokens, SMTP, invitations.
//   - submit disabled while pending or when input is too short.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { AdminSetPasswordModal } from "../AdminSetPasswordModal";
import * as usersHooks from "../../hooks";
import type { AdminSetUserPasswordParams } from "../../api";
import type { UserRead } from "../../types";

vi.mock("../../hooks", () => ({
  useAdminSetPasswordMutation: vi.fn(),
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
  AdminSetUserPasswordParams
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
    AdminSetUserPasswordParams
  > & {
    mutate: ReturnType<typeof vi.fn>;
    reset: ReturnType<typeof vi.fn>;
  };
}

beforeEach(() => {
  vi.mocked(usersHooks.useAdminSetPasswordMutation).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("AdminSetPasswordModal", () => {
  it("renders the direct-set copy and rules out reset/email/token/SMTP", () => {
    vi.mocked(usersHooks.useAdminSetPasswordMutation).mockReturnValue(
      makeMutation(),
    );
    render(
      <AdminSetPasswordModal
        user={makeUser()}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    expect(
      screen.getByText(/set a new password directly/i),
    ).toBeInTheDocument();
    // Defensive: never advertise a reset/SMTP/invitation flow.
    expect(screen.queryByText(/reset link/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/reset token/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/smtp/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/invitation/i)).not.toBeInTheDocument();
  });

  it("disables submit when password is shorter than 8 chars", () => {
    vi.mocked(usersHooks.useAdminSetPasswordMutation).mockReturnValue(
      makeMutation(),
    );
    render(
      <AdminSetPasswordModal
        user={makeUser()}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("admin-set-password-submit")).toBeDisabled();
    fireEvent.change(screen.getByTestId("admin-set-password-input"), {
      target: { value: "1234567" },
    });
    expect(screen.getByTestId("admin-set-password-submit")).toBeDisabled();
  });

  it("submits only `new_password`", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useAdminSetPasswordMutation).mockReturnValue(
      mutation,
    );
    const user = makeUser();
    render(
      <AdminSetPasswordModal
        user={user}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByTestId("admin-set-password-input"), {
      target: { value: "fresh-secret-1234" },
    });
    fireEvent.click(screen.getByTestId("admin-set-password-submit"));
    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      userId: user.id,
      body: { new_password: "fresh-secret-1234" },
    });
    const args = mutation.mutate.mock
      .calls[0][0] as AdminSetUserPasswordParams;
    expect(Object.keys(args.body)).toEqual(["new_password"]);
    expect(args.body).not.toHaveProperty("password_hash");
  });

  it("does not render any password_hash field", () => {
    vi.mocked(usersHooks.useAdminSetPasswordMutation).mockReturnValue(
      makeMutation(),
    );
    render(
      <AdminSetPasswordModal
        user={makeUser()}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    expect(screen.queryByLabelText(/password_hash/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/password_hash/i)).not.toBeInTheDocument();
  });

  it("disables submit while pending", () => {
    vi.mocked(usersHooks.useAdminSetPasswordMutation).mockReturnValue(
      makeMutation({ isPending: true }),
    );
    render(
      <AdminSetPasswordModal
        user={makeUser()}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("admin-set-password-submit")).toBeDisabled();
    expect(
      screen.getByTestId("admin-set-password-submit"),
    ).toHaveTextContent(/setting/i);
  });

  it("renders backend error inline without closing", () => {
    const onOpenChange = vi.fn();
    vi.mocked(usersHooks.useAdminSetPasswordMutation).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 403,
          message: "Admin privileges required.",
        }),
      }),
    );
    render(
      <AdminSetPasswordModal
        user={makeUser()}
        open={true}
        onOpenChange={onOpenChange}
      />,
    );
    expect(
      screen.getByTestId("admin-set-password-error"),
    ).toHaveTextContent(/admin privileges required/i);
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it("clears the password and calls onSuccess on success", async () => {
    const onOpenChange = vi.fn();
    const onSuccess = vi.fn();
    const updated = makeUser();
    vi.mocked(usersHooks.useAdminSetPasswordMutation).mockReturnValue(
      makeMutation({ isSuccess: true, data: updated }),
    );
    render(
      <AdminSetPasswordModal
        user={makeUser()}
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
});
