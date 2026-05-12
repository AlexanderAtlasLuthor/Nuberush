// F2.15.5: UsersFilters tests.
//
// Drives the controlled component through user-event and asserts the
// `onChange` snapshots against the documented behavior. We treat the
// Radix `Select` triggers as the canonical way to switch values to
// match the patterns in features/products / features/inventory.

import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";

import { UsersFilters } from "../UsersFilters";
import type { UserListFilters } from "../../types";

const STORE_ID = "44444444-4444-4444-4444-444444444444";

describe("UsersFilters - search (q)", () => {
  it("renders the search input", () => {
    render(<UsersFilters filters={{}} onChange={() => {}} />);
    expect(screen.getByTestId("users-filter-q")).toBeInTheDocument();
  });

  it("emits q when typed", () => {
    const onChange = vi.fn();
    render(<UsersFilters filters={{}} onChange={onChange} />);
    fireEvent.change(screen.getByTestId("users-filter-q"), {
      target: { value: "alice" },
    });
    expect(onChange).toHaveBeenCalledWith({ q: "alice" });
  });

  it("removes q when cleared", () => {
    const onChange = vi.fn();
    render(
      <UsersFilters filters={{ q: "alice" }} onChange={onChange} />,
    );
    fireEvent.change(screen.getByTestId("users-filter-q"), {
      target: { value: "" },
    });
    const next = onChange.mock.calls[0][0] as UserListFilters;
    expect(next).not.toHaveProperty("q");
  });
});

describe("UsersFilters - role", () => {
  it("setting role 'manager' emits role: manager", () => {
    const onChange = vi.fn();
    render(<UsersFilters filters={{}} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("users-filter-role-trigger"));
    fireEvent.click(screen.getByRole("option", { name: "Manager" }));
    expect(onChange).toHaveBeenCalledWith({ role: "manager" });
  });

  it("setting role 'all' removes role from filters", () => {
    const onChange = vi.fn();
    render(
      <UsersFilters
        filters={{ role: "manager" }}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByTestId("users-filter-role-trigger"));
    fireEvent.click(screen.getByRole("option", { name: "All roles" }));
    const next = onChange.mock.calls[0][0] as UserListFilters;
    expect(next).not.toHaveProperty("role");
  });
});

describe("UsersFilters - status / is_active", () => {
  it("Active sets is_active=true", () => {
    const onChange = vi.fn();
    render(<UsersFilters filters={{}} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("users-filter-status-trigger"));
    fireEvent.click(screen.getByRole("option", { name: "Active" }));
    expect(onChange).toHaveBeenCalledWith({ is_active: true });
  });

  it("Inactive sets is_active=false (a meaningful explicit false)", () => {
    const onChange = vi.fn();
    render(<UsersFilters filters={{}} onChange={onChange} />);
    fireEvent.click(screen.getByTestId("users-filter-status-trigger"));
    fireEvent.click(screen.getByRole("option", { name: "Inactive" }));
    expect(onChange).toHaveBeenCalledWith({ is_active: false });
  });

  it("'All' removes is_active from filters", () => {
    const onChange = vi.fn();
    render(
      <UsersFilters
        filters={{ is_active: true }}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByTestId("users-filter-status-trigger"));
    // The status select also has an "All" option; scope to its
    // listbox to avoid clashing with the role select's "All roles".
    const listbox = screen.getByRole("listbox");
    fireEvent.click(within(listbox).getByRole("option", { name: "All" }));
    const next = onChange.mock.calls[0][0] as UserListFilters;
    expect(next).not.toHaveProperty("is_active");
  });
});

describe("UsersFilters - store filter visibility", () => {
  it("does not render the store_id input when showStoreFilter=false", () => {
    render(<UsersFilters filters={{}} onChange={() => {}} />);
    expect(
      screen.queryByTestId("users-filter-store-id"),
    ).not.toBeInTheDocument();
  });

  it("renders the store_id input when showStoreFilter=true", () => {
    render(
      <UsersFilters filters={{}} onChange={() => {}} showStoreFilter />,
    );
    expect(
      screen.getByTestId("users-filter-store-id"),
    ).toBeInTheDocument();
  });

  it("emits store_id when typed", () => {
    const onChange = vi.fn();
    render(
      <UsersFilters
        filters={{}}
        onChange={onChange}
        showStoreFilter
      />,
    );
    fireEvent.change(screen.getByTestId("users-filter-store-id"), {
      target: { value: STORE_ID },
    });
    expect(onChange).toHaveBeenCalledWith({ store_id: STORE_ID });
  });

  it("removes store_id when cleared", () => {
    const onChange = vi.fn();
    render(
      <UsersFilters
        filters={{ store_id: STORE_ID }}
        onChange={onChange}
        showStoreFilter
      />,
    );
    fireEvent.change(screen.getByTestId("users-filter-store-id"), {
      target: { value: "" },
    });
    const next = onChange.mock.calls[0][0] as UserListFilters;
    expect(next).not.toHaveProperty("store_id");
  });
});

describe("UsersFilters - preserve / reset semantics", () => {
  it("preserves limit when changing q", () => {
    const onChange = vi.fn();
    render(
      <UsersFilters
        filters={{ limit: 50 }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("users-filter-q"), {
      target: { value: "bob" },
    });
    const next = onChange.mock.calls[0][0] as UserListFilters;
    expect(next.limit).toBe(50);
    expect(next.q).toBe("bob");
  });

  it("resets offset to 0 when changing q if offset was set", () => {
    const onChange = vi.fn();
    render(
      <UsersFilters
        filters={{ limit: 25, offset: 75 }}
        onChange={onChange}
      />,
    );
    fireEvent.change(screen.getByTestId("users-filter-q"), {
      target: { value: "bob" },
    });
    const next = onChange.mock.calls[0][0] as UserListFilters;
    expect(next.offset).toBe(0);
    expect(next.limit).toBe(25);
  });

  it("does not introduce offset when none was set", () => {
    const onChange = vi.fn();
    render(<UsersFilters filters={{}} onChange={onChange} />);
    fireEvent.change(screen.getByTestId("users-filter-q"), {
      target: { value: "bob" },
    });
    const next = onChange.mock.calls[0][0] as UserListFilters;
    expect(next).not.toHaveProperty("offset");
  });

  it("resets offset to 0 when changing role", () => {
    const onChange = vi.fn();
    render(
      <UsersFilters
        filters={{ offset: 30 }}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByTestId("users-filter-role-trigger"));
    fireEvent.click(screen.getByRole("option", { name: "Staff" }));
    const next = onChange.mock.calls[0][0] as UserListFilters;
    expect(next.offset).toBe(0);
    expect(next.role).toBe("staff");
  });
});

describe("UsersFilters - disabled", () => {
  it("disables every control when disabled=true", () => {
    render(
      <UsersFilters
        filters={{}}
        onChange={() => {}}
        showStoreFilter
        disabled
      />,
    );
    expect(screen.getByTestId("users-filter-q")).toBeDisabled();
    expect(
      screen.getByTestId("users-filter-role-trigger"),
    ).toBeDisabled();
    expect(
      screen.getByTestId("users-filter-status-trigger"),
    ).toBeDisabled();
    expect(
      screen.getByTestId("users-filter-store-id"),
    ).toBeDisabled();
  });
});
