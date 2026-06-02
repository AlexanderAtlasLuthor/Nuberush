// Full earnings page for the platform admin.
//
// Read-only. Every number on this page comes verbatim from the
// `GET /admin/earnings` aggregator — the frontend never recomputes
// commission, gross base, or per-store breakdowns.

import {
  AlertCircle,
  Coins,
  Receipt,
  Truck,
  Wallet,
} from "lucide-react";

import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

import { EarningsHeroCard } from "../components/EarningsHeroCard";
import { MoneyTile } from "../components/MoneyTile";
import { formatUsd } from "../components/format";
import { useAdminEarningsQuery } from "../hooks";

function PageHeader() {
  return (
    <header>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Admin · Earnings
      </p>
      <h1 className="mt-1.5 text-2xl font-semibold tracking-tight md:text-[28px]">
        Platform earnings
      </h1>
      <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground leading-relaxed">
        20% commission on every delivered order. Pricing breakdown per
        order: product subtotal + $10 delivery + tip (if any) + taxes +
        20% platform commission. Read-only — every value is computed by
        the backend from existing orders on each request.
      </p>
    </header>
  );
}

function LoadingState() {
  return (
    <p
      className="text-sm text-muted-foreground"
      data-testid="admin-earnings-loading"
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
    <Alert variant="destructive" data-testid="admin-earnings-error">
      <AlertCircle className="h-4 w-4" />
      <AlertTitle>Could not load platform earnings</AlertTitle>
      <AlertDescription className="flex flex-col gap-2">
        <span>{message}</span>
        <Button
          variant="outline"
          size="sm"
          onClick={onRetry}
          className="self-start"
          data-testid="admin-earnings-retry"
        >
          Retry
        </Button>
      </AlertDescription>
    </Alert>
  );
}

interface StoreShareBarProps {
  value: string;
  max: string;
}

function StoreShareBar({ value, max }: StoreShareBarProps) {
  const valueNumber = Number(value);
  const maxNumber = Number(max);
  if (!Number.isFinite(valueNumber) || !Number.isFinite(maxNumber) || maxNumber <= 0) {
    return null;
  }
  const pct = Math.min(100, Math.max(0, (valueNumber / maxNumber) * 100));
  return (
    <div className="h-1.5 w-24 rounded-full bg-foreground/5 overflow-hidden">
      <div
        className="h-full rounded-full bg-success"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

export default function AdminEarningsPage() {
  const query = useAdminEarningsQuery();

  const maxStoreCommission = query.data
    ? query.data.by_store.reduce(
        (acc, row) => Math.max(acc, Number(row.commission)),
        0,
      )
    : 0;

  return (
    <div
      className="px-4 py-5 md:px-8 md:py-7 max-w-[1320px] mx-auto w-full space-y-5 md:space-y-6"
      data-testid="admin-earnings-page"
    >
      <PageHeader />

      {query.isPending ? <LoadingState /> : null}

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
          <section className="grid gap-3 md:gap-4 grid-cols-1 lg:grid-cols-[2fr_1fr]">
            <EarningsHeroCard
              eyebrow="Commission earned"
              value={query.data.commission_total}
              description={`${query.data.delivered_orders} delivered orders · 20% of gross base across all stores`}
              composition={[
                {
                  label: "Product subtotal",
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
                  label: "Commission (yours)",
                  amount: query.data.commission_total,
                  highlight: true,
                },
              ]}
              data-testid="admin-earnings-commission"
            />
            <div className="grid grid-cols-1 gap-3 md:gap-4">
              <MoneyTile
                title="Gross base"
                value={query.data.gross_base_total}
                description="Subtotal + delivery + tip + tax"
                icon={Wallet}
                data-testid="admin-earnings-gross-base"
              />
              <MoneyTile
                title="Customer paid"
                value={query.data.customer_paid_total}
                description="What customers were charged total"
                icon={Coins}
                data-testid="admin-earnings-customer-paid"
              />
            </div>
          </section>

          <section className="grid gap-3 md:gap-4 grid-cols-2 lg:grid-cols-4">
            <MoneyTile
              title="Subtotal (products)"
              value={query.data.subtotal_total}
              description="Sum of all product subtotals"
              icon={Receipt}
              data-testid="admin-earnings-subtotal"
            />
            <MoneyTile
              title="Delivery collected"
              value={query.data.delivery_total}
              description={`${formatUsd(query.data.delivery_fee)} per order`}
              icon={Truck}
              data-testid="admin-earnings-delivery"
            />
            <MoneyTile
              title="Taxes collected"
              value={query.data.tax_total}
              description="Pass-through taxes"
              icon={Wallet}
              data-testid="admin-earnings-tax"
            />
            <MoneyTile
              title="Tips collected"
              value={query.data.tip_total}
              description="Currently $0 — tips not tracked yet"
              icon={Coins}
              data-testid="admin-earnings-tip"
            />
          </section>

          <section
            className="rounded-xl border border-border bg-card overflow-hidden"
            data-testid="admin-earnings-by-store"
            aria-label="Earnings by store"
          >
            <div className="p-5 md:p-6 border-b border-border">
              <h2 className="text-base font-semibold">Earnings by store</h2>
              <p className="mt-1 text-sm text-muted-foreground">
                Top {query.data.by_store.length} stores by commission.
                Commission = 20% of (subtotal + delivery + tip + tax).
              </p>
            </div>
            {query.data.by_store.length === 0 ? (
              <p
                className="p-5 md:p-6 text-sm text-muted-foreground"
                data-testid="admin-earnings-by-store-empty"
              >
                No delivered orders yet.
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-secondary/40 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                    <tr>
                      <th className="px-5 py-3 text-left">Store</th>
                      <th className="px-5 py-3 text-right">Delivered orders</th>
                      <th className="px-5 py-3 text-right">Gross base</th>
                      <th className="px-5 py-3 text-right">Share</th>
                      <th className="px-5 py-3 text-right">Commission</th>
                    </tr>
                  </thead>
                  <tbody>
                    {query.data.by_store.map((row) => (
                      <tr
                        key={row.store_id}
                        className="border-t border-border"
                        data-testid={`admin-earnings-row-${row.store_id}`}
                      >
                        <td className="px-5 py-3 font-medium">
                          {row.store_name}
                        </td>
                        <td className="px-5 py-3 text-right tabular-nums">
                          {row.delivered_orders}
                        </td>
                        <td className="px-5 py-3 text-right tabular-nums">
                          {formatUsd(row.gross_base)}
                        </td>
                        <td className="px-5 py-3">
                          <div className="flex justify-end">
                            <StoreShareBar
                              value={row.commission}
                              max={String(maxStoreCommission)}
                            />
                          </div>
                        </td>
                        <td className="px-5 py-3 text-right tabular-nums font-semibold text-success">
                          {formatUsd(row.commission)}
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
