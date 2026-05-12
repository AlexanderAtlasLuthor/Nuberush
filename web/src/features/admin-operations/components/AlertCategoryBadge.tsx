// F2.19.6: presentational badge for an alert's category.
//
// Pure presentational — no fetching, no context, no data
// derivation. Renders a readable label for one of the five locked
// `AdminOperationsAlertCategory` values; new values would be a
// contract update, not a frontend invention.

import { Badge } from "@/components/ui/badge";

import type { AdminOperationsAlertCategory } from "../types";

const LABEL: Record<AdminOperationsAlertCategory, string> = {
  low_stock: "Low stock",
  aging_order: "Aging order",
  compliance_blocker: "Compliance blocker",
  inactive_store: "Inactive store",
  store_no_inventory: "Store has no inventory",
};

export interface AlertCategoryBadgeProps {
  category: AdminOperationsAlertCategory;
}

export function AlertCategoryBadge({ category }: AlertCategoryBadgeProps) {
  return (
    <Badge
      variant="outline"
      data-testid={`alert-category-${category}`}
    >
      {LABEL[category]}
    </Badge>
  );
}
