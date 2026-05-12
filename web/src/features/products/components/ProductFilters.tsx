// F2.8.3: filter bar for the products list page.
//
// Pure controlled inputs — every filter is owned by the parent's
// useState and surfaced back through callbacks. No fetching, no derived
// rules, no business logic; the parent passes the values to
// `useProductsQuery` verbatim.

import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { ProductComplianceStatus } from "../types";

const ALL_STATUSES = "all";

const COMPLIANCE_STATUSES: ProductComplianceStatus[] = [
  "allowed",
  "restricted",
  "banned",
];

interface ProductFiltersProps {
  complianceStatus: ProductComplianceStatus | undefined;
  onlyActive: boolean;
  disabled?: boolean;
  onComplianceStatusChange: (next: ProductComplianceStatus | undefined) => void;
  onOnlyActiveChange: (next: boolean) => void;
}

export function ProductFilters({
  complianceStatus,
  onlyActive,
  disabled,
  onComplianceStatusChange,
  onOnlyActiveChange,
}: ProductFiltersProps) {
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(12rem,16rem)_auto] md:items-end">
      <div className="space-y-2">
        <Label htmlFor="products-compliance-status">Compliance status</Label>
        <Select
          value={complianceStatus ?? ALL_STATUSES}
          disabled={disabled}
          onValueChange={(value) =>
            onComplianceStatusChange(
              value === ALL_STATUSES
                ? undefined
                : (value as ProductComplianceStatus),
            )
          }
        >
          <SelectTrigger
            id="products-compliance-status"
            data-testid="products-compliance-trigger"
          >
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_STATUSES}>All statuses</SelectItem>
            {COMPLIANCE_STATUSES.map((option) => (
              <SelectItem key={option} value={option}>
                {option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="flex items-center gap-2 pb-2">
        <Checkbox
          id="products-only-active"
          checked={onlyActive}
          disabled={disabled}
          onCheckedChange={(value) => onOnlyActiveChange(value === true)}
          data-testid="products-only-active-checkbox"
        />
        <Label
          htmlFor="products-only-active"
          className="text-sm cursor-pointer"
        >
          Only active
        </Label>
      </div>
    </div>
  );
}
