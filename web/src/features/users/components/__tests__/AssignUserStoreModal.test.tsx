// F2.15.6: AssignUserStoreModal tests.
//
// Pins:
//   - empty input → null on the wire (admin-target signal),
//   - trimmed UUID submission,
//   - inline error on backend rejection (admin-only / inactive store),
//   - auto-close on success,
//   - no fake store names / picker.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { AssignUserStoreModal } from "../AssignUserStoreModal";
import * as usersHooks from "../../hooks";
import type { AssignUserStoreParams } from "../../api";
import type { UserRead } from "../../types";

vi.mock("../../hooks", () => ({
  useAssignUserStoreMutation: vi.fn(),
}));

const STORE_A = "33333333-3333-3333-3333-333333333333";
const STORE_B = "44444444-4444-4444-4444-444444444444";

function makeUser(overrides: Partial<UserRead> = {}): UserRead {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    full_name: "Alice Operator",
    email: "alice@example.com",
    role: "staff",
    store_id: STORE_A,
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
  AssignUserStoreParams
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
    AssignUserStoreParams
  > & {
    mutate: ReturnType<typeof vi.fn>;
    reset: ReturnType<typeof vi.fn>;
  };
}

beforeEach(() => {
  vi.mocked(usersHooks.useAssignUserStoreMutation).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("AssignUserStoreModal", () => {
  it("renders the user's current store_id", () => {
    vi.mocked(usersHooks.useAssignUserStoreMutation).mockReturnValue(
      makeMutation(),
    );
    render(
      <AssignUserStoreModal
        user={makeUser({ store_id: STORE_A })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    expect(
      screen.getByTestId("assign-user-store-current"),
    ).toHaveTextContent(STORE_A);
    const input = screen.getByTestId(
      "assign-user-store-input",
    ) as HTMLInputElement;
    expect(input.value).toBe(STORE_A);
  });

  it("initialises empty when store_id is null (Global)", () => {
    vi.mocked(usersHooks.useAssignUserStoreMutation).mockReturnValue(
      makeMutation(),
    );
    render(
      <AssignUserStoreModal
        user={makeUser({ store_id: null, role: "admin" })}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    expect(
      screen.getByTestId("assign-user-store-current"),
    ).toHaveTextContent("Global");
    const input = screen.getByTestId(
      "assign-user-store-input",
    ) as HTMLInputElement;
    expect(input.value).toBe("");
  });

  it("submits a trimmed UUID", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useAssignUserStoreMutation).mockReturnValue(
      mutation,
    );
    const user = makeUser();
    render(
      <AssignUserStoreModal
        user={user}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    fireEvent.change(screen.getByTestId("assign-user-store-input"), {
      target: { value: `  ${STORE_B}  ` },
    });
    fireEvent.click(screen.getByTestId("assign-user-store-submit"));
    expect(mutation.mutate).toHaveBeenCalledWith({
      userId: user.id,
      body: { store_id: STORE_B },
    });
  });

  it("submits store_id=null when the input is empty", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useAssignUserStoreMutation).mockReturnValue(
      mutation,
    );
    const user = makeUser({ store_id: null, role: "admin" });
    render(
      <AssignUserStoreModal
        user={user}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    fireEvent.click(screen.getByTestId("assign-user-store-submit"));
    expect(mutation.mutate).toHaveBeenCalledWith({
      userId: user.id,
      body: { store_id: null },
    });
  });

  it("disables submit while pending", () => {
    vi.mocked(usersHooks.useAssignUserStoreMutation).mockReturnValue(
      makeMutation({ isPending: true }),
    );
    render(
      <AssignUserStoreModal
        user={makeUser()}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    expect(screen.getByTestId("assign-user-store-submit")).toBeDisabled();
    expect(
      screen.getByTestId("assign-user-store-submit"),
    ).toHaveTextContent(/assigning/i);
  });

  it("renders backend error inline without closing", () => {
    const onOpenChange = vi.fn();
    vi.mocked(usersHooks.useAssignUserStoreMutation).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 400,
          message: "Store is inactive.",
        }),
      }),
    );
    render(
      <AssignUserStoreModal
        user={makeUser()}
        open={true}
        onOpenChange={onOpenChange}
      />,
    );
    expect(
      screen.getByTestId("assign-user-store-error"),
    ).toHaveTextContent(/store is inactive/i);
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it("auto-closes and calls onSuccess on success", async () => {
    const onOpenChange = vi.fn();
    const onSuccess = vi.fn();
    const updated = makeUser({ store_id: STORE_B });
    vi.mocked(usersHooks.useAssignUserStoreMutation).mockReturnValue(
      makeMutation({ isSuccess: true, data: updated }),
    );
    render(
      <AssignUserStoreModal
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

  it("does not render a store-name picker (raw UUID only)", () => {
    vi.mocked(usersHooks.useAssignUserStoreMutation).mockReturnValue(
      makeMutation(),
    );
    render(
      <AssignUserStoreModal
        user={makeUser()}
        open={true}
        onOpenChange={vi.fn()}
      />,
    );
    // No combobox / select trigger — just a text input.
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    // Copy makes the store-ID-or-blank rule explicit.
    expect(screen.getByText(/store id, or leave blank/i)).toBeInTheDocument();
  });
});
