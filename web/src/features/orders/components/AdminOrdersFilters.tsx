// F2.18.5: controlled filter bar for the admin global orders feed.
//
// Pure controlled component (same shape as AdminInventoryFilters and
// AdminAuditFilters): every field is owned by the parent and
// surfaced back through `onChange` with the next `AdminOrdersFilters`
// snapshot. No fetching, no derived rules, no business logic.
//
// Filter set (exact match to F2.18.2C AdminOrdersFilters type and
// F2.18.1B backend route — no extra fields, no missing fields):
//   - store_id   (admin-only: scope to one store).
//   - status     (OrderStatus enum select).
//   - date_from  (ISO 8601 text, inclusive lower bound on created_at).
//   - date_to    (ISO 8601 text, inclusive upper bound on created_at).
//
// `q` is INTENTIONALLY NOT exposed. F2.18.1B explicitly did not ship
// `q` for `/admin/orders` (the Order model has no clean text-search
// target); adding it here would force a 422 round-trip.
//
// `limit` / `offset` are owned by the parent page and NOT rendered
// here.
//
// Behavior contract:
//   - select "all" removes the corresponding key.
//   - text inputs: trim → empty drops the key; non-empty sets it.
//   - any filter change resets `offset` to 0 if the parent had one;
//     never introduces `offset` when it wasn't there.

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import type { AdminOrdersFilters, OrderStatus } from "../types";

const ALL = "all";

const ORDER_STATUSES: ReadonlyArray<{
  readonly value: OrderStatus;
  readonly label: string;
}> = [
  { value: "pending", label: "Pending" },
  { value: "accepted", label: "Accepted" },
  { value: "preparing", label: "Preparing" },
  { value: "ready", label: "Ready" },
  { value: "out_for_delivery", label: "Out for delivery" },
  { value: "delivered", label: "Delivered" },
  { value: "canceled", label: "Canceled" },
  { value: "returned", label: "Returned" },
];

export interface AdminOrdersFiltersProps {
  filters: AdminOrdersFilters;
  onChange: (next: AdminOrdersFilters) => void;
  disabled?: boolean;
}

function withOffsetReset(next: AdminOrdersFilters): AdminOrdersFilters {
  if (next.offset !== undefined) {
    next.offset = 0;
  }
  return next;
}

function normalizeText(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export function AdminOrdersFilters({
  filters,
  onChange,
  disabled = false,
}: AdminOrdersFiltersProps) {
  const handleStoreIdChange = (value: string) => {
    const next: AdminOrdersFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.store_id;
    } else {
      next.store_id = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleStatusChange = (value: string) => {
    const next: AdminOrdersFilters = { ...filters };
    if (value === ALL) {
      delete next.status;
    } else {
      next.status = value as OrderStatus;
    }
    onChange(withOffsetReset(next));
  };

  const handleDateFromChange = (value: string) => {
    const next: AdminOrdersFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.date_from;
    } else {
      next.date_from = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleDateToChange = (value: string) => {
    const next: AdminOrdersFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.date_to;
    } else {
      next.date_to = normalized;
    }
    onChange(withOffsetReset(next));
  };

  return (
    <div
      className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 md:items-end"
      data-testid="admin-orders-filters"
    >
      <div className="space-y-2">
        <Label htmlFor="admin-orders-filter-store-id">Store</Label>
        <Input
          id="admin-orders-filter-store-id"
          type="text"
          placeholder="Store UUID (optional)"
          value={filters.store_id ?? ""}
          disabled={disabled}
          onChange={(e) => handleStoreIdChange(e.target.value)}
          data-testid="admin-orders-filter-store-id"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-orders-filter-status">Status</Label>
        <Select
          value={filters.status ?? ALL}
          disabled={disabled}
          onValueChange={handleStatusChange}
        >
          <SelectTrigger
            id="admin-orders-filter-status"
            data-testid="admin-orders-filter-status-trigger"
          >
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All statuses</SelectItem>
            {ORDER_STATUSES.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-orders-filter-date-from">From</Label>
        <Input
          id="admin-orders-filter-date-from"
          type="text"
          placeholder="YYYY-MM-DD or ISO 8601"
          value={filters.date_from ?? ""}
          disabled={disabled}
          onChange={(e) => handleDateFromChange(e.target.value)}
          data-testid="admin-orders-filter-date-from"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-orders-filter-date-to">To</Label>
        <Input
          id="admin-orders-filter-date-to"
          type="text"
          placeholder="YYYY-MM-DD or ISO 8601"
          value={filters.date_to ?? ""}
          disabled={disabled}
          onChange={(e) => handleDateToChange(e.target.value)}
          data-testid="admin-orders-filter-date-to"
        />
      </div>
    </div>
  );
}
