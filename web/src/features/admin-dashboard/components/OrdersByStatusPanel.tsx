// F2.19.5: orders-by-status panel.
//
// Renders the backend-provided `orders.by_status` histogram
// verbatim. The backend densifies the dict so every `OrderStatus`
// member is present (zero-filled when no rows match) — the panel
// renders every entry in that fixed order without computing,
// re-sorting, or hiding zeros.
//
// IMPORTANT: this component MUST NOT compute order counts from
// `orders.recent`. `recent` is a 5-row tail; the histogram is the
// authoritative source.

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

import type { AdminDashboardSummary } from "../types";

// Display order matches the backend `OrderStatus` enum declaration
// in `app.db.models.OrderStatus`. The list is the locked lifecycle
// sequence (pending → ... → returned) so operators read it the
// same way they read the order detail page.
const STATUS_DISPLAY_ORDER: ReadonlyArray<keyof AdminDashboardSummary["orders"]["by_status"]> = [
  "pending",
  "accepted",
  "preparing",
  "ready",
  "out_for_delivery",
  "delivered",
  "canceled",
  "returned",
];

const STATUS_LABEL: Record<keyof AdminDashboardSummary["orders"]["by_status"], string> = {
  pending: "Pending",
  accepted: "Accepted",
  preparing: "Preparing",
  ready: "Ready",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  canceled: "Canceled",
  returned: "Returned",
};

export interface OrdersByStatusPanelProps {
  byStatus: AdminDashboardSummary["orders"]["by_status"];
}

export function OrdersByStatusPanel({ byStatus }: OrdersByStatusPanelProps) {
  return (
    <Card data-testid="admin-dashboard-orders-by-status">
      <CardHeader>
        <CardTitle className="text-base font-semibold">
          Orders by status
        </CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-sm sm:grid-cols-4">
          {STATUS_DISPLAY_ORDER.map((status) => (
            <div
              key={status}
              className="flex items-baseline justify-between"
              data-testid={`status-${status}`}
            >
              <dt className="text-muted-foreground">{STATUS_LABEL[status]}</dt>
              <dd className="font-medium tabular-nums">{byStatus[status]}</dd>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}
