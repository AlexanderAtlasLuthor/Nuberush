// F2.19.6: controlled filter bar for the admin operations alerts feed.
//
// Pure controlled component (same shape as features/inventory
// AdminInventoryFilters): every field is owned by the parent and
// surfaced back through `onChange` with the next
// `AdminOperationsAlertsFilters` snapshot. No fetching, no derived
// rules, no business logic.
//
// Filter set (exact match to F2.19.0 §3.2.1 contract and the
// F2.19.2 backend route — no extra fields, no missing fields):
//   - category       (5-value enum select)
//   - severity       (3-value enum select)
//   - store_id       (free text UUID; trim + drop empty)
//   - aging_minutes  (numeric input; min=1; default=1440)
//
// `limit` / `offset` are owned by the parent page and NOT rendered
// here.
//
// Behavior contract (mirrors AdminInventoryFilters):
//   - select "all" removes the corresponding key.
//   - text inputs: trim → empty drops the key; non-empty sets it.
//   - any filter change resets `offset` to 0 if the parent had one.
//   - reset button restores the parent's "default" snapshot through
//     `onReset`.

import { Button } from "@/components/ui/button";
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
  AdminOperationsAlertCategory,
  AdminOperationsAlertSeverity,
  AdminOperationsAlertsFilters,
} from "../types";

const ALL = "all";

const CATEGORY_OPTIONS: ReadonlyArray<{
  readonly value: AdminOperationsAlertCategory;
  readonly label: string;
}> = [
  { value: "low_stock", label: "Low stock" },
  { value: "aging_order", label: "Aging order" },
  { value: "compliance_blocker", label: "Compliance blocker" },
  { value: "inactive_store", label: "Inactive store" },
  { value: "store_no_inventory", label: "Store has no inventory" },
];

const SEVERITY_OPTIONS: ReadonlyArray<{
  readonly value: AdminOperationsAlertSeverity;
  readonly label: string;
}> = [
  { value: "high", label: "High" },
  { value: "medium", label: "Medium" },
  { value: "low", label: "Low" },
];

export interface AdminOperationsFiltersProps {
  filters: AdminOperationsAlertsFilters;
  onChange: (next: AdminOperationsAlertsFilters) => void;
  onReset: () => void;
  disabled?: boolean;
}

function withOffsetReset(
  next: AdminOperationsAlertsFilters,
): AdminOperationsAlertsFilters {
  if (next.offset !== undefined) {
    next.offset = 0;
  }
  return next;
}

function normalizeText(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export function AdminOperationsFilters({
  filters,
  onChange,
  onReset,
  disabled = false,
}: AdminOperationsFiltersProps) {
  const handleCategoryChange = (value: string) => {
    const next: AdminOperationsAlertsFilters = { ...filters };
    if (value === ALL) {
      delete next.category;
    } else {
      next.category = value as AdminOperationsAlertCategory;
    }
    onChange(withOffsetReset(next));
  };

  const handleSeverityChange = (value: string) => {
    const next: AdminOperationsAlertsFilters = { ...filters };
    if (value === ALL) {
      delete next.severity;
    } else {
      next.severity = value as AdminOperationsAlertSeverity;
    }
    onChange(withOffsetReset(next));
  };

  const handleStoreIdChange = (value: string) => {
    const next: AdminOperationsAlertsFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.store_id;
    } else {
      next.store_id = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleAgingMinutesChange = (value: string) => {
    const next: AdminOperationsAlertsFilters = { ...filters };
    // Empty input drops the key so the backend default (1440) wins
    // server-side. A non-numeric / NaN value is also dropped — the
    // page passes the user's intent only when it parses to a finite
    // number. Negative / zero values are forwarded so the backend
    // can 422 them via `Query(ge=1)` rather than the frontend
    // silently coercing them to the default.
    const trimmed = value.trim();
    if (trimmed.length === 0) {
      delete next.aging_minutes;
    } else {
      const parsed = Number(trimmed);
      if (Number.isFinite(parsed)) {
        next.aging_minutes = parsed;
      } else {
        delete next.aging_minutes;
      }
    }
    onChange(withOffsetReset(next));
  };

  return (
    <div
      className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 md:items-end"
      data-testid="admin-operations-filters"
    >
      <div className="space-y-2">
        <Label htmlFor="admin-operations-filter-category">Category</Label>
        <Select
          value={filters.category ?? ALL}
          disabled={disabled}
          onValueChange={handleCategoryChange}
        >
          <SelectTrigger
            id="admin-operations-filter-category"
            data-testid="admin-operations-filter-category-trigger"
          >
            <SelectValue placeholder="All categories" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All categories</SelectItem>
            {CATEGORY_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-operations-filter-severity">Severity</Label>
        <Select
          value={filters.severity ?? ALL}
          disabled={disabled}
          onValueChange={handleSeverityChange}
        >
          <SelectTrigger
            id="admin-operations-filter-severity"
            data-testid="admin-operations-filter-severity-trigger"
          >
            <SelectValue placeholder="All severities" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All severities</SelectItem>
            {SEVERITY_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-operations-filter-store-id">Store</Label>
        <Input
          id="admin-operations-filter-store-id"
          type="text"
          placeholder="Filter by store ID (optional)"
          value={filters.store_id ?? ""}
          disabled={disabled}
          onChange={(e) => handleStoreIdChange(e.target.value)}
          data-testid="admin-operations-filter-store-id"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-operations-filter-aging-minutes">
          Aging threshold (minutes)
        </Label>
        <div className="flex items-center gap-2">
          <Input
            id="admin-operations-filter-aging-minutes"
            type="number"
            min={1}
            placeholder="1440"
            value={
              filters.aging_minutes === undefined
                ? ""
                : String(filters.aging_minutes)
            }
            disabled={disabled}
            onChange={(e) => handleAgingMinutesChange(e.target.value)}
            data-testid="admin-operations-filter-aging-minutes"
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onReset}
            disabled={disabled}
            data-testid="admin-operations-filter-reset"
          >
            Reset
          </Button>
        </div>
      </div>
    </div>
  );
}
