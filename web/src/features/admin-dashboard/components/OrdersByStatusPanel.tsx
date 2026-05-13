// F2.19.5 / Phase C: orders-by-status panel.
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
//
// Phase C — visual upgrade adapted from the NubeRush Design System
// ZIP (`StatusStackedBar.jsx`):
//   - Single horizontal stacked bar split into status segments.
//   - Per-segment width is computed *from the same real counts* the
//     legend prints — no fake totals, no synthesized percentages.
//   - When the total is 0 the bar renders empty (no segments) and
//     every legend row reads "0 / 0.0%" honestly.
//
// The component intentionally keeps the same `data-testid` surface
// the page tests already assert (`admin-dashboard-orders-by-status`
// and `status-{status}` per row).

import { cn } from "@/lib/utils";

import type { AdminDashboardSummary } from "../types";

type Status = keyof AdminDashboardSummary["orders"]["by_status"];

// Display order matches the backend `OrderStatus` enum declaration
// in `app.db.models.OrderStatus`. The list is the locked lifecycle
// sequence (pending → ... → returned) so operators read it the
// same way they read the order detail page.
const STATUS_DISPLAY_ORDER: ReadonlyArray<Status> = [
  "pending",
  "accepted",
  "preparing",
  "ready",
  "out_for_delivery",
  "delivered",
  "canceled",
  "returned",
];

const STATUS_LABEL: Record<Status, string> = {
  pending: "Pending",
  accepted: "Accepted",
  preparing: "Preparing",
  ready: "Ready",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  canceled: "Canceled",
  returned: "Returned",
};

// Color treatment per status. Purely a visual mapping — counts and
// totals still come straight from the backend payload.
const STATUS_DOT_CLASS: Record<Status, string> = {
  pending: "bg-muted-foreground/60",
  accepted: "bg-primary/70",
  preparing: "bg-primary",
  ready: "bg-primary",
  out_for_delivery: "bg-warning",
  delivered: "bg-success",
  canceled: "bg-destructive/70",
  returned: "bg-muted-foreground/40",
};

const STATUS_SEGMENT_CLASS: Record<Status, string> = STATUS_DOT_CLASS;

function formatPercent(count: number, total: number): string {
  if (total === 0) return "0.0%";
  return `${((count / total) * 100).toFixed(1)}%`;
}

export interface OrdersByStatusPanelProps {
  byStatus: AdminDashboardSummary["orders"]["by_status"];
}

export function OrdersByStatusPanel({ byStatus }: OrdersByStatusPanelProps) {
  const total = STATUS_DISPLAY_ORDER.reduce(
    (sum, status) => sum + byStatus[status],
    0,
  );

  return (
    <section
      className="rounded-xl border border-border bg-card p-5 md:p-6"
      data-testid="admin-dashboard-orders-by-status"
      aria-label="Orders by status"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">Orders by status</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            Backend-densified histogram. Every status is rendered, even when
            its count is zero.
          </p>
        </div>
        <div className="text-right shrink-0">
          <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
            Total
          </p>
          <p
            className="mt-0.5 text-lg font-semibold tabular-nums"
            data-testid="admin-dashboard-orders-by-status-total"
          >
            {total}
          </p>
        </div>
      </div>

      <div
        className="mt-5 flex h-2.5 w-full overflow-hidden rounded-full bg-secondary/60"
        role="presentation"
        aria-hidden="true"
      >
        {total > 0
          ? STATUS_DISPLAY_ORDER.map((status) => {
              const count = byStatus[status];
              if (count <= 0) return null;
              const widthPct = (count / total) * 100;
              return (
                <span
                  key={status}
                  className={cn("h-full", STATUS_SEGMENT_CLASS[status])}
                  style={{ width: `${widthPct}%` }}
                />
              );
            })
          : null}
      </div>

      <ul className="mt-5 grid grid-cols-1 gap-x-6 gap-y-2.5 sm:grid-cols-2 lg:grid-cols-4">
        {STATUS_DISPLAY_ORDER.map((status) => {
          const count = byStatus[status];
          return (
            <li
              key={status}
              className="flex items-center gap-2 text-sm min-w-0"
              data-testid={`status-${status}`}
            >
              <span
                className={cn(
                  "h-2 w-2 rounded-full shrink-0",
                  STATUS_DOT_CLASS[status],
                )}
                aria-hidden="true"
              />
              <span className="text-muted-foreground truncate flex-1">
                {STATUS_LABEL[status]}
              </span>
              <span className="font-medium tabular-nums">{count}</span>
              <span className="w-12 text-right text-xs text-muted-foreground tabular-nums">
                {formatPercent(count, total)}
              </span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
