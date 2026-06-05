// F2.7.2 / F2.7.3: order detail page.
//
// Read-only in this subphase. Cancel, return, status transitions and
// any other action UI intentionally remain out of scope; mutation
// hooks already exist (F2.7.0) and will plug in via dedicated modals
// in a later subphase.
//
// Rendering structure:
//   - PageHeader with back-link to /app/store/orders
//   - SummaryCard (id, status, totals, timestamps, customer, notes)
//   - ItemsTable (line items with variant + product enrichment)
//   - OrderAuditLogsPanel (F2.7.3 — extracted to its own component;
//     owns its own data fetch via useOrderAuditLogs(orderId), so a
//     slow audit log query does not block the order detail render)
//
// Hard rules in force:
//   - No fetch, no Zustand, no mutations, no status transitions.
//   - useOrder is called unconditionally before any return (Rules of
//     Hooks intact); `enabled: orderId.length > 0` inside the hook
//     keeps the network silent when the route param is missing.
//   - No business logic: nullable fields render as em-dashes, no
//     calculations, no client-side formatting beyond raw display.

import { ArrowLeft, ClipboardList } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { getApiErrorMessage } from "@/api";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { OrderActionsBar } from "../components/OrderActionsBar";
import { OrderAuditLogsPanel } from "../components/OrderAuditLogsPanel";
import { useOrder } from "../hooks";
import { orderStatusLabel } from "../labels";
import type { OrderItemRead, OrderRead } from "../types";

const EM_DASH = "—";

function nullableText(value: string | null | undefined): string {
  return value === null || value === undefined || value === ""
    ? EM_DASH
    : value;
}

// --------------------------------------------------------------------- //
// Sub-components
// --------------------------------------------------------------------- //

function PageHeader({ orderId }: { orderId: string }) {
  return (
    <header className="flex flex-col gap-3">
      <Button variant="ghost" size="sm" asChild className="self-start">
        <Link to="/app/store/orders" data-testid="order-detail-back">
          <ArrowLeft className="mr-2 h-4 w-4" aria-hidden="true" />
          Back to orders
        </Link>
      </Button>
      <div>
        <h1 className="text-xl font-semibold">Order detail</h1>
        <p className="font-mono text-xs text-muted-foreground break-all">
          {orderId}
        </p>
      </div>
    </header>
  );
}

function SummaryCard({ order }: { order: OrderRead }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Summary</CardTitle>
        <CardDescription>Order summary and totals.</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-1 gap-4 text-sm md:grid-cols-2">
          <SummaryField label="Status">
            <span className="text-xs uppercase tracking-wide text-muted-foreground">
              {orderStatusLabel(order.status)}
            </span>
          </SummaryField>
          <SummaryField label="Customer">
            <span className="font-mono text-xs">
              {nullableText(order.customer_user_id)}
            </span>
          </SummaryField>
          <SummaryField label="Subtotal">
            <span className="tabular-nums">{order.subtotal_amount}</span>
          </SummaryField>
          <SummaryField label="Tax">
            <span className="tabular-nums">{order.tax_amount}</span>
          </SummaryField>
          <SummaryField label="Total">
            <span className="tabular-nums font-medium">
              {order.total_amount}
            </span>
          </SummaryField>
          <SummaryField label="Order reference">
            <span className="font-mono text-xs break-all">
              {order.idempotency_key}
            </span>
          </SummaryField>
          <SummaryField label="Created at">
            <span className="whitespace-nowrap">{order.created_at}</span>
          </SummaryField>
          <SummaryField label="Updated at">
            <span className="whitespace-nowrap">{order.updated_at}</span>
          </SummaryField>
          <SummaryField label="Notes" wide>
            <span className="whitespace-pre-wrap">
              {nullableText(order.notes)}
            </span>
          </SummaryField>
        </div>
      </CardContent>
    </Card>
  );
}

function SummaryField({
  label,
  wide,
  children,
}: {
  label: string;
  wide?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div className={wide ? "md:col-span-2" : undefined}>
      <p className="text-xs uppercase tracking-wide text-muted-foreground">
        {label}
      </p>
      <div className="mt-1">{children}</div>
    </div>
  );
}

function ItemsTable({ items }: { items: OrderItemRead[] }) {
  if (items.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Items</CardTitle>
        </CardHeader>
        <CardContent>
          <EmptyState
            icon={ClipboardList}
            title="No items"
            message="This order has no line items."
          />
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Items</CardTitle>
        <CardDescription>
          Line items snapshot from order creation.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <div className="rounded-b-md border-t border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead>SKU</TableHead>
                <TableHead>Flavor</TableHead>
                <TableHead>Size</TableHead>
                <TableHead className="text-right">Quantity</TableHead>
                <TableHead className="text-right">Unit price</TableHead>
                <TableHead className="text-right">Line total</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  <TableCell className="font-medium">
                    {item.variant.product.name}
                  </TableCell>
                  <TableCell className="font-mono text-xs">
                    {item.variant.sku}
                  </TableCell>
                  <TableCell>{nullableText(item.variant.flavor)}</TableCell>
                  <TableCell>
                    {nullableText(item.variant.size_label)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {item.quantity}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">
                    {item.unit_price}
                  </TableCell>
                  <TableCell className="text-right tabular-nums font-medium">
                    {item.line_total}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
}

// --------------------------------------------------------------------- //
// Page
// --------------------------------------------------------------------- //

export default function OrderDetailPage() {
  // useParams is typed permissively; the param is `string | undefined`
  // because React Router cannot prove the URL matched a parent route
  // that defines `:orderId`. We narrow defensively.
  const params = useParams<{ orderId: string }>();
  const orderId = params.orderId ?? "";

  // Always called: the hook short-circuits via `enabled: orderId.length > 0`.
  // The audit-logs query lives inside OrderAuditLogsPanel so it only fires
  // when we have an order to display logs for.
  const orderQuery = useOrder(orderId);

  // ------------------------- render branches ------------------------- //

  if (orderId.length === 0) {
    return (
      <div className="p-6 md:p-8 space-y-6 max-w-7xl">
        <PageHeader orderId={EM_DASH} />
        <ErrorState
          title="Missing order id"
          message="The route did not provide a valid order id."
        />
      </div>
    );
  }

  if (orderQuery.isLoading) {
    return (
      <div className="p-6 md:p-8 space-y-6 max-w-7xl">
        <PageHeader orderId={orderId} />
        <LoadingState message="Loading order..." />
      </div>
    );
  }

  if (orderQuery.isError) {
    return (
      <div className="p-6 md:p-8 space-y-6 max-w-7xl">
        <PageHeader orderId={orderId} />
        <ErrorState
          title="Order failed to load"
          message={getApiErrorMessage(orderQuery.error)}
          onRetry={() => orderQuery.refetch()}
        />
      </div>
    );
  }

  if (!orderQuery.data) {
    return (
      <div className="p-6 md:p-8 space-y-6 max-w-7xl">
        <PageHeader orderId={orderId} />
        <EmptyState
          icon={ClipboardList}
          title="Order not found"
          message="We couldn't find this order. It may have been removed."
        />
      </div>
    );
  }

  const order = orderQuery.data;

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl">
      <PageHeader orderId={orderId} />
      <OrderActionsBar order={order} />
      <SummaryCard order={order} />
      <ItemsTable items={order.items} />
      <OrderAuditLogsPanel orderId={order.id} />
    </div>
  );
}
