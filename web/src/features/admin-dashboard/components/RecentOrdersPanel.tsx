// F2.19.5: recent orders panel.
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

import { Link } from "react-router-dom";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

import type { AdminDashboardSummary } from "../types";

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
    <Card data-testid="admin-dashboard-recent-orders">
      <CardHeader className="flex flex-row items-center justify-between space-y-0">
        <CardTitle className="text-base font-semibold">
          Recent orders
        </CardTitle>
        <Link
          to="/app/admin/orders"
          className="text-sm text-muted-foreground hover:text-foreground"
          data-testid="recent-orders-view-all"
        >
          View all
        </Link>
      </CardHeader>
      <CardContent>
        {orders.length === 0 ? (
          <p
            className="text-sm text-muted-foreground"
            data-testid="recent-orders-empty"
          >
            No recent orders yet.
          </p>
        ) : (
          <ul className="divide-y" data-testid="recent-orders-list">
            {orders.map((order) => (
              <li
                key={order.id}
                className="flex items-center justify-between gap-2 py-2 text-sm"
                data-testid={`recent-order-${order.id}`}
              >
                <div className="min-w-0">
                  <p className="font-medium">
                    Order{" "}
                    <span
                      className="font-mono text-xs text-muted-foreground"
                      data-testid={`recent-order-id-${order.id}`}
                    >
                      {shortId(order.id)}
                    </span>
                  </p>
                  <p
                    className="text-xs text-muted-foreground"
                    data-testid={`recent-order-created-at-${order.id}`}
                  >
                    {formatTimestamp(order.created_at)}
                  </p>
                </div>
                <div className="text-right">
                  <p
                    className="text-xs uppercase tracking-wide text-muted-foreground"
                    data-testid={`recent-order-status-${order.id}`}
                  >
                    {order.status}
                  </p>
                  <p
                    className="font-medium tabular-nums"
                    data-testid={`recent-order-total-${order.id}`}
                  >
                    {order.total_amount}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
