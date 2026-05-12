// F2.15.5: UserStatusBadge tests.
//
// Two states only — `isActive` boolean projection. Mirrors the
// shape of features/products/__tests__/ProductStatusBadge tests
// implicitly.

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { UserStatusBadge } from "../UserStatusBadge";

describe("UserStatusBadge", () => {
  it("renders 'Active' when isActive is true", () => {
    render(<UserStatusBadge isActive />);
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByTestId("user-status-active")).toBeInTheDocument();
  });

  it("renders 'Inactive' when isActive is false", () => {
    render(<UserStatusBadge isActive={false} />);
    expect(screen.getByText("Inactive")).toBeInTheDocument();
    expect(screen.getByTestId("user-status-inactive")).toBeInTheDocument();
  });

  it("applies the className override when provided", () => {
    const { container } = render(
      <UserStatusBadge isActive className="custom-status" />,
    );
    expect(container.querySelector(".custom-status")).not.toBeNull();
  });
});
