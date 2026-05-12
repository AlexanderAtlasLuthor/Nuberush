// F2.15.6: EditUserModal tests.
//
// Mocks `useUpdateUserMutation` and asserts payload composition,
// loading/error/success rendering, and the schema-locked invariants
// (no email/role/store/is_active/password fields rendered).

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { EditUserModal } from "../EditUserModal";
import * as usersHooks from "../../hooks";
import type { UpdateUserParams } from "../../api";
import type { UserRead } from "../../types";

vi.mock("../../hooks", () => ({
  useUpdateUserMutation: vi.fn(),
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
  UpdateUserParams
> & { mutate: ReturnType<typeof vi.fn>; reset: ReturnType<typeof vi.fn> } {
  return {
    mutate: vi.fn(),
    reset: vi.fn(),
    isPending: o.isPending ?? false,
    isSuccess: o.isSuccess ?? false,
    isError: o.isError ?? false,
    error: o.error ?? null,
    data: o.data ?? undefined,
  } as unknown as UseMutationResult<UserRead, Error, UpdateUserParams> & {
    mutate: ReturnType<typeof vi.fn>;
    reset: ReturnType<typeof vi.fn>;
  };
}

beforeEach(() => {
  vi.mocked(usersHooks.useUpdateUserMutation).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("EditUserModal", () => {
  it("renders the user's current name and email", () => {
    vi.mocked(usersHooks.useUpdateUserMutation).mockReturnValue(
      makeMutation(),
    );
    render(
      <EditUserModal user={makeUser()} open={true} onOpenChange={vi.fn()} />,
    );
    expect(
      screen.getByTestId("edit-user-current-name"),
    ).toHaveTextContent("Alice Operator");
    expect(
      screen.getByTestId("edit-user-current-email"),
    ).toHaveTextContent("alice@example.com");
  });

  it("initialises full_name with user.full_name", () => {
    vi.mocked(usersHooks.useUpdateUserMutation).mockReturnValue(
      makeMutation(),
    );
    render(
      <EditUserModal user={makeUser()} open={true} onOpenChange={vi.fn()} />,
    );
    const input = screen.getByTestId("edit-user-full-name") as HTMLInputElement;
    expect(input.value).toBe("Alice Operator");
  });

  it("initialises phone as empty (UserRead does not carry phone)", () => {
    vi.mocked(usersHooks.useUpdateUserMutation).mockReturnValue(
      makeMutation(),
    );
    render(
      <EditUserModal user={makeUser()} open={true} onOpenChange={vi.fn()} />,
    );
    const input = screen.getByTestId("edit-user-phone") as HTMLInputElement;
    expect(input.value).toBe("");
  });

  it("submits trimmed full_name and trimmed phone when phone is touched", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useUpdateUserMutation).mockReturnValue(mutation);
    const user = makeUser();
    render(
      <EditUserModal user={user} open={true} onOpenChange={vi.fn()} />,
    );
    fireEvent.change(screen.getByTestId("edit-user-full-name"), {
      target: { value: "  New Name  " },
    });
    fireEvent.change(screen.getByTestId("edit-user-phone"), {
      target: { value: "  +1-555-9999  " },
    });
    fireEvent.click(screen.getByTestId("edit-user-submit"));

    expect(mutation.mutate).toHaveBeenCalledWith({
      userId: user.id,
      body: { full_name: "New Name", phone: "+1-555-9999" },
    });
  });

  // F2.15.10 hardening: phone is only sent when the operator actually
  // touched the field. Saving with an untouched phone must NOT include
  // `phone` in the body (otherwise the existing server value would be
  // silently wiped).
  it("omits phone from the body when the field is untouched", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useUpdateUserMutation).mockReturnValue(mutation);
    const user = makeUser();
    render(
      <EditUserModal user={user} open={true} onOpenChange={vi.fn()} />,
    );
    fireEvent.click(screen.getByTestId("edit-user-submit"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    const callArg = mutation.mutate.mock.calls[0][0] as {
      userId: string;
      body: Record<string, unknown>;
    };
    expect(callArg.userId).toBe(user.id);
    expect(callArg.body).toEqual({ full_name: "Alice Operator" });
    expect(callArg.body).not.toHaveProperty("phone");
  });

  it("submits phone:null when the operator touched and then cleared the field", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useUpdateUserMutation).mockReturnValue(mutation);
    const user = makeUser();
    render(
      <EditUserModal user={user} open={true} onOpenChange={vi.fn()} />,
    );
    // Touch the field with a value, then clear it — this is the only
    // path that should send an explicit null clear to the server.
    fireEvent.change(screen.getByTestId("edit-user-phone"), {
      target: { value: "+1-555-0000" },
    });
    fireEvent.change(screen.getByTestId("edit-user-phone"), {
      target: { value: "" },
    });
    fireEvent.click(screen.getByTestId("edit-user-submit"));

    expect(mutation.mutate).toHaveBeenCalledWith({
      userId: user.id,
      body: { full_name: "Alice Operator", phone: null },
    });
  });

  it("submits phone:null when the operator types only whitespace after touching", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useUpdateUserMutation).mockReturnValue(mutation);
    const user = makeUser();
    render(
      <EditUserModal user={user} open={true} onOpenChange={vi.fn()} />,
    );
    fireEvent.change(screen.getByTestId("edit-user-phone"), {
      target: { value: "   " },
    });
    fireEvent.click(screen.getByTestId("edit-user-submit"));

    expect(mutation.mutate).toHaveBeenCalledWith({
      userId: user.id,
      body: { full_name: "Alice Operator", phone: null },
    });
  });

  it("does not render fields for email, role, store_id, is_active, password", () => {
    vi.mocked(usersHooks.useUpdateUserMutation).mockReturnValue(
      makeMutation(),
    );
    render(
      <EditUserModal user={makeUser()} open={true} onOpenChange={vi.fn()} />,
    );
    // Radix Dialog renders to a portal under document.body; query the
    // whole document rather than the original render container.
    const inputs = document.body.querySelectorAll("input, select, textarea");
    const editableIds = Array.from(inputs)
      .map((el) => el.id)
      .filter(Boolean);
    expect(editableIds.sort()).toEqual(
      ["edit-user-full-name", "edit-user-phone"].sort(),
    );
    // Defensive: no labels for forbidden fields.
    expect(screen.queryByLabelText(/^role$/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/store/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/active/i)).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/password/i)).not.toBeInTheDocument();
  });

  it("disables submit while pending", () => {
    vi.mocked(usersHooks.useUpdateUserMutation).mockReturnValue(
      makeMutation({ isPending: true }),
    );
    render(
      <EditUserModal user={makeUser()} open={true} onOpenChange={vi.fn()} />,
    );
    expect(screen.getByTestId("edit-user-submit")).toBeDisabled();
    expect(screen.getByTestId("edit-user-submit")).toHaveTextContent(
      /saving/i,
    );
  });

  it("renders backend error inline without closing", () => {
    const onOpenChange = vi.fn();
    vi.mocked(usersHooks.useUpdateUserMutation).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({ status: 403, message: "Forbidden by matrix" }),
      }),
    );
    render(
      <EditUserModal
        user={makeUser()}
        open={true}
        onOpenChange={onOpenChange}
      />,
    );
    expect(screen.getByTestId("edit-user-error")).toHaveTextContent(
      /forbidden by matrix/i,
    );
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it("calls onSuccess and closes on mutation success", async () => {
    const onOpenChange = vi.fn();
    const onSuccess = vi.fn();
    const updated = makeUser({ full_name: "Renamed" });
    vi.mocked(usersHooks.useUpdateUserMutation).mockReturnValue(
      makeMutation({ isSuccess: true, data: updated }),
    );
    render(
      <EditUserModal
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

  it("renders a 'no user selected' fallback when user is null", () => {
    vi.mocked(usersHooks.useUpdateUserMutation).mockReturnValue(
      makeMutation(),
    );
    render(
      <EditUserModal user={null} open={true} onOpenChange={vi.fn()} />,
    );
    expect(screen.getByTestId("edit-user-no-target")).toBeInTheDocument();
    expect(screen.queryByTestId("edit-user-form")).not.toBeInTheDocument();
  });

  // F2.15.10 hardening: phoneTouched must reset when the modal
  // re-opens or switches to a different row. Otherwise an operator
  // who touched phone in one session and reopened on a fresh user
  // would still send a clearing null on the next save.
  it("resets phoneTouched when the modal re-opens on a different user", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useUpdateUserMutation).mockReturnValue(mutation);
    const userA = makeUser({
      id: "11111111-1111-1111-1111-111111111111",
      full_name: "Alice",
    });
    const userB = makeUser({
      id: "22222222-2222-2222-2222-222222222222",
      full_name: "Bob",
    });

    const { rerender } = render(
      <EditUserModal user={userA} open={true} onOpenChange={vi.fn()} />,
    );
    // Touch phone for Alice so phoneTouched becomes true.
    fireEvent.change(screen.getByTestId("edit-user-phone"), {
      target: { value: "+1-555-0001" },
    });

    // Switch the modal to Bob (simulating "open on a different row").
    // The useEffect keyed on user.id resets phone + phoneTouched.
    rerender(
      <EditUserModal user={userB} open={true} onOpenChange={vi.fn()} />,
    );

    // Click submit without touching phone in the new session — body
    // must NOT include phone for Bob.
    fireEvent.click(screen.getByTestId("edit-user-submit"));
    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    const callArg = mutation.mutate.mock.calls[0][0] as {
      userId: string;
      body: Record<string, unknown>;
    };
    expect(callArg.userId).toBe(userB.id);
    expect(callArg.body).toEqual({ full_name: "Bob" });
    expect(callArg.body).not.toHaveProperty("phone");
  });
});
