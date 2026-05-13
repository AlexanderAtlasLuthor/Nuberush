// F2.20.6: controlled filter bar for the admin compliance queue.
//
// Same shape as AdminProductsFilters (F2.20.5) and
// AdminOperationsFilters (F2.19.6): every field is owned by the
// parent and surfaced back through `onChange` with the next
// `AdminComplianceProductsFilters` snapshot. No fetching, no
// derived rules, no business logic.
//
// Filter set (exact match to the F2.20.2 backend route — no extras,
// no missing fields):
//   - q                 (free text search)
//   - compliance_status (3-value enum select)
//   - allowed_for_sale  (boolean tri-state)
//   - is_active         (boolean tri-state)
//
// `limit` / `offset` are owned by the parent page and NOT rendered
// here. There is intentionally NO `category` field (the backend
// route does not accept it — see `backend/app/api/routes/
// admin_compliance.py`). There is also NO `store_id` filter —
// Product is global per F2.20.0 §4. No workflow/incident/task
// filters exist per F2.20.0 §12.
//
// Behavior contract:
//   - "all" select value removes the corresponding key.
//   - Text inputs: trim → empty drops the key; non-empty sets it.
//   - Any filter change resets `offset` to 0 if the parent had one.
//   - Reset button restores the parent's "default" snapshot through
//     `onReset` when provided.

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
  AdminComplianceProductsFilters,
  ProductComplianceStatus,
} from "../types";

const ALL = "all";
const BOOL_TRUE = "true";
const BOOL_FALSE = "false";

const COMPLIANCE_OPTIONS: ReadonlyArray<{
  readonly value: ProductComplianceStatus;
  readonly label: string;
}> = [
  { value: "allowed", label: "Allowed" },
  { value: "restricted", label: "Restricted" },
  { value: "banned", label: "Banned" },
];

export interface ComplianceFiltersProps {
  filters: AdminComplianceProductsFilters;
  onChange: (next: AdminComplianceProductsFilters) => void;
  onReset?: () => void;
  disabled?: boolean;
}

function withOffsetReset(
  next: AdminComplianceProductsFilters,
): AdminComplianceProductsFilters {
  if (next.offset !== undefined) {
    next.offset = 0;
  }
  return next;
}

function normalizeText(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

function selectValueForBoolean(value: boolean | undefined): string {
  if (value === true) return BOOL_TRUE;
  if (value === false) return BOOL_FALSE;
  return ALL;
}

function booleanFromSelect(value: string): boolean | undefined {
  if (value === BOOL_TRUE) return true;
  if (value === BOOL_FALSE) return false;
  return undefined;
}

export function ComplianceFilters({
  filters,
  onChange,
  onReset,
  disabled = false,
}: ComplianceFiltersProps) {
  const handleQChange = (value: string) => {
    const next: AdminComplianceProductsFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.q;
    } else {
      next.q = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleComplianceStatusChange = (value: string) => {
    const next: AdminComplianceProductsFilters = { ...filters };
    if (value === ALL) {
      delete next.compliance_status;
    } else {
      next.compliance_status = value as ProductComplianceStatus;
    }
    onChange(withOffsetReset(next));
  };

  const handleAllowedForSaleChange = (value: string) => {
    const next: AdminComplianceProductsFilters = { ...filters };
    const parsed = booleanFromSelect(value);
    if (parsed === undefined) {
      delete next.allowed_for_sale;
    } else {
      next.allowed_for_sale = parsed;
    }
    onChange(withOffsetReset(next));
  };

  const handleIsActiveChange = (value: string) => {
    const next: AdminComplianceProductsFilters = { ...filters };
    const parsed = booleanFromSelect(value);
    if (parsed === undefined) {
      delete next.is_active;
    } else {
      next.is_active = parsed;
    }
    onChange(withOffsetReset(next));
  };

  return (
    <div
      className="grid gap-4 md:grid-cols-2 lg:grid-cols-4 md:items-end"
      data-testid="compliance-filters"
    >
      <div className="space-y-2">
        <Label htmlFor="compliance-filter-q">Search</Label>
        <Input
          id="compliance-filter-q"
          type="text"
          placeholder="Name, brand, category, description"
          value={filters.q ?? ""}
          disabled={disabled}
          onChange={(e) => handleQChange(e.target.value)}
          data-testid="compliance-filter-q"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="compliance-filter-compliance">Compliance</Label>
        <Select
          value={filters.compliance_status ?? ALL}
          disabled={disabled}
          onValueChange={handleComplianceStatusChange}
        >
          <SelectTrigger
            id="compliance-filter-compliance"
            data-testid="compliance-filter-compliance-trigger"
          >
            <SelectValue placeholder="All compliance" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All compliance</SelectItem>
            {COMPLIANCE_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="compliance-filter-allowed-for-sale">
          Allowed for sale
        </Label>
        <Select
          value={selectValueForBoolean(filters.allowed_for_sale)}
          disabled={disabled}
          onValueChange={handleAllowedForSaleChange}
        >
          <SelectTrigger
            id="compliance-filter-allowed-for-sale"
            data-testid="compliance-filter-allowed-for-sale-trigger"
          >
            <SelectValue placeholder="All" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All</SelectItem>
            <SelectItem value={BOOL_TRUE}>Yes</SelectItem>
            <SelectItem value={BOOL_FALSE}>No</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="compliance-filter-is-active">Active</Label>
        <div className="flex items-center gap-2">
          <Select
            value={selectValueForBoolean(filters.is_active)}
            disabled={disabled}
            onValueChange={handleIsActiveChange}
          >
            <SelectTrigger
              id="compliance-filter-is-active"
              className="flex-1"
              data-testid="compliance-filter-is-active-trigger"
            >
              <SelectValue placeholder="All" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All</SelectItem>
              <SelectItem value={BOOL_TRUE}>Yes</SelectItem>
              <SelectItem value={BOOL_FALSE}>No</SelectItem>
            </SelectContent>
          </Select>
          {onReset ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onReset}
              disabled={disabled}
              data-testid="compliance-filter-reset"
            >
              Reset
            </Button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
