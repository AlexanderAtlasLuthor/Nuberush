// F2.26.6.C: controlled filter bar for the regulatory alerts read surface.
//
// Pure controlled component (same contract as AdminOperationsFilters): every
// field is owned by the parent and surfaced back through `onChange` with the
// next `ComplianceAlertFilters` snapshot. No fetching, no business logic.
//
// Filter set (matches the GET /admin/regulatory/alerts query contract):
//   - status              (enum select, "all" omits)
//   - severity            (enum select, "all" omits)
//   - recommended_action  (enum select, "all" omits)
//   - product_id          (free text; trim → drop empty)
//   - notice_id           (free text; trim → drop empty)
//
// `limit` / `offset` are owned by the parent page and NOT rendered here. Any
// filter change resets `offset` to 0 via `withOffsetReset`.
//
// Enum filters use native <select> rather than the Radix Select primitive:
// they are label-associated, keyboard/AT accessible, and deterministically
// testable in jsdom (the test env polyfills ResizeObserver but not the
// pointer APIs Radix needs to open a listbox).

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

import type {
  ComplianceAlertFilters,
  ComplianceAlertSeverity,
  ComplianceAlertStatus,
  ComplianceRecommendedAction,
} from "../types";

const ALL = "all";

const STATUS_OPTIONS: ReadonlyArray<{
  readonly value: ComplianceAlertStatus;
  readonly label: string;
}> = [
  { value: "open", label: "Open" },
  { value: "acknowledged", label: "Acknowledged" },
  { value: "actioned", label: "Actioned" },
  { value: "dismissed", label: "Dismissed" },
];

const SEVERITY_OPTIONS: ReadonlyArray<{
  readonly value: ComplianceAlertSeverity;
  readonly label: string;
}> = [
  { value: "low", label: "Low" },
  { value: "medium", label: "Medium" },
  { value: "high", label: "High" },
  { value: "critical", label: "Critical" },
];

const RECOMMENDED_ACTION_OPTIONS: ReadonlyArray<{
  readonly value: ComplianceRecommendedAction;
  readonly label: string;
}> = [
  { value: "none", label: "No action recommended" },
  { value: "hold", label: "Hold recommended" },
  { value: "ban", label: "Ban recommended" },
];

const SELECT_CLASS =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50";

export interface RegulatoryAlertsFiltersProps {
  filters: ComplianceAlertFilters;
  onChange: (next: ComplianceAlertFilters) => void;
  onReset: () => void;
  disabled?: boolean;
}

/** Any filter change returns to the first page. */
function withOffsetReset(next: ComplianceAlertFilters): ComplianceAlertFilters {
  if (next.offset !== undefined) {
    next.offset = 0;
  }
  return next;
}

function normalizeText(value: string): string | undefined {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
}

export function RegulatoryAlertsFilters({
  filters,
  onChange,
  onReset,
  disabled = false,
}: RegulatoryAlertsFiltersProps) {
  const handleStatusChange = (value: string) => {
    const next: ComplianceAlertFilters = { ...filters };
    if (value === ALL) {
      delete next.status;
    } else {
      next.status = value as ComplianceAlertStatus;
    }
    onChange(withOffsetReset(next));
  };

  const handleSeverityChange = (value: string) => {
    const next: ComplianceAlertFilters = { ...filters };
    if (value === ALL) {
      delete next.severity;
    } else {
      next.severity = value as ComplianceAlertSeverity;
    }
    onChange(withOffsetReset(next));
  };

  const handleRecommendedActionChange = (value: string) => {
    const next: ComplianceAlertFilters = { ...filters };
    if (value === ALL) {
      delete next.recommended_action;
    } else {
      next.recommended_action = value as ComplianceRecommendedAction;
    }
    onChange(withOffsetReset(next));
  };

  const handleProductIdChange = (value: string) => {
    const next: ComplianceAlertFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.product_id;
    } else {
      next.product_id = normalized;
    }
    onChange(withOffsetReset(next));
  };

  const handleNoticeIdChange = (value: string) => {
    const next: ComplianceAlertFilters = { ...filters };
    const normalized = normalizeText(value);
    if (normalized === undefined) {
      delete next.notice_id;
    } else {
      next.notice_id = normalized;
    }
    onChange(withOffsetReset(next));
  };

  return (
    <div
      className="grid gap-4 md:grid-cols-2 lg:grid-cols-3 md:items-end"
      data-testid="regulatory-filters"
    >
      <div className="space-y-2">
        <Label htmlFor="regulatory-filter-status">Status</Label>
        <select
          id="regulatory-filter-status"
          className={cn(SELECT_CLASS)}
          value={filters.status ?? ALL}
          disabled={disabled}
          onChange={(e) => handleStatusChange(e.target.value)}
          data-testid="regulatory-filter-status"
        >
          <option value={ALL}>All statuses</option>
          {STATUS_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="regulatory-filter-severity">Severity</Label>
        <select
          id="regulatory-filter-severity"
          className={cn(SELECT_CLASS)}
          value={filters.severity ?? ALL}
          disabled={disabled}
          onChange={(e) => handleSeverityChange(e.target.value)}
          data-testid="regulatory-filter-severity"
        >
          <option value={ALL}>All severities</option>
          {SEVERITY_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="regulatory-filter-recommended-action">
          Recommended action
        </Label>
        <select
          id="regulatory-filter-recommended-action"
          className={cn(SELECT_CLASS)}
          value={filters.recommended_action ?? ALL}
          disabled={disabled}
          onChange={(e) => handleRecommendedActionChange(e.target.value)}
          data-testid="regulatory-filter-recommended-action"
        >
          <option value={ALL}>All recommendations</option>
          {RECOMMENDED_ACTION_OPTIONS.map((opt) => (
            <option key={opt.value} value={opt.value}>
              {opt.label}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="regulatory-filter-product-id">Product ID</Label>
        <Input
          id="regulatory-filter-product-id"
          type="text"
          placeholder="Filter by product ID (optional)"
          value={filters.product_id ?? ""}
          disabled={disabled}
          onChange={(e) => handleProductIdChange(e.target.value)}
          data-testid="regulatory-filter-product-id"
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="regulatory-filter-notice-id">Notice ID</Label>
        <Input
          id="regulatory-filter-notice-id"
          type="text"
          placeholder="Filter by notice ID (optional)"
          value={filters.notice_id ?? ""}
          disabled={disabled}
          onChange={(e) => handleNoticeIdChange(e.target.value)}
          data-testid="regulatory-filter-notice-id"
        />
      </div>

      <div className="space-y-2 md:items-end md:flex md:flex-col">
        <Button
          type="button"
          variant="outline"
          size="sm"
          onClick={onReset}
          disabled={disabled}
          data-testid="regulatory-filter-reset"
          className="md:mt-auto"
        >
          Reset filters
        </Button>
      </div>
    </div>
  );
}
