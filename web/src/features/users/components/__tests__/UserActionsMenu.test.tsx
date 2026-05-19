// F2.15.6: UserActionsMenu tests.
//
// Pure presentational + callback router. We assert which menu items
// surface for which props, that clicking them calls the matching
// callback with the row's user, and that admin-only items hide
// behind `showAdminActions`.
//
// Radix `DropdownMenu` cannot be opened via `fireEvent` in jsdom
// because it listens to pointer events that the testing harness
// does not synthesise (see InventoryActions.test.tsx for the
// project-wide precedent). We mock the primitive so the menu
// content renders inline; then `fireEvent.click` on each item is
// a plain button click.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { ReactNode } from "react";

import { UserActionsMenu } from "../UserActionsMenu";
import type { UserRead } from "../../types";

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

// With the Radix mock above, every menu item is rendered inline,
// so opening the menu is a no-op. We keep the helper to keep the
// test bodies clear about intent.
function openMenu() {
  /* no-op when the dropdown is mocked inline */
}

describe("UserActionsMenu - rendering", () => {
  it("renders the trigger with an aria-label including the user name", () => {
    render(<UserActionsMenu user={makeUser()} />);
    const trigger = screen.getByTestId("user-actions-trigger");
    expect(trigger).toHaveAttribute(
      "aria-label",
      "Open actions for Alice Operator",
    );
  });

  it("renders Edit only when onEdit is provided", () => {
    const onEdit = vi.fn();
    const { rerender } = render(<UserActionsMenu user={makeUser()} />);
    openMenu();
    expect(screen.queryByTestId("user-action-edit")).not.toBeInTheDocument();

    rerender(<UserActionsMenu user={makeUser()} onEdit={onEdit} />);
    openMenu();
    expect(screen.getByTestId("user-action-edit")).toBeInTheDocument();
  });

  it("renders Deactivate when user is active and the lifecycle callback exists", () => {
    render(
      <UserActionsMenu
        user={makeUser({ is_active: true })}
        onDeactivateReactivate={vi.fn()}
      />,
    );
    openMenu();
    expect(
      screen.getByTestId("user-action-deactivate"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("user-action-reactivate"),
    ).not.toBeInTheDocument();
  });

  it("renders Reactivate when user is inactive and the lifecycle callback exists", () => {
    render(
      <UserActionsMenu
        user={makeUser({ is_active: false })}
        onDeactivateReactivate={vi.fn()}
      />,
    );
    openMenu();
    expect(
      screen.getByTestId("user-action-reactivate"),
    ).toBeInTheDocument();
    expect(
      screen.queryByTestId("user-action-deactivate"),
    ).not.toBeInTheDocument();
  });

  it("hides admin items when showAdminActions=false", () => {
    render(
      <UserActionsMenu
        user={makeUser()}
        onAssignStore={vi.fn()}
        showAdminActions={false}
      />,
    );
    openMenu();
    expect(
      screen.queryByTestId("user-action-assign-store"),
    ).not.toBeInTheDocument();
  });

  it("shows admin items when showAdminActions=true", () => {
    render(
      <UserActionsMenu
        user={makeUser()}
        onAssignStore={vi.fn()}
        showAdminActions
      />,
    );
    openMenu();
    expect(
      screen.getByTestId("user-action-assign-store"),
    ).toBeInTheDocument();
  });

  it("never renders a Set password action (endpoint removed in F2.22.2.F)", () => {
    render(
      <UserActionsMenu
        user={makeUser()}
        onAssignStore={vi.fn()}
        showAdminActions
      />,
    );
    openMenu();
    expect(
      screen.queryByTestId("user-action-set-password"),
    ).not.toBeInTheDocument();
    expect(screen.queryByText(/set password/i)).not.toBeInTheDocument();
  });
});

describe("UserActionsMenu - callbacks", () => {
  it("clicking Edit forwards the user", () => {
    const onEdit = vi.fn();
    const user = makeUser();
    render(<UserActionsMenu user={user} onEdit={onEdit} />);
    openMenu();
    fireEvent.click(screen.getByTestId("user-action-edit"));
    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onEdit).toHaveBeenCalledWith(user);
  });

  it("clicking Change role forwards the user", () => {
    const onChangeRole = vi.fn();
    const user = makeUser();
    render(<UserActionsMenu user={user} onChangeRole={onChangeRole} />);
    openMenu();
    fireEvent.click(screen.getByTestId("user-action-change-role"));
    expect(onChangeRole).toHaveBeenCalledWith(user);
  });

  it("clicking Deactivate forwards the active user", () => {
    const onDeactivateReactivate = vi.fn();
    const user = makeUser({ is_active: true });
    render(
      <UserActionsMenu
        user={user}
        onDeactivateReactivate={onDeactivateReactivate}
      />,
    );
    openMenu();
    fireEvent.click(screen.getByTestId("user-action-deactivate"));
    expect(onDeactivateReactivate).toHaveBeenCalledWith(user);
  });

  it("clicking Assign store forwards the user (admin actions visible)", () => {
    const onAssignStore = vi.fn();
    const user = makeUser();
    render(
      <UserActionsMenu
        user={user}
        onAssignStore={onAssignStore}
        showAdminActions
      />,
    );
    openMenu();
    fireEvent.click(screen.getByTestId("user-action-assign-store"));
    expect(onAssignStore).toHaveBeenCalledWith(user);
  });

});

describe("UserActionsMenu - disabled", () => {
  it("disables the trigger when disabled=true", () => {
    render(
      <UserActionsMenu
        user={makeUser()}
        onEdit={vi.fn()}
        disabled
      />,
    );
    expect(screen.getByTestId("user-actions-trigger")).toBeDisabled();
  });
});

describe("UserActionsMenu - permission boundary", () => {
  // The menu must NOT decide for itself which actions are valid for
  // the caller. It only mirrors the callbacks the parent passed in.
  // This test guards against future drift where someone adds a
  // `caller.role`-aware filter.
  it("renders admin-tagged callbacks regardless of the row's role when showAdminActions=true", () => {
    render(
      <UserActionsMenu
        user={makeUser({ role: "admin", store_id: null })}
        onAssignStore={vi.fn()}
        showAdminActions
      />,
    );
    openMenu();
    expect(
      screen.getByTestId("user-action-assign-store"),
    ).toBeInTheDocument();
  });
});
