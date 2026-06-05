// Compact earnings widget for the Platform overview dashboard.
// Renders above "Orders by status" and links into the dedicated
// `/app/admin/earnings` page for the full breakdown.

import { ArrowRight, Receipt, Truck } from "lucide-react";
import { Link } from "react-router-dom";

import { useAdminEarningsQuery } from "../hooks";
import { EarningsDisclaimer } from "./EarningsDisclaimer";
import { EarningsHeroCard } from "./EarningsHeroCard";
import { MoneyTile } from "./MoneyTile";
import { formatUsd } from "./format";

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
          <h2 className="text-base font-semibold">Projected platform earnings</h2>
          <p className="mt-1 text-sm text-muted-foreground max-w-2xl">
            Projected 20% platform commission across all stores. Stripe pending.
          </p>
        </div>
        <Link
          to="/app/admin/earnings"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-success hover:underline self-start"
          data-testid="admin-earnings-widget-link"
        >
          View details
          <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </div>

      <div className="mb-4">
        <EarningsDisclaimer data-testid="admin-earnings-widget-disclaimer" />
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
        <div className="grid gap-3 md:gap-4 grid-cols-1 lg:grid-cols-[1.6fr_1fr_1fr]">
          <EarningsHeroCard
            eyebrow="Projected platform commission"
            value={query.data.commission_total}
            description={`${query.data.delivered_orders} delivered orders · projected 20% of order value`}
            composition={[
              {
                label: "Subtotal",
                amount: query.data.subtotal_total,
              },
              {
                label: "Delivery",
                amount: query.data.delivery_total,
              },
              {
                label: "Tax",
                amount: query.data.tax_total,
              },
              {
                label: "Commission",
                amount: query.data.commission_total,
                highlight: true,
              },
            ]}
            to="/app/admin/earnings"
            data-testid="admin-earnings-widget-commission"
          />
          <MoneyTile
            title="Projected order value"
            value={query.data.gross_base_total}
            description="Subtotal + delivery + tip + tax"
            icon={Receipt}
            data-testid="admin-earnings-widget-gross-base"
          />
          <MoneyTile
            title="Projected customer total"
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
            } per order (projected)`}
            icon={Truck}
            data-testid="admin-earnings-widget-customer-paid"
          />
        </div>
      ) : null}
    </section>
  );
}
