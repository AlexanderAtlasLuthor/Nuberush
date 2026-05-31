// F2.24.C7: store-applications filter bar (status + search).
//
// Pure controlled component. The page owns the filter state; this just
// renders inputs and calls `onChange` with the next filter set. No query
// logic, no debouncing (the query hook handles refetch timing).
//
// Status uses the shared Radix Select; search uses the shared Input.
// Selecting a status (or clearing it via "All") resets nothing else —
// the page resets pagination on filter change.
//
// Testability note (mirrors features/admin-products AdminProductsFilters):
// Radix Select renders its listbox in a portal that jsdom can't drive
// reliably, so we ALSO render a visually-hidden native <select> wired to
// the same handler. Production shows the styled Radix control; tests
// drive the native one. Both call the same handler so behavior can't
// drift.

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import type {
  StoreApplicationListFilters,
  StoreApplicationStatus,
} from "../types";

export interface StoreApplicationsFiltersProps {
  filters: StoreApplicationListFilters;
  onChange: (next: StoreApplicationListFilters) => void;
  disabled?: boolean;
}

const STATUS_ALL = "all";

const STATUS_OPTIONS: ReadonlyArray<{
  value: string;
  label: string;
}> = [
  { value: STATUS_ALL, label: "All statuses" },
  { value: "pending_review", label: "Pending review" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
  { value: "submitted", label: "Submitted" },
  { value: "draft", label: "Draft" },
];

function statusValue(filters: StoreApplicationListFilters): string {
  return filters.status ?? STATUS_ALL;
}

export function StoreApplicationsFilters({
  filters,
  onChange,
  disabled = false,
}: StoreApplicationsFiltersProps) {
  const handleStatusChange = (value: string) => {
    const next: StoreApplicationListFilters = { ...filters };
    if (value === STATUS_ALL) {
      delete next.status;
    } else {
      next.status = value as StoreApplicationStatus;
    }
    onChange(next);
  };

  const handleSearchChange = (
    event: React.ChangeEvent<HTMLInputElement>,
  ) => {
    const next: StoreApplicationListFilters = { ...filters };
    const value = event.target.value;
    if (value.length > 0) next.q = value;
    else delete next.q;
    onChange(next);
  };

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-end">
      <div className="flex-1 space-y-2">
        <Label htmlFor="store-applications-search">Search</Label>
        <Input
          id="store-applications-search"
          type="search"
          placeholder="Search by business, owner, or email"
          value={filters.q ?? ""}
          onChange={handleSearchChange}
          disabled={disabled}
          data-testid="store-applications-search"
        />
      </div>
      <div className="w-full space-y-2 sm:w-56">
        <Label htmlFor="store-applications-status">Status</Label>
        <Select
          value={statusValue(filters)}
          onValueChange={handleStatusChange}
          disabled={disabled}
        >
          <SelectTrigger
            id="store-applications-status"
            data-testid="store-applications-status"
          >
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            {STATUS_OPTIONS.map((option) => (
              <SelectItem key={option.value} value={option.value}>
                {option.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        {/* Deterministic, accessible fallback for tests + no-JS. The
            Radix listbox renders in a portal that jsdom can't drive
            reliably; this native select shares the same handler. */}
        <select
          aria-hidden="true"
          tabIndex={-1}
          className="sr-only"
          value={statusValue(filters)}
          disabled={disabled}
          onChange={(event) => handleStatusChange(event.target.value)}
          data-testid="store-applications-status-native"
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
