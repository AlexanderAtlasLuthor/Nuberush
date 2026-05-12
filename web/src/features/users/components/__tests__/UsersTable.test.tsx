// F2.15.5: UsersTable tests.
//
// Pure presentational coverage. We assert:
//   - the four render branches: loading, error, empty, data,
//   - retry callback wiring,
//   - column shape (Name, Email, Role, Store, Status, optional
//     Actions),
//   - badge labels delegated to UserRoleBadge / UserStatusBadge,
//   - store_id null → "Global",
//   - actions slot visibility + callback,
//   - no inventions of phone / created_at columns.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { UsersTable } from "../UsersTable";
import type { UserRead } from "../../types";

const STORE_A = "33333333-3333-3333-3333-333333333333";
const ALICE: UserRead = {
  id: "11111111-1111-1111-1111-111111111111",
  full_name: "Alice Operator",
  email: "alice@example.com",
  role: "manager",
  store_id: STORE_A,
  is_active: true,
};
const ROOT: UserRead = {
  id: "22222222-2222-2222-2222-222222222222",
  full_name: "Global Admin",
  email: "root@example.com",
  role: "admin",
  store_id: null,
  is_active: false,
};

describe("UsersTable - states", () => {
  it("renders the loading state when isLoading=true", () => {
    render(<UsersTable users={[]} isLoading />);
    expect(screen.getByText("Loading users…")).toBeInTheDocument();
    expect(screen.queryByTestId("users-table")).not.toBeInTheDocument();
  });

  it("renders the error state when error is truthy", () => {
    render(<UsersTable users={[]} error={new Error("boom")} />);
    expect(screen.getByText("Could not load users")).toBeInTheDocument();
    expect(screen.getByText("boom")).toBeInTheDocument();
    expect(screen.queryByTestId("users-table")).not.toBeInTheDocument();
  });

  it("calls onRetry when the retry button is clicked", () => {
    const onRetry = vi.fn();
    render(
      <UsersTable
        users={[]}
        error={new Error("nope")}
        onRetry={onRetry}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: "Retry" }));
    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("renders the default empty state when users is empty", () => {
    render(<UsersTable users={[]} />);
    expect(screen.getByText("No users found")).toBeInTheDocument();
    expect(
      screen.getByText("Try adjusting filters or create a new user."),
    ).toBeInTheDocument();
  });

  it("uses custom emptyTitle / emptyDescription when provided", () => {
    render(
      <UsersTable
        users={[]}
        emptyTitle="Nada"
        emptyDescription="Nada description"
      />,
    );
    expect(screen.getByText("Nada")).toBeInTheDocument();
    expect(screen.getByText("Nada description")).toBeInTheDocument();
  });
});

describe("UsersTable - data rows", () => {
  it("renders one row per user with full_name and email", () => {
    render(<UsersTable users={[ALICE, ROOT]} />);
    const rows = screen.getAllByTestId("users-row");
    expect(rows).toHaveLength(2);

    expect(
      within(rows[0]).getByTestId("users-row-name"),
    ).toHaveTextContent("Alice Operator");
    expect(
      within(rows[0]).getByTestId("users-row-email"),
    ).toHaveTextContent("alice@example.com");

    expect(
      within(rows[1]).getByTestId("users-row-name"),
    ).toHaveTextContent("Global Admin");
    expect(
      within(rows[1]).getByTestId("users-row-email"),
    ).toHaveTextContent("root@example.com");
  });

  it("renders the UserRoleBadge label per row", () => {
    render(<UsersTable users={[ALICE, ROOT]} />);
    expect(screen.getByText("Manager")).toBeInTheDocument();
    expect(screen.getByText("Admin")).toBeInTheDocument();
  });

  it("renders the UserStatusBadge label per row", () => {
    render(<UsersTable users={[ALICE, ROOT]} />);
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Inactive")).toBeInTheDocument();
  });

  it("renders store_id when present", () => {
    render(<UsersTable users={[ALICE]} />);
    expect(
      screen.getByTestId("users-row-store"),
    ).toHaveTextContent(STORE_A);
  });

  it("renders 'Global' when store_id is null", () => {
    render(<UsersTable users={[ROOT]} />);
    expect(
      screen.getByTestId("users-row-store"),
    ).toHaveTextContent("Global");
  });

  it("does not render a phone column", () => {
    render(<UsersTable users={[ALICE, ROOT]} />);
    expect(screen.queryByText(/phone/i)).not.toBeInTheDocument();
  });

  it("does not render a created_at column", () => {
    render(<UsersTable users={[ALICE, ROOT]} />);
    expect(screen.queryByText(/created/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/updated/i)).not.toBeInTheDocument();
  });
});

describe("UsersTable - actions slot", () => {
  it("does not render the Actions column when no actions prop is supplied", () => {
    render(<UsersTable users={[ALICE]} />);
    // No "Actions" header (the column itself is omitted) and no
    // per-row actions cell.
    expect(
      screen.queryByTestId("users-row-actions"),
    ).not.toBeInTheDocument();
  });

  it("renders the Actions column when actions prop is supplied", () => {
    render(
      <UsersTable
        users={[ALICE]}
        actions={(user) => (
          <button type="button" data-testid={`row-cta-${user.id}`}>
            Manage {user.full_name}
          </button>
        )}
      />,
    );
    expect(
      screen.getByTestId("users-row-actions"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId(`row-cta-${ALICE.id}`),
    ).toBeInTheDocument();
  });

  it("invokes the actions callback with the row's user", () => {
    const actions = vi.fn(() => <span>action-cell</span>);
    render(<UsersTable users={[ALICE, ROOT]} actions={actions} />);
    expect(actions).toHaveBeenCalledTimes(2);
    expect(actions).toHaveBeenCalledWith(ALICE);
    expect(actions).toHaveBeenCalledWith(ROOT);
  });
});
