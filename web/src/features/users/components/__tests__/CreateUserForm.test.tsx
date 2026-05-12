// F2.9.3: tests for CreateUserForm.
//
// Strategy mirrors features/products/components/__tests__/ProductFormModal.test.tsx:
// stub `../../hooks` so we can drive `useCreateUserMutation` per case
// and assert (a) wire payload composition, (b) UX validation gating,
// (c) backend success/error rendering, and (d) the role-picker rules.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { CreateUserForm } from "../CreateUserForm";
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

const STORE_ID = "33333333-3333-3333-3333-333333333333";
const NEW_USER_ID = "11111111-1111-1111-1111-111111111111";

function fillRequiredFields(opts?: {
  full_name?: string;
  email?: string;
  password?: string;
  role?: "owner" | "manager" | "staff" | "driver";
}) {
  const {
    full_name = "Jane Operator",
    email = "jane@example.com",
    password = "supersecret123",
    role = "staff",
  } = opts ?? {};

  fireEvent.change(screen.getByTestId("create-user-full-name"), {
    target: { value: full_name },
  });
  fireEvent.change(screen.getByTestId("create-user-email"), {
    target: { value: email },
  });
  fireEvent.change(screen.getByTestId("create-user-password"), {
    target: { value: password },
  });
  fireEvent.click(screen.getByTestId("create-user-role-trigger"));
  fireEvent.click(screen.getByTestId(`user-role-option-${role}`));
}

beforeEach(() => {
  vi.mocked(usersHooks.useCreateUserMutation).mockReset();
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Rendering
// --------------------------------------------------------------------- //

describe("CreateUserForm — rendering", () => {
  it("renders all required and optional fields", () => {
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(makeMutation());

    render(<CreateUserForm />);

    expect(screen.getByTestId("create-user-full-name")).toBeInTheDocument();
    expect(screen.getByTestId("create-user-email")).toBeInTheDocument();
    expect(screen.getByTestId("create-user-password")).toBeInTheDocument();
    expect(screen.getByTestId("create-user-role-trigger")).toBeInTheDocument();
    expect(screen.getByTestId("create-user-store-id")).toBeInTheDocument();
    expect(screen.getByTestId("create-user-phone")).toBeInTheDocument();
    expect(screen.getByTestId("create-user-submit")).toBeInTheDocument();
  });

  it("disables submit by default (form is empty)", () => {
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(makeMutation());

    render(<CreateUserForm />);

    expect(screen.getByTestId("create-user-submit")).toBeDisabled();
  });

  it("hides the cancel button when no onCancel is provided", () => {
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(makeMutation());

    render(<CreateUserForm />);

    expect(screen.queryByTestId("create-user-cancel")).toBeNull();
  });

  it("renders the cancel button when onCancel is provided and wires it", () => {
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(makeMutation());

    const onCancel = vi.fn();
    render(<CreateUserForm onCancel={onCancel} />);

    fireEvent.click(screen.getByTestId("create-user-cancel"));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });
});

// --------------------------------------------------------------------- //
// Role picker — visible options
// --------------------------------------------------------------------- //

describe("CreateUserForm — role picker", () => {
  it("shows owner / manager / staff / driver as creatable roles", () => {
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(makeMutation());

    render(<CreateUserForm />);

    fireEvent.click(screen.getByTestId("create-user-role-trigger"));

    expect(screen.getByTestId("user-role-option-owner")).toBeInTheDocument();
    expect(screen.getByTestId("user-role-option-manager")).toBeInTheDocument();
    expect(screen.getByTestId("user-role-option-staff")).toBeInTheDocument();
    expect(screen.getByTestId("user-role-option-driver")).toBeInTheDocument();
  });

  it("does NOT show admin as a creatable role", () => {
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(makeMutation());

    render(<CreateUserForm />);

    fireEvent.click(screen.getByTestId("create-user-role-trigger"));

    expect(screen.queryByTestId("user-role-option-admin")).toBeNull();
    expect(screen.queryByRole("option", { name: /^admin$/i })).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// Submit — payload composition
// --------------------------------------------------------------------- //

describe("CreateUserForm — submit payload", () => {
  it("forwards required-only fields verbatim and omits empty optionals", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(mutation);

    render(<CreateUserForm />);
    fillRequiredFields();
    fireEvent.click(screen.getByTestId("create-user-submit"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      body: {
        full_name: "Jane Operator",
        email: "jane@example.com",
        password: "supersecret123",
        role: "staff",
      },
    });
    const sent = mutation.mutate.mock.calls[0][0] as { body: object };
    expect("store_id" in sent.body).toBe(false);
    expect("phone" in sent.body).toBe(false);
  });

  it("includes store_id and phone when provided", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(mutation);

    render(<CreateUserForm />);
    fillRequiredFields({ role: "driver" });
    fireEvent.change(screen.getByTestId("create-user-store-id"), {
      target: { value: STORE_ID },
    });
    fireEvent.change(screen.getByTestId("create-user-phone"), {
      target: { value: "+15555550123" },
    });
    fireEvent.click(screen.getByTestId("create-user-submit"));

    expect(mutation.mutate).toHaveBeenCalledWith({
      body: {
        full_name: "Jane Operator",
        email: "jane@example.com",
        password: "supersecret123",
        role: "driver",
        store_id: STORE_ID,
        phone: "+15555550123",
      },
    });
  });

  it("trims whitespace on full_name, email, store_id and phone", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(mutation);

    render(<CreateUserForm />);
    fireEvent.change(screen.getByTestId("create-user-full-name"), {
      target: { value: "  Jane Operator  " },
    });
    fireEvent.change(screen.getByTestId("create-user-email"), {
      target: { value: "  jane@example.com  " },
    });
    fireEvent.change(screen.getByTestId("create-user-password"), {
      target: { value: "supersecret123" },
    });
    fireEvent.change(screen.getByTestId("create-user-store-id"), {
      target: { value: `  ${STORE_ID}  ` },
    });
    fireEvent.change(screen.getByTestId("create-user-phone"), {
      target: { value: "  +1 555  " },
    });
    fireEvent.click(screen.getByTestId("create-user-role-trigger"));
    fireEvent.click(screen.getByTestId("user-role-option-staff"));
    fireEvent.click(screen.getByTestId("create-user-submit"));

    expect(mutation.mutate).toHaveBeenCalledWith({
      body: {
        full_name: "Jane Operator",
        email: "jane@example.com",
        password: "supersecret123",
        role: "staff",
        store_id: STORE_ID,
        phone: "+1 555",
      },
    });
  });

  it("omits store_id when only whitespace is entered", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(mutation);

    render(<CreateUserForm />);
    fillRequiredFields();
    fireEvent.change(screen.getByTestId("create-user-store-id"), {
      target: { value: "   " },
    });
    fireEvent.click(screen.getByTestId("create-user-submit"));

    const sent = mutation.mutate.mock.calls[0][0] as { body: object };
    expect("store_id" in sent.body).toBe(false);
  });
});

// --------------------------------------------------------------------- //
// UX validation
// --------------------------------------------------------------------- //

describe("CreateUserForm — client validation", () => {
  it("blocks submit when full_name is empty", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(mutation);

    render(<CreateUserForm />);
    fillRequiredFields({ full_name: "   " });
    fireEvent.click(screen.getByTestId("create-user-submit"));

    expect(screen.getByTestId("create-user-submit")).toBeDisabled();
    expect(mutation.mutate).not.toHaveBeenCalled();
  });

  it("blocks submit when email format is invalid", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(mutation);

    render(<CreateUserForm />);
    fillRequiredFields({ email: "not-an-email" });

    expect(screen.getByTestId("create-user-submit")).toBeDisabled();
    fireEvent.click(screen.getByTestId("create-user-submit"));
    expect(mutation.mutate).not.toHaveBeenCalled();
  });

  it("blocks submit when password is shorter than 8 characters", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(mutation);

    render(<CreateUserForm />);
    fillRequiredFields({ password: "short7!" });

    expect(screen.getByTestId("create-user-submit")).toBeDisabled();
    fireEvent.click(screen.getByTestId("create-user-submit"));
    expect(mutation.mutate).not.toHaveBeenCalled();
  });

  it("blocks submit when role is not picked", () => {
    const mutation = makeMutation();
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(mutation);

    render(<CreateUserForm />);
    fireEvent.change(screen.getByTestId("create-user-full-name"), {
      target: { value: "Jane Operator" },
    });
    fireEvent.change(screen.getByTestId("create-user-email"), {
      target: { value: "jane@example.com" },
    });
    fireEvent.change(screen.getByTestId("create-user-password"), {
      target: { value: "supersecret123" },
    });

    expect(screen.getByTestId("create-user-submit")).toBeDisabled();
    fireEvent.click(screen.getByTestId("create-user-submit"));
    expect(mutation.mutate).not.toHaveBeenCalled();
  });

  it("disables submit while pending and shows loading copy", () => {
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(
      makeMutation({ isPending: true }),
    );

    render(<CreateUserForm />);
    // Even with valid-looking inputs, isPending forces the disable.
    fireEvent.change(screen.getByTestId("create-user-full-name"), {
      target: { value: "Jane Operator" },
    });
    fireEvent.change(screen.getByTestId("create-user-email"), {
      target: { value: "jane@example.com" },
    });
    fireEvent.change(screen.getByTestId("create-user-password"), {
      target: { value: "supersecret123" },
    });

    const submit = screen.getByTestId("create-user-submit");
    expect(submit).toBeDisabled();
    expect(submit).toHaveTextContent(/creating/i);
  });
});

// --------------------------------------------------------------------- //
// Backend success / error UX
// --------------------------------------------------------------------- //

describe("CreateUserForm — server feedback", () => {
  it("shows the backend detail on a 403 error without crashing", () => {
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 403,
          message: "You cannot create users in another store.",
        }),
      }),
    );

    render(<CreateUserForm />);

    expect(screen.getByTestId("create-user-error")).toHaveTextContent(
      /You cannot create users in another store\./i,
    );
  });

  it("shows the backend detail on a 409 duplicate-email error", () => {
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 409,
          message: "Email already registered.",
        }),
      }),
    );

    render(<CreateUserForm />);

    expect(screen.getByTestId("create-user-error")).toHaveTextContent(
      /email already registered/i,
    );
  });

  it("shows the backend detail on a 422 validation error", () => {
    vi.mocked(usersHooks.useCreateUserMutation).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 422,
          message: "value is not a valid email address",
        }),
      }),
    );

    render(<CreateUserForm />);

    expect(screen.getByTestId("create-user-error")).toHaveTextContent(
      /not a valid email/i,
    );
  });

  it("shows the success panel and calls onCreated with the created user", async () => {
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

    const onCreated = vi.fn();
    render(<CreateUserForm onCreated={onCreated} />);

    expect(screen.getByTestId("create-user-success")).toHaveTextContent(
      /Created Jane Operator \(jane@example.com\) as staff\./i,
    );
    await waitFor(() => {
      expect(onCreated).toHaveBeenCalledWith(created);
    });
  });
});

// --------------------------------------------------------------------- //
// Architecture guards
// --------------------------------------------------------------------- //

describe("CreateUserForm — architecture", () => {
  it("does NOT import or reference useAuth / currentUser / role checks (compile-time guarantee)", async () => {
    // Source-level guard: scan the form module for forbidden tokens.
    // We import it dynamically so the test file does not transitively
    // pull useAuth into its own dep graph.
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(
      __dirname,
      "..",
      "CreateUserForm.tsx",
    );
    const source = fs.readFileSync(here, "utf-8");

    // Strip /* ... */ block comments and // line comments so rationale
    // text in the file header doesn't trigger false positives.
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
    // Permission-style equality on a `.role` access in CODE (the
    // comment-stripped source). Cosmetic role rendering elsewhere is
    // out of scope for this form.
    expect(code).not.toMatch(/\.role\s*===\s*["']/);
  });
});
