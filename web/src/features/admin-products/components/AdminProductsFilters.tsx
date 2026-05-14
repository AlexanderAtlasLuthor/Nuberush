// F2.20.5: controlled filter bar for the admin products oversight page.
//
// Pure controlled component (same shape as AdminOperationsFilters):
// every field is owned by the parent and surfaced back through
// `onChange` with the next `AdminProductsFilters` snapshot. No
// fetching, no derived rules, no business logic.
//
// Filter set (exact match to the F2.20.0 / F2.20.1 contract):
//   - q                 (free text search)
//   - category          (free text)
//   - compliance_status (3-value enum select)
//   - allowed_for_sale  (boolean tri-state)
//   - is_active         (boolean tri-state)
//
// `limit` / `offset` are owned by the parent page and NOT rendered
// here. There is NO `store_id` filter — Product is global per
// F2.20.0 §4; store-specific availability lives on InventoryItem.
//
// Behavior contract (mirrors AdminOperationsFilters):
//   - "all" select value removes the corresponding key.
//   - Text inputs: trim → empty drops the key; non-empty sets it.
//   - Any filter change resets `offset` to 0 if the parent had one.
//   - Reset button restores the parent's "default" snapshot through
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
  AdminProductsFilters,
  ProductApprovalStatus,
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

const APPROVAL_OPTIONS: ReadonlyArray<{
  readonly value: ProductApprovalStatus;
  readonly label: string;
}> = [
  { value: "pending", label: "Pending" },
  { value: "approved", label: "Approved" },
  { value: "rejected", label: "Rejected" },
];

export interface AdminProductsFiltersProps {
  filters: AdminProductsFilters;
  onChange: (next: AdminProductsFilters) => void;
  onReset: () => void;
  disabled?: boolean;
}

function withOffsetReset(
  next: AdminProductsFilters,
): AdminProductsFilters {
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

export function AdminProductsFilters({
  filters,
  onChange,
  onReset,
  disabled = false,
}: AdminProductsFiltersProps) {
  const handleQChange = (value: string) => {
    const next: AdminProductsFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.q;
    } else {
      next.q = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleCategoryChange = (value: string) => {
    const next: AdminProductsFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.category;
    } else {
      next.category = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleComplianceStatusChange = (value: string) => {
    const next: AdminProductsFilters = { ...filters };
    if (value === ALL) {
      delete next.compliance_status;
    } else {
      next.compliance_status = value as ProductComplianceStatus;
    }
    onChange(withOffsetReset(next));
  };

  const handleApprovalStatusChange = (value: string) => {
    const next: AdminProductsFilters = { ...filters };
    if (value === ALL) {
      delete next.approval_status;
    } else {
      next.approval_status = value as ProductApprovalStatus;
    }
    onChange(withOffsetReset(next));
  };

  const handleAllowedForSaleChange = (value: string) => {
    const next: AdminProductsFilters = { ...filters };
    const parsed = booleanFromSelect(value);
    if (parsed === undefined) {
      delete next.allowed_for_sale;
    } else {
      next.allowed_for_sale = parsed;
    }
    onChange(withOffsetReset(next));
  };

  const handleIsActiveChange = (value: string) => {
    const next: AdminProductsFilters = { ...filters };
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
      className="grid gap-4 md:grid-cols-2 lg:grid-cols-6 md:items-end"
      data-testid="admin-products-filters"
    >
      <div className="space-y-2">
        <Label htmlFor="admin-products-filter-q">Search</Label>
        <Input
          id="admin-products-filter-q"
          type="text"
          placeholder="Name, brand, category, description"
          value={filters.q ?? ""}
          disabled={disabled}
          onChange={(e) => handleQChange(e.target.value)}
          data-testid="admin-products-filter-q"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-products-filter-category">Category</Label>
        <Input
          id="admin-products-filter-category"
          type="text"
          placeholder="e.g. vape, edibles"
          value={filters.category ?? ""}
          disabled={disabled}
          onChange={(e) => handleCategoryChange(e.target.value)}
          data-testid="admin-products-filter-category"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-products-filter-approval">Approval</Label>
        <Select
          value={filters.approval_status ?? ALL}
          disabled={disabled}
          onValueChange={handleApprovalStatusChange}
        >
          <SelectTrigger
            id="admin-products-filter-approval"
            data-testid="admin-products-filter-approval-trigger"
          >
            <SelectValue placeholder="All approval" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All approval</SelectItem>
            {APPROVAL_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-products-filter-compliance">Compliance</Label>
        <Select
          value={filters.compliance_status ?? ALL}
          disabled={disabled}
          onValueChange={handleComplianceStatusChange}
        >
          <SelectTrigger
            id="admin-products-filter-compliance"
            data-testid="admin-products-filter-compliance-trigger"
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
        <Label htmlFor="admin-products-filter-allowed-for-sale">
          Allowed for sale
        </Label>
        <Select
          value={selectValueForBoolean(filters.allowed_for_sale)}
          disabled={disabled}
          onValueChange={handleAllowedForSaleChange}
        >
          <SelectTrigger
            id="admin-products-filter-allowed-for-sale"
            data-testid="admin-products-filter-allowed-for-sale-trigger"
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
        <Label htmlFor="admin-products-filter-is-active">Active</Label>
        <div className="flex items-center gap-2">
          <Select
            value={selectValueForBoolean(filters.is_active)}
            disabled={disabled}
            onValueChange={handleIsActiveChange}
          >
            <SelectTrigger
              id="admin-products-filter-is-active"
              className="flex-1"
              data-testid="admin-products-filter-is-active-trigger"
            >
              <SelectValue placeholder="All" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All</SelectItem>
              <SelectItem value={BOOL_TRUE}>Yes</SelectItem>
              <SelectItem value={BOOL_FALSE}>No</SelectItem>
            </SelectContent>
          </Select>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={onReset}
            disabled={disabled}
            data-testid="admin-products-filter-reset"
          >
            Reset
          </Button>
        </div>
      </div>
    </div>
  );
}
