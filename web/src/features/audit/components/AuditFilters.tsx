// F2.16.5: controlled filter bar for the unified store audit feed.
//
// Pure controlled component (same shape as features/users/components
// /UsersFilters): every field is owned by the parent and surfaced
// back through `onChange` with the next `StoreAuditFilters`
// snapshot. No fetching, no derived rules, no business logic.
//
// Behavior contract:
//   - source select: "all" removes `source`; any other value sets it.
//   - action input: trim → empty drops `action`; non-empty sets it.
//   - actor_id input: trim → empty drops `actor_id`; non-empty sets.
//   - date_from / date_to inputs: trim → empty drops the field;
//     non-empty sets it verbatim (backend parses ISO 8601).
//   - `limit` is preserved verbatim. The component never invents a
//     default — pagination semantics belong to the parent.
//   - `offset`: if the parent had paged in (`offset !== undefined`),
//     any filter change resets it to 0 because the new filter could
//     shrink the dataset and leave the page out of bounds. If the
//     parent never set `offset`, the next snapshot also omits it
//     (no spurious key introduction).

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import type { AuditSource, StoreAuditFilters } from "../types";

const ALL = "all";

const SOURCE_OPTIONS: ReadonlyArray<{
  readonly value: AuditSource;
  readonly label: string;
}> = [
  { value: "inventory", label: "Inventory" },
  { value: "order", label: "Order" },
  { value: "product_compliance", label: "Compliance" },
];

export interface AuditFiltersProps {
  filters: StoreAuditFilters;
  onChange: (next: StoreAuditFilters) => void;
  disabled?: boolean;
}

/**
 * Reset offset to 0 if the parent had one. Never introduce offset
 * when it wasn't there — the parent owns pagination semantics.
 */
function withOffsetReset(next: StoreAuditFilters): StoreAuditFilters {
  if (next.offset !== undefined) {
    next.offset = 0;
  }
  return next;
}

/**
 * Trim a text value; return undefined for empty/whitespace. Mirrors
 * the API layer's `trimOrUndefined` so the wire and the filter
 * snapshot agree.
 */
function normalizeText(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export function AuditFilters({
  filters,
  onChange,
  disabled = false,
}: AuditFiltersProps) {
  const handleSourceChange = (value: string) => {
    const next: StoreAuditFilters = { ...filters };
    if (value === ALL) {
      delete next.source;
    } else {
      next.source = value as AuditSource;
    }
    onChange(withOffsetReset(next));
  };

  const handleActionChange = (value: string) => {
    const next: StoreAuditFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.action;
    } else {
      next.action = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleActorIdChange = (value: string) => {
    const next: StoreAuditFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.actor_id;
    } else {
      next.actor_id = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleDateFromChange = (value: string) => {
    const next: StoreAuditFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.date_from;
    } else {
      next.date_from = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleDateToChange = (value: string) => {
    const next: StoreAuditFilters = { ...filters };
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
      className="grid gap-4 md:grid-cols-[minmax(8rem,12rem)_minmax(8rem,14rem)_minmax(10rem,16rem)_minmax(10rem,14rem)_minmax(10rem,14rem)] md:items-end"
      data-testid="audit-filters"
    >
      <div className="space-y-2">
        <Label htmlFor="audit-filter-source">Source</Label>
        <Select
          value={filters.source ?? ALL}
          disabled={disabled}
          onValueChange={handleSourceChange}
        >
          <SelectTrigger
            id="audit-filter-source"
            data-testid="audit-filter-source-trigger"
          >
            <SelectValue placeholder="All sources" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All sources</SelectItem>
            {SOURCE_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="audit-filter-action">Action</Label>
        <Input
          id="audit-filter-action"
          type="text"
          placeholder="e.g. receipt, status_changed"
          value={filters.action ?? ""}
          disabled={disabled}
          onChange={(e) => handleActionChange(e.target.value)}
          data-testid="audit-filter-action"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="audit-filter-actor-id">Actor</Label>
        <Input
          id="audit-filter-actor-id"
          type="text"
          placeholder="Actor UUID"
          value={filters.actor_id ?? ""}
          disabled={disabled}
          onChange={(e) => handleActorIdChange(e.target.value)}
          data-testid="audit-filter-actor-id"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="audit-filter-date-from">From</Label>
        <Input
          id="audit-filter-date-from"
          type="text"
          placeholder="YYYY-MM-DD or ISO 8601"
          value={filters.date_from ?? ""}
          disabled={disabled}
          onChange={(e) => handleDateFromChange(e.target.value)}
          data-testid="audit-filter-date-from"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="audit-filter-date-to">To</Label>
        <Input
          id="audit-filter-date-to"
          type="text"
          placeholder="YYYY-MM-DD or ISO 8601"
          value={filters.date_to ?? ""}
          disabled={disabled}
          onChange={(e) => handleDateToChange(e.target.value)}
          data-testid="audit-filter-date-to"
        />
      </div>
    </div>
  );
}
