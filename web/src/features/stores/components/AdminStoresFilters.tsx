// F2.18.3: filter bar for the admin stores list page.
//
// Pure controlled component. Every field is owned by the parent's
// state and surfaced back through `onChange` with the next snapshot.
// No fetching, no derived rules, no business logic; the parent passes
// the resulting filters to `useAdminStoresQuery` verbatim.
//
// Behavior contract (mirrors features/users UsersFilters):
//   - search input: emits `q` when non-empty; removes it when empty
//     so the query param drops off the wire (matches `listStores`
//     which only forwards `q` when length > 0).
//   - status select: "all" removes `is_active`; "active" sets true;
//     "inactive" sets false. Explicit false is meaningful — backend
//     surfaces deactivated stores only.
//   - any field change resets `offset` to 0 if the parent had paged
//     into the list, matching the convention in features/users.
//   - `limit` is preserved verbatim; the parent owns pagination.

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { StoreListFilters } from "../types";

const ALL = "all";
const ACTIVE = "active";
const INACTIVE = "inactive";

interface AdminStoresFiltersProps {
  filters: StoreListFilters;
  onChange: (next: StoreListFilters) => void;
  disabled?: boolean;
}

function statusValueOf(filters: StoreListFilters): string {
  if (filters.is_active === true) return ACTIVE;
  if (filters.is_active === false) return INACTIVE;
  return ALL;
}

export function AdminStoresFilters({
  filters,
  onChange,
  disabled = false,
}: AdminStoresFiltersProps) {
  const handleSearchChange = (value: string) => {
    const next: StoreListFilters = { ...filters };
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

  const handleStatusChange = (value: string) => {
    const next: StoreListFilters = { ...filters };
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

  return (
    <div className="grid gap-4 md:grid-cols-[minmax(12rem,20rem)_minmax(8rem,12rem)] md:items-end">
      <div className="space-y-2">
        <Label htmlFor="admin-stores-filter-q">Search</Label>
        <Input
          id="admin-stores-filter-q"
          type="search"
          placeholder="Search by name or code"
          value={filters.q ?? ""}
          disabled={disabled}
          onChange={(e) => handleSearchChange(e.target.value)}
          data-testid="admin-stores-filter-q"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-stores-filter-status">Status</Label>
        <Select
          value={statusValueOf(filters)}
          disabled={disabled}
          onValueChange={handleStatusChange}
        >
          <SelectTrigger
            id="admin-stores-filter-status"
            data-testid="admin-stores-filter-status-trigger"
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
    </div>
  );
}
