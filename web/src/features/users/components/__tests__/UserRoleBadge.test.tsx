// F2.15.5: UserRoleBadge tests.
//
// Pure presentational component — render each of the 5 roles and
// assert the visible label + accessible name. No mocks, no
// QueryClient.

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { UserRoleBadge } from "../UserRoleBadge";
import type { UserRole } from "../../types";

describe("UserRoleBadge", () => {
  it.each([
    ["admin", "Admin"],
    ["owner", "Owner"],
    ["manager", "Manager"],
    ["staff", "Staff"],
    ["driver", "Driver"],
  ] as const)("renders the human label for %s", (role, label) => {
    render(<UserRoleBadge role={role as UserRole} />);
    expect(screen.getByText(label)).toBeInTheDocument();
    expect(screen.getByLabelText(`Role: ${label}`)).toBeInTheDocument();
  });

  it("tags the rendered badge with a role-specific data-testid", () => {
    render(<UserRoleBadge role="manager" />);
    expect(
      screen.getByTestId("user-role-badge-manager"),
    ).toBeInTheDocument();
  });

  it("applies the className override when provided", () => {
    const { container } = render(
      <UserRoleBadge role="staff" className="custom-class" />,
    );
    const node = container.querySelector(".custom-class");
    expect(node).not.toBeNull();
  });
});
