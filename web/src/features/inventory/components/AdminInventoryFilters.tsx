// F2.18.5: controlled filter bar for the admin global inventory feed.
//
// Pure controlled component (same shape as features/audit
// AdminAuditFilters): every field is owned by the parent and
// surfaced back through `onChange` with the next `AdminInventoryFilters`
// snapshot. No fetching, no derived rules, no business logic.
//
// Filter set (exact match to F2.18.2C AdminInventoryFilters type and
// the F2.18.1A backend route — no extra fields, no missing fields):
//   - store_id    (admin-only: scope to one store).
//   - low_stock   (bool checkbox; explicit `false` is preserved).
//   - q           (free-text ILIKE over variant.sku + product.name).
//   - product_id  (UUID text).
//   - variant_id  (UUID text).
//   - status      (InventoryStatus enum select).
//
// `limit` / `offset` are owned by the parent page and NOT rendered
// here.
//
// Behavior contract (mirrors AdminAuditFilters):
//   - select "all" removes the corresponding key.
//   - text inputs: trim → empty drops the key; non-empty sets it.
//   - low_stock checkbox: explicit `true`/`false` are both meaningful;
//     unchecked clears the key.
//   - any filter change resets `offset` to 0 if the parent had one;
//     never introduces `offset` when it wasn't there.

import { Checkbox } from "@/components/ui/checkbox";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

import type { AdminInventoryFilters, InventoryStatus } from "../types";

const ALL = "all";

const STATUS_OPTIONS: ReadonlyArray<{
  readonly value: InventoryStatus;
  readonly label: string;
}> = [
  { value: "available", label: "Available" },
  { value: "reserved", label: "Reserved" },
  { value: "sold", label: "Sold" },
  { value: "flagged", label: "Flagged" },
  { value: "quarantined", label: "Quarantined" },
];

export interface AdminInventoryFiltersProps {
  filters: AdminInventoryFilters;
  onChange: (next: AdminInventoryFilters) => void;
  disabled?: boolean;
}

function withOffsetReset(
  next: AdminInventoryFilters,
): AdminInventoryFilters {
  if (next.offset !== undefined) {
    next.offset = 0;
  }
  return next;
}

function normalizeText(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export function AdminInventoryFilters({
  filters,
  onChange,
  disabled = false,
}: AdminInventoryFiltersProps) {
  const handleStoreIdChange = (value: string) => {
    const next: AdminInventoryFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.store_id;
    } else {
      next.store_id = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleQChange = (value: string) => {
    const next: AdminInventoryFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.q;
    } else {
      next.q = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleProductIdChange = (value: string) => {
    const next: AdminInventoryFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.product_id;
    } else {
      next.product_id = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleVariantIdChange = (value: string) => {
    const next: AdminInventoryFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.variant_id;
    } else {
      next.variant_id = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleStatusChange = (value: string) => {
    const next: AdminInventoryFilters = { ...filters };
    if (value === ALL) {
      delete next.status;
    } else {
      next.status = value as InventoryStatus;
    }
    onChange(withOffsetReset(next));
  };

  const handleLowStockChange = (checked: boolean) => {
    const next: AdminInventoryFilters = { ...filters };
    if (checked) {
      next.low_stock = true;
    } else {
      delete next.low_stock;
    }
    onChange(withOffsetReset(next));
  };

  return (
    <div
      className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 md:items-end"
      data-testid="admin-inventory-filters"
    >
      <div className="space-y-2">
        <Label htmlFor="admin-inventory-filter-store-id">Store</Label>
        <Input
          id="admin-inventory-filter-store-id"
          type="text"
          placeholder="Store UUID (optional)"
          value={filters.store_id ?? ""}
          disabled={disabled}
          onChange={(e) => handleStoreIdChange(e.target.value)}
          data-testid="admin-inventory-filter-store-id"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-inventory-filter-q">Search</Label>
        <Input
          id="admin-inventory-filter-q"
          type="search"
          placeholder="SKU or product name"
          value={filters.q ?? ""}
          disabled={disabled}
          onChange={(e) => handleQChange(e.target.value)}
          data-testid="admin-inventory-filter-q"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-inventory-filter-status">Status</Label>
        <Select
          value={filters.status ?? ALL}
          disabled={disabled}
          onValueChange={handleStatusChange}
        >
          <SelectTrigger
            id="admin-inventory-filter-status"
            data-testid="admin-inventory-filter-status-trigger"
          >
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL}>All statuses</SelectItem>
            {STATUS_OPTIONS.map((opt) => (
              <SelectItem key={opt.value} value={opt.value}>
                {opt.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-inventory-filter-product-id">Product</Label>
        <Input
          id="admin-inventory-filter-product-id"
          type="text"
          placeholder="Product UUID"
          value={filters.product_id ?? ""}
          disabled={disabled}
          onChange={(e) => handleProductIdChange(e.target.value)}
          data-testid="admin-inventory-filter-product-id"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="admin-inventory-filter-variant-id">Variant</Label>
        <Input
          id="admin-inventory-filter-variant-id"
          type="text"
          placeholder="Variant UUID"
          value={filters.variant_id ?? ""}
          disabled={disabled}
          onChange={(e) => handleVariantIdChange(e.target.value)}
          data-testid="admin-inventory-filter-variant-id"
        />
      </div>

      <div className="flex items-center gap-2 pb-2 md:pb-0">
        <Checkbox
          id="admin-inventory-filter-low-stock"
          checked={filters.low_stock === true}
          disabled={disabled}
          onCheckedChange={(value) => handleLowStockChange(value === true)}
          data-testid="admin-inventory-filter-low-stock"
        />
        <Label
          htmlFor="admin-inventory-filter-low-stock"
          className="text-sm cursor-pointer"
        >
          Low stock only
        </Label>
      </div>
    </div>
  );
}
