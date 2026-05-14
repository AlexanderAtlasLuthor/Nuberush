// Compact earnings widget for the Platform overview dashboard.
// Renders above "Orders by status" and links into the dedicated
// `/app/admin/earnings` page for the full breakdown.

import { ArrowRight, DollarSign, Wallet } from "lucide-react";
import { Link } from "react-router-dom";

import { useAdminEarningsQuery } from "../hooks";
import { MoneyTile, formatUsd } from "./MoneyTile";

export function AdminEarningsWidget() {
  const query = useAdminEarningsQuery();

  return (
    <section
      className="rounded-xl border border-border bg-card p-5 md:p-6"
      data-testid="admin-earnings-widget"
      aria-label="Platform earnings"
    >
      <div className="flex flex-col gap-1 mb-4 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">Platform earnings</h2>
          <p className="mt-1 text-sm text-muted-foreground max-w-2xl">
            20% commission on every delivered order across all stores.
          </p>
        </div>
        <Link
          to="/app/admin/earnings"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline self-start"
          data-testid="admin-earnings-widget-link"
        >
          View details
          <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </div>

      {query.isPending ? (
        <p
          className="text-sm text-muted-foreground"
          data-testid="admin-earnings-widget-loading"
        >
          Loading earnings…
        </p>
      ) : null}

      {query.isError ? (
        <p
          className="text-sm text-destructive"
          data-testid="admin-earnings-widget-error"
        >
          Could not load platform earnings.
        </p>
      ) : null}

      {query.isSuccess && query.data ? (
        <div className="grid gap-3 md:gap-4 grid-cols-1 md:grid-cols-3">
          <MoneyTile
            title="Commission earned"
            value={query.data.commission_total}
            description={`${query.data.delivered_orders} delivered orders`}
            variant="hero"
            icon={DollarSign}
            data-testid="admin-earnings-widget-commission"
          />
          <MoneyTile
            title="Gross base"
            value={query.data.gross_base_total}
            description="Subtotal + delivery + tip + tax"
            icon={Wallet}
            data-testid="admin-earnings-widget-gross-base"
          />
          <MoneyTile
            title="Customer paid"
            value={query.data.customer_paid_total}
            description={`Avg ${
              query.data.delivered_orders > 0
                ? formatUsd(
                    String(
                      Number(query.data.customer_paid_total) /
                        query.data.delivered_orders,
                    ),
                  )
                : formatUsd("0")
            } per order`}
            icon={Wallet}
            data-testid="admin-earnings-widget-customer-paid"
          />
        </div>
      ) : null}
    </section>
  );
}
