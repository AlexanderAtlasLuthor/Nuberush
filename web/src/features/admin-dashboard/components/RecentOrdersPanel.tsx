// F2.19.5 / Phase C: recent orders panel.
//
// Renders the backend-provided `orders.recent` tail (bounded to 5
// by the backend). Pure presentational — never fetches orders
// separately, never re-sorts, never recomputes totals.
//
// Each row exposes the order id (linked to the global admin orders
// page where the operator can drill in further), status, total, and
// created_at. No `customer_user_id` is shown (admins typically
// don't need it on a dashboard tail), no per-store enrichment is
// performed.
//
// Phase C — visual upgrade adapted from the NubeRush Design System
// ZIP (`OrderTimeline.jsx`):
//   - Each row reads as a compact card with a colored status pill
//     and tabular total alignment.
//   - The status pill colors are a *visual* mapping from the real
//     `OrderStatus` value; the displayed text and number are never
//     altered or replaced.
//   - Rejected from the ZIP: the 5-stage StageBar lifecycle preview
//     (we only have the current status on the wire, not the history,
//     so progress visualisation would invent a stage transition).
//   - Rejected: customer names / store names from the ZIP demo;
//     the backend tail doesn't carry those, and inventing them would
//     be a mock.

import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";

import type { AdminDashboardSummary } from "../types";

type OrderStatus =
  AdminDashboardSummary["orders"]["recent"][number]["status"];

const STATUS_PILL_CLASS: Record<OrderStatus, string> = {
  pending: "bg-secondary text-muted-foreground",
  accepted: "bg-primary/15 text-primary",
  preparing: "bg-primary/15 text-primary",
  ready: "bg-primary/15 text-primary",
  out_for_delivery: "bg-warning/15 text-warning",
  delivered: "bg-success/15 text-success",
  canceled: "bg-destructive/15 text-destructive",
  returned: "bg-muted text-muted-foreground",
};

export interface RecentOrdersPanelProps {
  orders: AdminDashboardSummary["orders"]["recent"];
}

function shortId(id: string): string {
  // Show the first 8 chars of the UUID — enough to disambiguate on
  // the dashboard surface, while keeping the row compact. The full
  // id is preserved in the link href for downstream pages.
  return id.length > 8 ? id.slice(0, 8) : id;
}

function formatTimestamp(iso: string): string {
  // Lightweight UTC-ish formatting that doesn't pull in a locale-
  // dependent library. Anything fancier belongs in a shared
  // formatter and is out of scope for the dashboard.
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toISOString().replace("T", " ").replace(/:\d\d\.\d+Z$/, "Z");
}

export function RecentOrdersPanel({ orders }: RecentOrdersPanelProps) {
  return (
    <section
      className="rounded-xl border border-border bg-card flex flex-col"
      data-testid="admin-dashboard-recent-orders"
      aria-label="Recent orders"
    >
      <header className="flex items-start justify-between gap-3 border-b border-border px-5 py-4 md:px-6">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">Recent orders</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">
            Last 5 — bounded by the backend.
          </p>
        </div>
        <Link
          to="/app/admin/orders"
          className="inline-flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground shrink-0"
          data-testid="recent-orders-view-all"
        >
          View all
          <ArrowRight className="h-3 w-3" aria-hidden="true" />
        </Link>
      </header>
      <div className="px-5 md:px-6">
        {orders.length === 0 ? (
          <p
            className="py-5 text-sm text-muted-foreground"
            data-testid="recent-orders-empty"
          >
            No recent orders yet.
          </p>
        ) : (
          <ul className="divide-y divide-border" data-testid="recent-orders-list">
            {orders.map((order) => (
              <li
                key={order.id}
                className="flex items-center gap-3 py-3 text-sm"
                data-testid={`recent-order-${order.id}`}
              >
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className="font-mono text-xs text-muted-foreground"
                      data-testid={`recent-order-id-${order.id}`}
                    >
                      {shortId(order.id)}
                    </span>
                    <span
                      className={cn(
                        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
                        STATUS_PILL_CLASS[order.status] ??
                          "bg-secondary text-muted-foreground",
                      )}
                      data-testid={`recent-order-status-${order.id}`}
                    >
                      {order.status}
                    </span>
                  </div>
                  <p
                    className="mt-0.5 text-xs text-muted-foreground"
                    data-testid={`recent-order-created-at-${order.id}`}
                  >
                    {formatTimestamp(order.created_at)}
                  </p>
                </div>
                <p
                  className="text-sm font-semibold tabular-nums shrink-0"
                  data-testid={`recent-order-total-${order.id}`}
                >
                  {order.total_amount}
                </p>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
