// Full earnings page for the store account. Shows only what the store
// earns from products sold — no delivery, no tip, no tax, no platform
// commission (those live on the admin earnings surface).

import { AlertCircle, Package, TrendingUp } from "lucide-react";

import { useStoreContext } from "@/auth";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  MoneyTile,
  formatUsd,
} from "@/features/admin-earnings/components/MoneyTile";

import { useStoreEarningsQuery } from "../hooks";

function PageHeader() {
  return (
    <header>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Store · Earnings
      </p>
      <h1 className="mt-1.5 text-2xl font-semibold tracking-tight md:text-[28px]">
        Earnings
      </h1>
      <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground leading-relaxed">
        Revenue your store has generated from delivered orders. Read-only —
        every value is computed by the backend from existing data on each
        request. Delivery, tips, taxes and platform commission are excluded.
      </p>
    </header>
  );
}

function LoadingState() {
  return (
    <p
      className="text-sm text-muted-foreground"
      data-testid="store-earnings-loading"
    >
      Loading earnings…
    </p>
  );
}

interface ErrorStateProps {
  error: unknown;
  onRetry: () => void;
}

function ErrorState({ error, onRetry }: ErrorStateProps) {
  const message =
    error instanceof Error && error.message
      ? error.message
      : "Unable to load earnings.";
  return (
    <Alert variant="destructive" data-testid="store-earnings-error">
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Could not load earnings</AlertTitle>
      <AlertDescription className="flex flex-col gap-2">
        <span>{message}</span>
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          className="self-start"
          data-testid="store-earnings-retry"
        >
          Retry
        </Button>
      </AlertDescription>
    </Alert>
  );
}

export default function StoreEarningsPage() {
  const { currentStoreId } = useStoreContext();
  const query = useStoreEarningsQuery({ storeId: currentStoreId });

  return (
    <div
      className="px-4 py-5 md:px-8 md:py-7 max-w-[1320px] mx-auto w-full space-y-5 md:space-y-6"
      data-testid="store-earnings-page"
    >
      <PageHeader />

      {!currentStoreId ? (
        <p
          className="text-sm text-muted-foreground"
          data-testid="store-earnings-no-store"
        >
          Select a store to view earnings.
        </p>
      ) : null}

      {query.isPending && currentStoreId ? <LoadingState /> : null}

      {query.isError ? (
        <ErrorState
          error={query.error}
          onRetry={() => {
            void query.refetch();
          }}
        />
      ) : null}

      {query.isSuccess && query.data ? (
        <>
          <section className="grid gap-3 md:gap-4 grid-cols-1 sm:grid-cols-3">
            <MoneyTile
              title="Product revenue"
              value={query.data.product_revenue}
              description={`From ${query.data.delivered_orders} delivered orders`}
              variant="hero"
              icon={TrendingUp}
              data-testid="store-earnings-revenue"
            />
            <div
              className="relative h-full rounded-xl border border-border bg-card p-4 md:p-5 flex flex-col gap-2"
              data-testid="store-earnings-items"
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
              title="Avg revenue per order"
              value={
                query.data.delivered_orders > 0
                  ? String(
                      Number(query.data.product_revenue) /
                        query.data.delivered_orders,
                    )
                  : "0"
              }
              description="Product revenue / delivered orders"
              data-testid="store-earnings-avg"
            />
          </section>

          <section
            className="rounded-xl border border-border bg-card overflow-hidden"
            data-testid="store-earnings-top-products"
            aria-label="Top products by revenue"
          >
            <div className="p-5 md:p-6 border-b border-border">
              <h2 className="text-base font-semibold">
                Top products by revenue
              </h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Top {query.data.top_products.length} variants in your store
                across delivered orders.
              </p>
            </div>
            {query.data.top_products.length === 0 ? (
              <p
                className="p-5 md:p-6 text-sm text-muted-foreground"
                data-testid="store-earnings-top-products-empty"
              >
                No products sold yet.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-secondary/40 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    <tr>
                      <th className="px-5 py-3 text-left">Product</th>
                      <th className="px-5 py-3 text-left">Variant</th>
                      <th className="px-5 py-3 text-right">Units sold</th>
                      <th className="px-5 py-3 text-right">Revenue</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.top_products.map((row) => (
                      <tr
                        key={row.variant_id}
                        className="border-t border-border"
                        data-testid={`store-earnings-row-${row.variant_id}`}
                      >
                        <td className="px-5 py-3 font-medium">
                          {row.product_name}
                        </td>
                        <td className="px-5 py-3 text-muted-foreground">
                          {row.variant_label ?? "—"}
                        </td>
                        <td className="px-5 py-3 text-right tabular-nums">
                          {row.quantity_sold}
                        </td>
                        <td className="px-5 py-3 text-right tabular-nums font-semibold">
                          {formatUsd(row.revenue)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        </>
      ) : null}
    </div>
  );
}
