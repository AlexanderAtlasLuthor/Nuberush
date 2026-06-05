// F2.15.5: filter bar for the users list page.
//
// Pure controlled component. Every field is owned by the parent's
// state and surfaced back through `onChange` with the next snapshot.
// No fetching, no derived rules, no business logic; the parent passes
// the resulting filters to `useUsersQuery` verbatim.
//
// Behavior contract:
//   - search input: emits `q` when non-empty; removes it when empty
//     so the query param drops off the wire (matches `listUsers`).
//   - role select: "all" removes `role`; any other value sets it.
//   - status select: "all" removes `is_active`; "active" sets true;
//     "inactive" sets false.
//   - store_id input (optional): mirrors search behavior.
//   - any field change resets `offset` to 0 if the parent had paged
//     into the list — the new filter could shrink the dataset and
//     leave the page out of bounds, so the convention here matches
//     features/products / features/inventory.
//   - `limit` is preserved verbatim; we never invent a default for
//     it because the parent owns pagination semantics.

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { UserListFilters, UserRole } from "../types";

const ALL = "all";
const ACTIVE = "active";
const INACTIVE = "inactive";

const ROLE_OPTIONS: ReadonlyArray<{
  readonly value: UserRole;
  readonly label: string;
}> = [
  { value: "admin", label: "Admin" },
  { value: "owner", label: "Owner" },
  { value: "manager", label: "Manager" },
  { value: "staff", label: "Staff" },
  { value: "driver", label: "Driver" },
];

interface UsersFiltersProps {
  filters: UserListFilters;
  onChange: (next: UserListFilters) => void;
  /**
   * When true, expose the `store_id` text input. Defaults to false
   * because owners/managers are forced to their own store server-side
   * and never need this control; admins managing the global users
   * surface do.
   */
  showStoreFilter?: boolean;
  disabled?: boolean;
}

function statusValueOf(filters: UserListFilters): string {
  if (filters.is_active === true) return ACTIVE;
  if (filters.is_active === false) return INACTIVE;
  return ALL;
}

export function UsersFilters({
  filters,
  onChange,
  showStoreFilter = false,
  disabled = false,
}: UsersFiltersProps) {
  const handleSearchChange = (value: string) => {
    const next: UserListFilters = { ...filters };
    if (value.length === 0) {
      delete next.q;
    } else {
      next.q = value;
    }
    if (filters.offset !== undefined) {
      next.offset = 0;
    }
    onChange(next);
  };

  const handleRoleChange = (value: string) => {
    const next: UserListFilters = { ...filters };
    if (value === ALL) {
      delete next.role;
    } else {
      next.role = value as UserRole;
    }
    if (filters.offset !== undefined) {
      next.offset = 0;
    }
    onChange(next);
  };

  const handleStatusChange = (value: string) => {
    const next: UserListFilters = { ...filters };
    if (value === ACTIVE) {
      next.is_active = true;
    } else if (value === INACTIVE) {
      next.is_active = false;
    } else {
      delete next.is_active;
    }
    if (filters.offset !== undefined) {
      next.offset = 0;
    }
    onChange(next);
  };

  const handleStoreIdChange = (value: string) => {
    const next: UserListFilters = { ...filters };
    if (value.length === 0) {
      delete next.store_id;
    } else {
      next.store_id = value;
    }
    if (filters.offset !== undefined) {
      next.offset = 0;
    }
    onChange(next);
  };

  // Note: each handler builds the next snapshot inline so the full
  // payload is visible at the call site; the helper would obscure it.

  return (
    <div className="grid gap-4 md:grid-cols-[minmax(12rem,20rem)_minmax(8rem,12rem)_minmax(8rem,12rem)_minmax(0,1fr)] md:items-end">
      <div className="space-y-2">
        <Label htmlFor="users-filter-q">Search</Label>
        <Input
          id="users-filter-q"
          type="search"
          placeholder="Search name, email or phone"
          value={filters.q ?? ""}
          disabled={disabled}
          onChange={(e) => handleSearchChange(e.target.value)}
          data-testid="users-filter-q"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="users-filter-role">Role</Label>
        <Select
          value={filters.role ?? ALL}
          disabled={disabled}
          onValueChange={handleRoleChange}
        >
          <SelectTrigger
            id="users-filter-role"
            data-testid="users-filter-role-trigger"
          >
            <SelectValue placeholder="All roles" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All roles</SelectItem>
            {ROLE_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="users-filter-status">Status</Label>
        <Select
          value={statusValueOf(filters)}
          disabled={disabled}
          onValueChange={handleStatusChange}
        >
          <SelectTrigger
            id="users-filter-status"
            data-testid="users-filter-status-trigger"
          >
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All</SelectItem>
            <SelectItem value={ACTIVE}>Active</SelectItem>
            <SelectItem value={INACTIVE}>Inactive</SelectItem>
          </SelectContent>
        </Select>
      </div>

      {showStoreFilter ? (
        <div className="space-y-2">
          <Label htmlFor="users-filter-store-id">Store ID</Label>
          <Input
            id="users-filter-store-id"
            type="text"
            placeholder="Filter by store ID"
            value={filters.store_id ?? ""}
            disabled={disabled}
            onChange={(e) => handleStoreIdChange(e.target.value)}
            data-testid="users-filter-store-id"
          />
        </div>
      ) : null}
    </div>
  );
}
