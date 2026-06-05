// F2.18.4: controlled filter bar for the admin global audit feed.
//
// Pure controlled component (same shape as AuditFilters, but typed
// against the admin filter envelope from F2.18.2B). Every field is
// owned by the parent and surfaced back through `onChange` with the
// next `AdminAuditFilters` snapshot. No fetching, no derived rules,
// no business logic.
//
// Filter set (exact match to the F2.18.2B AdminAuditFilters type and
// the F2.17.5 backend route — no extra fields, no missing fields):
//   - store_id   (admin-only: scope the global feed to one store).
//   - source     (audit source enum select).
//   - entity_type (audit entity-type enum select).
//   - action     (free-text).
//   - actor_id   (UUID text).
//   - date_from / date_to (ISO 8601 text).
//   - limit / offset are owned by the parent page and are NOT
//     rendered here.
//
// Behavior contract (mirrors AuditFilters):
//   - select "all" removes the corresponding key.
//   - text inputs: trim → empty drops the key; non-empty sets it.
//   - any filter change resets `offset` to 0 if the parent had one;
//     never introduces `offset` when it wasn't there.
//
// Why a separate component (not a generalised `AuditFilters`):
//   - Existing `AuditFilters` is typed against `StoreAuditFilters`
//     (no `store_id`, no `entity_type`). Generalising it to a union
//     would either weaken the type or force every store-scoped caller
//     to pass extra props. Splitting keeps both surfaces clean.

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
  AdminAuditFilters as AdminAuditFiltersType,
  AuditEntityType,
  AuditSource,
} from "../types";

const ALL = "all";

const SOURCE_OPTIONS: ReadonlyArray<{
  readonly value: AuditSource;
  readonly label: string;
}> = [
  { value: "inventory", label: "Inventory" },
  { value: "order", label: "Order" },
  { value: "product_compliance", label: "Compliance" },
];

const ENTITY_OPTIONS: ReadonlyArray<{
  readonly value: AuditEntityType;
  readonly label: string;
}> = [
  { value: "inventory_item", label: "Inventory item" },
  { value: "order", label: "Order" },
  { value: "product", label: "Product" },
];

export interface AdminAuditFiltersProps {
  filters: AdminAuditFiltersType;
  onChange: (next: AdminAuditFiltersType) => void;
  disabled?: boolean;
}

/**
 * Reset offset to 0 if the parent had one. Never introduce offset
 * when it wasn't there — the parent owns pagination semantics.
 */
function withOffsetReset(
  next: AdminAuditFiltersType,
): AdminAuditFiltersType {
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

export function AdminAuditFilters({
  filters,
  onChange,
  disabled = false,
}: AdminAuditFiltersProps) {
  const handleStoreIdChange = (value: string) => {
    const next: AdminAuditFiltersType = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.store_id;
    } else {
      next.store_id = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleSourceChange = (value: string) => {
    const next: AdminAuditFiltersType = { ...filters };
    if (value === ALL) {
      delete next.source;
    } else {
      next.source = value as AuditSource;
    }
    onChange(withOffsetReset(next));
  };

  const handleEntityTypeChange = (value: string) => {
    const next: AdminAuditFiltersType = { ...filters };
    if (value === ALL) {
      delete next.entity_type;
    } else {
      next.entity_type = value as AuditEntityType;
    }
    onChange(withOffsetReset(next));
  };

  const handleActionChange = (value: string) => {
    const next: AdminAuditFiltersType = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.action;
    } else {
      next.action = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleActorIdChange = (value: string) => {
    const next: AdminAuditFiltersType = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.actor_id;
    } else {
      next.actor_id = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleDateFromChange = (value: string) => {
    const next: AdminAuditFiltersType = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.date_from;
    } else {
      next.date_from = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleDateToChange = (value: string) => {
    const next: AdminAuditFiltersType = { ...filters };
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
      data-testid="admin-audit-filters"
    >
      <div className="space-y-2">
        <Label htmlFor="admin-audit-filter-store-id">Store</Label>
        <Input
          id="admin-audit-filter-store-id"
          type="text"
          placeholder="Filter by store ID (optional)"
          value={filters.store_id ?? ""}
          disabled={disabled}
          onChange={(e) => handleStoreIdChange(e.target.value)}
          data-testid="admin-audit-filter-store-id"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-audit-filter-source">Source</Label>
        <Select
          value={filters.source ?? ALL}
          disabled={disabled}
          onValueChange={handleSourceChange}
        >
          <SelectTrigger
            id="admin-audit-filter-source"
            data-testid="admin-audit-filter-source-trigger"
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
        <Label htmlFor="admin-audit-filter-entity-type">Entity</Label>
        <Select
          value={filters.entity_type ?? ALL}
          disabled={disabled}
          onValueChange={handleEntityTypeChange}
        >
          <SelectTrigger
            id="admin-audit-filter-entity-type"
            data-testid="admin-audit-filter-entity-type-trigger"
          >
            <SelectValue placeholder="All entities" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All entities</SelectItem>
            {ENTITY_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-audit-filter-action">Action</Label>
        <Input
          id="admin-audit-filter-action"
          type="text"
          placeholder="e.g. receipt, status_changed"
          value={filters.action ?? ""}
          disabled={disabled}
          onChange={(e) => handleActionChange(e.target.value)}
          data-testid="admin-audit-filter-action"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-audit-filter-actor-id">Actor</Label>
        <Input
          id="admin-audit-filter-actor-id"
          type="text"
          placeholder="Actor ID"
          value={filters.actor_id ?? ""}
          disabled={disabled}
          onChange={(e) => handleActorIdChange(e.target.value)}
          data-testid="admin-audit-filter-actor-id"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-audit-filter-date-from">From</Label>
        <Input
          id="admin-audit-filter-date-from"
          type="text"
          placeholder="YYYY-MM-DD or ISO 8601"
          value={filters.date_from ?? ""}
          disabled={disabled}
          onChange={(e) => handleDateFromChange(e.target.value)}
          data-testid="admin-audit-filter-date-from"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-audit-filter-date-to">To</Label>
        <Input
          id="admin-audit-filter-date-to"
          type="text"
          placeholder="YYYY-MM-DD or ISO 8601"
          value={filters.date_to ?? ""}
          disabled={disabled}
          onChange={(e) => handleDateToChange(e.target.value)}
          data-testid="admin-audit-filter-date-to"
        />
      </div>
    </div>
  );
}
