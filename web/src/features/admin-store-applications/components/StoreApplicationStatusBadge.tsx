// F2.24.C7: reusable store-application status badge.
//
// Maps every `StoreApplicationStatus` to a readable label and a token-
// based colour treatment (same approach as StoreStatusBadge — semantic
// utility classes layered onto the shared Badge primitive, no raw hex).

import { cn } from "@/lib/utils";
import { Badge } from "@/components/ui/badge";

import type { StoreApplicationStatus } from "../types";

export interface StoreApplicationStatusBadgeProps {
  status: StoreApplicationStatus;
  className?: string;
}

interface StatusPresentation {
  label: string;
  classes: string;
}

const STATUS_PRESENTATION: Record<StoreApplicationStatus, StatusPresentation> = {
  draft: {
    label: "Draft",
    classes: "border-transparent bg-neutral-200 text-neutral-700 hover:bg-neutral-200",
  },
  submitted: {
    label: "Submitted",
    classes: "border-transparent bg-sky-100 text-sky-900 hover:bg-sky-100",
  },
  pending_review: {
    label: "Pending review",
    classes: "border-transparent bg-amber-100 text-amber-900 hover:bg-amber-100",
  },
  approved: {
    label: "Approved",
    classes: "border-transparent bg-emerald-100 text-emerald-900 hover:bg-emerald-100",
  },
  rejected: {
    label: "Rejected",
    classes: "border-transparent bg-red-100 text-red-900 hover:bg-red-100",
  },
};

export function StoreApplicationStatusBadge({
  status,
  className,
}: StoreApplicationStatusBadgeProps) {
  const presentation = STATUS_PRESENTATION[status];
  return (
    <Badge
      variant="outline"
      className={cn("uppercase tracking-wide", presentation.classes, className)}
      data-testid={`application-status-${status}`}
    >
      {presentation.label}
    </Badge>
  );
}
