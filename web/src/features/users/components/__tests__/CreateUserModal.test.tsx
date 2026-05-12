// F2.9.3: tests for CreateUserModal.
//
// Pattern matches features/products/components/__tests__/ProductFormModal.test.tsx:
// stub `../../hooks` so we can drive `useCreateUserMutation` per case.
// The modal is a thin Dialog wrapper around CreateUserForm — we only
// assert the open/onOpenChange/onCreated contract and the close-on-
// success behaviour. Field-level coverage lives in CreateUserForm.test.tsx.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { CreateUserModal } from "../CreateUserModal";
import * as usersHooks from "../../hooks";
import type { CreateUserParams } from "../../api";
import type { UserRead } from "../../types";

vi.mock("../../hooks", () => ({
  useCreateUserMutation: vi.fn(),
}));

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
  CreateUserParams
> & { mutate: ReturnType<typeof vi.fn> } {
  const mutate = vi.fn();
  return {
    mutate,
    isPending: o.isPending ?? false,
    isSuccess: o.isSuccess ?? false,
    isError: o.isError ?? false,
    error: o.error ?? null,
    data: o.data ?? undefined,
    reset: vi.fn(),
  } as unknown as UseMutationResult<UserRead, Error, CreateUserParams> & {
    mutate: ReturnType<typeof vi.fn>;
  };
}

const NEW_USER_ID = "11111111-1111-1111-1111-111111111111";
const STORE_ID = "33333333-3333-3333-3333-333333333333";

beforeEach(() => {
  vi.mocked(usersHooks.useCreateUserMutation).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("CreateUserModal", () => {
  it("does not render when open=false", () => {
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(makeMutation());

    render(
      <CreateUserModal open={false} onOpenChange={vi.fn()} />,
    );

    expect(screen.queryByTestId("create-user-modal")).toBeNull();
    expect(screen.queryByTestId("create-user-form")).toBeNull();
  });

  it("renders the form when open=true", () => {
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(makeMutation());

    render(
      <CreateUserModal open={true} onOpenChange={vi.fn()} />,
    );

    expect(screen.getByTestId("create-user-modal")).toBeInTheDocument();
    expect(screen.getByTestId("create-user-form")).toBeInTheDocument();
  });

  it("closes and calls onCreated with the created user on mutation success", async () => {
    const created: UserRead = {
      id: NEW_USER_ID,
      full_name: "Jane Operator",
      email: "jane@example.com",
      role: "staff",
      store_id: STORE_ID,
      is_active: true,
    };
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(
      makeMutation({ isSuccess: true, data: created }),
    );

    const onOpenChange = vi.fn();
    const onCreated = vi.fn();
    render(
      <CreateUserModal
        open={true}
        onOpenChange={onOpenChange}
        onCreated={onCreated}
      />,
    );

    await waitFor(() => {
      expect(onCreated).toHaveBeenCalledWith(created);
      expect(onOpenChange).toHaveBeenCalledWith(false);
    });
  });
});
