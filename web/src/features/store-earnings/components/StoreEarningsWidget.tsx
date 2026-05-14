// Compact earnings widget for the Store Dashboard. Shows the store's
// product revenue + units sold and links into the dedicated
// `/app/store/earnings` page for the full top-products breakdown.

import { ArrowRight, Package, TrendingUp } from "lucide-react";
import { Link } from "react-router-dom";

import { useStoreContext } from "@/auth";
import {
  MoneyTile,
  formatUsd,
} from "@/features/admin-earnings/components/MoneyTile";

import { useStoreEarningsQuery } from "../hooks";

export function StoreEarningsWidget() {
  const { currentStoreId } = useStoreContext();
  const query = useStoreEarningsQuery({ storeId: currentStoreId });

  return (
    <section
      className="rounded-xl border border-border bg-card p-5 md:p-6"
      data-testid="store-earnings-widget"
      aria-label="Store earnings"
    >
      <div className="flex flex-col gap-1 mb-4 md:flex-row md:items-end md:justify-between">
        <div className="min-w-0">
          <h2 className="text-base font-semibold">Earnings from products sold</h2>
          <p className="mt-1 text-sm text-muted-foreground max-w-2xl">
            Revenue your store has earned from delivered orders.
          </p>
        </div>
        <Link
          to="/app/store/earnings"
          className="inline-flex items-center gap-1.5 text-sm font-medium text-primary hover:underline self-start"
          data-testid="store-earnings-widget-link"
        >
          View details
          <ArrowRight className="h-3.5 w-3.5" aria-hidden="true" />
        </Link>
      </div>

      {query.isPending ? (
        <p
          className="text-sm text-muted-foreground"
          data-testid="store-earnings-widget-loading"
        >
          Loading earnings…
        </p>
      ) : null}

      {query.isError ? (
        <p
          className="text-sm text-destructive"
          data-testid="store-earnings-widget-error"
        >
          Could not load earnings.
        </p>
      ) : null}

      {query.isSuccess && query.data ? (
        <div className="grid gap-3 md:gap-4 grid-cols-1 md:grid-cols-3">
          <MoneyTile
            title="Product revenue"
            value={query.data.product_revenue}
            description={`From ${query.data.delivered_orders} delivered orders`}
            variant="hero"
            icon={TrendingUp}
            data-testid="store-earnings-widget-revenue"
          />
          <div
            className="relative h-full rounded-xl border border-border bg-card p-4 md:p-5 flex flex-col gap-2"
            data-testid="store-earnings-widget-items"
          >
            <div className="flex items-center justify-between gap-2">
              <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground truncate">
                Items sold
              </p>
              <span className="inline-flex items-center justify-center rounded-md shrink-0 h-7 w-7 bg-secondary/60 text-muted-foreground">
                <Package className="h-3.5 w-3.5" aria-hidden="true" />
              </span>
            </div>
            <p className="font-semibold tabular-nums tracking-tight leading-none text-2xl md:text-3xl">
              {query.data.total_items_sold}
            </p>
            <p className="text-xs text-muted-foreground leading-snug">
              Total units across delivered orders
            </p>
          </div>
          <MoneyTile
            title="Avg per order"
            value={
              query.data.delivered_orders > 0
                ? String(
                    Number(query.data.product_revenue) /
                      query.data.delivered_orders,
                  )
                : "0"
            }
            description={
              query.data.delivered_orders > 0
                ? `${formatUsd(query.data.product_revenue)} / ${query.data.delivered_orders} orders`
                : "No delivered orders yet"
            }
            data-testid="store-earnings-widget-avg"
          />
        </div>
      ) : null}
    </section>
  );
}
