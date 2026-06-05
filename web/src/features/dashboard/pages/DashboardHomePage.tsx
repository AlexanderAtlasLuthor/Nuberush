// Store operations home for /app/store.
//
// Widgets:
//   - KPI strip (key metrics) — backed by /stores/:storeId/dashboard/kpis
//   - Operational alerts      — backed by /stores/:storeId/alerts
//   - Quick actions           — static nav tiles
//   - Low-stock inventory     — backed by /stores/:storeId/inventory?low_stock_only
//   - Orders to review        — backed by /stores/:storeId/orders
//   - Product review          — backed by /products?only_blocked
//   - Recent inventory activity — backed by /stores/:storeId/inventory/logs
//
// Every value displayed is a real wire field; nothing on this page is
// simulated.

import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Boxes,
  ClipboardList,
  Inbox,
  ListChecks,
  PackageSearch,
  Plus,
  Settings,
  ShieldCheck,
  ShoppingBag,
  User as UserIcon,
  UserPlus,
  type LucideIcon,
} from "lucide-react";
import { Link } from "react-router-dom";

import { getApiErrorMessage } from "@/api";
import { useStoreContext } from "@/auth";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { cn } from "@/lib/utils";
import {
  useStoreAlertsQuery,
  useStoreDashboardKpisQuery,
} from "@/features/dashboard";
import type {
  StoreAlert,
  StoreAlertSeverity,
  StoreDashboardKpis,
} from "@/features/dashboard";
import { useStoreInventoryLogsQuery } from "@/features/audit/hooks";
import type { StoreInventoryLogEntry } from "@/features/audit/types";
import { useInventoryList } from "@/features/inventory/hooks";
import type { InventoryItem } from "@/features/inventory/types";
import { useOrdersList } from "@/features/orders/hooks";
import { orderStatusLabel } from "@/features/orders/labels";
import type { OrderRead, OrderStatus } from "@/features/orders/types";
import { ProductComplianceBadge } from "@/features/products/components/ProductComplianceBadge";
import { ProductStatusBadge } from "@/features/products/components/ProductStatusBadge";
import { useProductsQuery } from "@/features/products/hooks";
import type { Product } from "@/features/products/types";
import { StoreEarningsWidget } from "@/features/store-earnings/components/StoreEarningsWidget";

const SIGNED_QTY_FORMAT = new Intl.NumberFormat("en-US", {
  signDisplay: "exceptZero",
});

interface QuickAction {
  title: string;
  description: string;
  href: string;
  icon: LucideIcon;
  testId: string;
}

const QUICK_ACTIONS: ReadonlyArray<QuickAction> = [
  {
    testId: "quick-action-create-order",
    title: "Create order",
    description: "Start a store order workflow.",
    href: "/app/store/orders/new",
    icon: Plus,
  },
  {
    testId: "quick-action-view-orders",
    title: "View orders",
    description: "Review and manage store orders.",
    href: "/app/store/orders",
    icon: ClipboardList,
  },
  {
    testId: "quick-action-view-inventory",
    title: "View inventory",
    description: "Check stock levels and inventory actions.",
    href: "/app/store/inventory",
    icon: Boxes,
  },
  {
    testId: "quick-action-view-products",
    title: "View products",
    description: "Review product catalog and compliance status.",
    href: "/app/store/products",
    icon: ShoppingBag,
  },
  {
    testId: "quick-action-create-store-user",
    title: "Create store user",
    description: "Manage store user access.",
    href: "/app/store/users",
    icon: UserPlus,
  },
  {
    testId: "quick-action-view-audit",
    title: "View audit",
    description: "Review inventory and operational audit records.",
    href: "/app/store/audit",
    icon: ShieldCheck,
  },
  {
    testId: "quick-action-store-settings",
    title: "Store settings",
    description: "Manage store configuration.",
    href: "/app/store/settings",
    icon: Settings,
  },
];

const ORDER_STATUS_PILL_CLASS: Record<OrderStatus, string> = {
  pending: "bg-secondary text-muted-foreground",
  accepted: "bg-primary/15 text-primary",
  preparing: "bg-primary/15 text-primary",
  ready: "bg-primary/15 text-primary",
  out_for_delivery: "bg-warning/15 text-warning",
  delivered: "bg-success/15 text-success",
  canceled: "bg-destructive/15 text-destructive",
  returned: "bg-muted text-muted-foreground",
};

const MOVEMENT_DOT_CLASS: Record<string, string> = {
  receipt: "bg-success",
  adjustment: "bg-warning",
  sale: "bg-primary",
  return: "bg-muted-foreground/70",
  transfer: "bg-primary/70",
  reserve: "bg-secondary",
  release: "bg-secondary",
};

function movementDotClass(movementType: string): string {
  return MOVEMENT_DOT_CLASS[movementType] ?? "bg-muted-foreground/60";
}

const SEVERITY_BADGE_CLASS: Record<StoreAlertSeverity, string> = {
  high: "bg-destructive/15 text-destructive",
  medium: "bg-warning/15 text-warning",
  low: "bg-muted text-muted-foreground",
};

function PageHeader() {
  return (
    <header>
      <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        Store · Operations
      </p>
      <h1 className="mt-1.5 text-2xl font-semibold tracking-tight md:text-[28px]">
        Store Dashboard
      </h1>
      <p className="mt-1.5 text-sm font-medium text-foreground">
        Operational home for this store
      </p>
      <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground leading-relaxed">
        Review orders, inventory, product review items, and recent inventory
        activity for this store.
      </p>
    </header>
  );
}

// --------------------------------------------------------------------- //
// KPI strip
// --------------------------------------------------------------------- //

interface KpiTileProps {
  label: string;
  value: number | string;
  hint?: string;
  tone?: "default" | "warning" | "destructive" | "success";
  testId: string;
}

function KpiTile({ label, value, hint, tone = "default", testId }: KpiTileProps) {
  const toneClass =
    tone === "destructive"
      ? "text-destructive"
      : tone === "warning"
        ? "text-warning"
        : tone === "success"
          ? "text-success"
          : "text-foreground";
  return (
    <div
      data-testid={testId}
      className="flex flex-col gap-1 rounded-xl border border-border bg-card p-4"
    >
      <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </span>
      <span
        className={cn(
          "text-2xl font-semibold tabular-nums leading-tight",
          toneClass,
        )}
      >
        {value}
      </span>
      {hint ? (
        <span className="text-xs text-muted-foreground">{hint}</span>
      ) : null}
    </div>
  );
}

function KpiStripContent({ kpis }: { kpis: StoreDashboardKpis }) {
  const lowStockTone =
    kpis.inventory_low_stock > 0 ? "warning" : "success";
  const blockedTone =
    kpis.products_blocked > 0 ? "destructive" : "default";
  return (
    <div
      className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
      data-testid="dashboard-kpi-grid"
    >
      <KpiTile
        testId="dashboard-kpi-orders-open"
        label="Open orders"
        value={kpis.orders_open}
        hint="Pending through out-for-delivery"
      />
      <KpiTile
        testId="dashboard-kpi-low-stock"
        label="Low-stock items"
        value={kpis.inventory_low_stock}
        hint={`of ${kpis.inventory_total_items} tracked`}
        tone={lowStockTone}
      />
      <KpiTile
        testId="dashboard-kpi-products"
        label="Products in store"
        value={kpis.products_in_store}
      />
      <KpiTile
        testId="dashboard-kpi-blocked"
        label="Blocked products"
        value={kpis.products_blocked}
        hint="Restricted or banned"
        tone={blockedTone}
      />
    </div>
  );
}

function KpiStripSection() {
  const { currentStoreId } = useStoreContext();
  const query = useStoreDashboardKpisQuery({ storeId: currentStoreId });

  return (
    <Card data-testid="dashboard-kpis">
      <CardHeader>
        <CardTitle className="text-base">Key metrics</CardTitle>
        <CardDescription>
          Live counts pulled from inventory, orders, and product compliance.
        </CardDescription>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <LoadingState message="Loading metrics…" />
        ) : query.isError ? (
          <ErrorState
            title="Metrics failed to load."
            message={getApiErrorMessage(query.error)}
            onRetry={() => query.refetch()}
          />
        ) : query.data ? (
          <KpiStripContent kpis={query.data} />
        ) : null}
      </CardContent>
    </Card>
  );
}

// --------------------------------------------------------------------- //
// Operational alerts
// --------------------------------------------------------------------- //

function AlertRow({ alert }: { alert: StoreAlert }) {
  return (
    <li
      className="flex items-start justify-between gap-4 py-3 first:pt-0 last:pb-0"
      data-testid="dashboard-alert-item"
    >
      <div className="min-w-0 flex-1 space-y-1">
        <p className="text-sm font-medium leading-tight">
          {alert.summary}
        </p>
        <p className="text-[11px] uppercase tracking-wider text-muted-foreground">
          {alert.category.replace(/_/g, " ")}
        </p>
      </div>
      <Badge
        variant="outline"
        className={cn(
          "shrink-0 border-0 text-[11px] font-medium uppercase",
          SEVERITY_BADGE_CLASS[alert.severity],
        )}
      >
        {alert.severity}
      </Badge>
    </li>
  );
}

function OperationalAlertsSection() {
  const { currentStoreId } = useStoreContext();
  const query = useStoreAlertsQuery({
    storeId: currentStoreId,
    limit: 5,
  });

  const total = query.data?.total ?? 0;
  return (
    <Card data-testid="dashboard-alerts">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-1">
          <CardTitle className="text-base flex items-center gap-2">
            <AlertCircle
              className="h-4 w-4 text-warning"
              aria-hidden="true"
            />
            Operational alerts
            {total > 0 ? (
              <Badge
                variant="secondary"
                className="ml-1 text-[11px]"
                data-testid="dashboard-alerts-total"
              >
                {total}
              </Badge>
            ) : null}
          </CardTitle>
          <CardDescription>
            Low-stock items, aging orders, and store-level issues
            computed live by the backend.
          </CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <LoadingState message="Loading alerts…" />
        ) : query.isError ? (
          <ErrorState
            title="Alerts failed to load."
            message={getApiErrorMessage(query.error)}
            onRetry={() => query.refetch()}
          />
        ) : query.data && query.data.items.length === 0 ? (
          <EmptyState
            icon={ShieldCheck}
            title="No active alerts"
            message="Nothing requires attention right now."
          />
        ) : query.data ? (
          <ul
            className="divide-y divide-border"
            data-testid="dashboard-alerts-list"
          >
            {query.data.items.map((alert) => (
              <AlertRow key={alert.id} alert={alert} />
            ))}
          </ul>
        ) : null}
      </CardContent>
    </Card>
  );
}

// --------------------------------------------------------------------- //
// Quick actions
// --------------------------------------------------------------------- //

function QuickActionTile({ action }: { action: QuickAction }) {
  const Icon = action.icon;
  return (
    <Link
      to={action.href}
      data-testid={action.testId}
      className="group flex items-start gap-3 rounded-xl border border-border bg-card p-4 text-left transition-colors hover:bg-secondary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <span
        className="mt-0.5 inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/15 text-primary"
        aria-hidden="true"
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1 space-y-1">
        <span className="block text-sm font-medium leading-tight">
          {action.title}
        </span>
        <span className="block text-xs text-muted-foreground leading-snug">
          {action.description}
        </span>
      </span>
      <ArrowRight
        className="mt-1.5 h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
        aria-hidden="true"
      />
    </Link>
  );
}

function QuickActionsSection() {
  return (
    <Card data-testid="dashboard-quick-actions">
      <CardHeader>
        <CardTitle className="text-base">Quick actions</CardTitle>
        <CardDescription>
          Shortcuts to operational areas in this store.
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {QUICK_ACTIONS.map((action) => (
            <QuickActionTile key={action.href} action={action} />
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

// --------------------------------------------------------------------- //
// Low-stock inventory
// --------------------------------------------------------------------- //

function depletionPercent(onHand: number, threshold: number): number {
  if (threshold <= 0) return 0;
  const ratio = (onHand / threshold) * 100;
  if (Number.isNaN(ratio)) return 0;
  return Math.max(0, Math.min(100, ratio));
}

function depletionTone(percent: number): string {
  if (percent < 25) return "bg-destructive";
  if (percent < 60) return "bg-warning";
  return "bg-primary";
}

function LowStockInventoryList({ items }: { items: InventoryItem[] }) {
  return (
    <ul
      className="divide-y divide-border"
      data-testid="dashboard-low-stock-list"
    >
      {items.map((item) => {
        const percent = depletionPercent(
          item.quantity_on_hand,
          item.reorder_threshold,
        );
        const tone = depletionTone(percent);
        return (
          <li
            key={item.id}
            className="flex items-center gap-4 py-3 first:pt-0 last:pb-0"
            data-testid="dashboard-low-stock-item"
          >
            <div className="min-w-0 flex-1 space-y-1.5">
              <p className="truncate text-sm font-medium leading-tight">
                {item.variant.product.name}
              </p>
              <p className="font-mono text-xs text-muted-foreground">
                {item.variant.sku}
              </p>
              <div
                className="h-1 w-full overflow-hidden rounded-full bg-secondary/60"
                role="presentation"
                aria-hidden="true"
              >
                <div
                  className={cn("h-full", tone)}
                  style={{ width: `${percent}%` }}
                />
              </div>
            </div>
            <div className="flex shrink-0 flex-col items-end gap-1 text-xs">
              <span className="tabular-nums">
                <span className="text-sm font-semibold">
                  {item.quantity_on_hand}
                </span>
                <span className="text-muted-foreground">
                  {" "}
                  / {item.reorder_threshold}
                </span>
              </span>
              <span className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
                {item.status}
              </span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function LowStockInventorySection() {
  const query = useInventoryList({
    limit: 5,
    offset: 0,
    low_stock_only: true,
  });

  return (
    <Card data-testid="dashboard-low-stock">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-1">
          <CardTitle className="text-base">Low-stock inventory</CardTitle>
          <CardDescription>
            Inventory items at or below their reorder threshold.
          </CardDescription>
        </div>
        <Button variant="ghost" size="sm" asChild>
          {/* The link carries the filter as a URL search param so the
              inventory page can seed its initial filter state from the
              URL — clicking "View all" lands the user on a pre-filtered
              list instead of the unfiltered default. */}
          <Link
            to="/app/store/inventory?low_stock_only=true"
            data-testid="dashboard-low-stock-link"
          >
            View all
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <LoadingState message="Loading low-stock inventory…" />
        ) : query.isError ? (
          <ErrorState
            title="Low-stock inventory failed to load."
            message={getApiErrorMessage(query.error)}
            onRetry={() => query.refetch()}
          />
        ) : query.data && query.data.items.length === 0 ? (
          <EmptyState
            icon={Boxes}
            title="No low-stock items"
            message="No low-stock inventory returned by the current filters."
          />
        ) : query.data ? (
          <LowStockInventoryList items={query.data.items} />
        ) : null}
      </CardContent>
    </Card>
  );
}

// --------------------------------------------------------------------- //
// Orders to review
// --------------------------------------------------------------------- //

function OrdersToReviewList({ orders }: { orders: OrderRead[] }) {
  return (
    <ul
      className="divide-y divide-border"
      data-testid="dashboard-orders-to-review-list"
    >
      {orders.map((order) => {
        const pillClass =
          ORDER_STATUS_PILL_CLASS[order.status] ??
          "bg-secondary text-muted-foreground";
        return (
          <li
            key={order.id}
            className="py-3 first:pt-0 last:pb-0"
            data-testid="dashboard-orders-to-review-item"
          >
            <Link
              to={`/app/store/orders/${order.id}`}
              data-testid="dashboard-orders-to-review-item-link"
              className="-mx-2 flex items-start justify-between gap-4 rounded-md px-2 py-1 transition-colors hover:bg-secondary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            >
              <div className="min-w-0 flex-1 space-y-1">
                <p className="truncate font-mono text-xs">{order.id}</p>
                <p className="text-xs text-muted-foreground">
                  {order.created_at}
                </p>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-1 text-xs">
                <span
                  className={cn(
                    "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
                    pillClass,
                  )}
                >
                  {orderStatusLabel(order.status)}
                </span>
                <span className="tabular-nums text-muted-foreground">
                  {order.items.length}{" "}
                  {order.items.length === 1 ? "item" : "items"}
                </span>
              </div>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

function OrdersToReviewSection() {
  const query = useOrdersList({ limit: 5, offset: 0 });

  return (
    <Card data-testid="dashboard-orders-to-review">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-1">
          <CardTitle className="text-base">Orders to review</CardTitle>
          <CardDescription>
            Orders awaiting acceptance or follow-up by store staff.
          </CardDescription>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link
            to="/app/store/orders"
            data-testid="dashboard-orders-to-review-link"
          >
            View all
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <LoadingState message="Loading orders to review…" />
        ) : query.isError ? (
          <ErrorState
            title="Orders to review failed to load."
            message={getApiErrorMessage(query.error)}
            onRetry={() => query.refetch()}
          />
        ) : query.data && query.data.items.length === 0 ? (
          <EmptyState
            icon={ClipboardList}
            title="No orders to review"
            message="No orders returned by the current dashboard query."
          />
        ) : query.data ? (
          <OrdersToReviewList orders={query.data.items} />
        ) : null}
      </CardContent>
    </Card>
  );
}

// --------------------------------------------------------------------- //
// Product review (compliance queue)
// --------------------------------------------------------------------- //

function ProductReviewList({ products }: { products: Product[] }) {
  return (
    <ul
      className="divide-y divide-border"
      data-testid="dashboard-product-review-list"
    >
      {products.map((product) => (
        <li
          key={product.id}
          className="py-3 first:pt-0 last:pb-0"
          data-testid="dashboard-product-review-item"
        >
          <Link
            to={`/app/store/products/${product.id}`}
            data-testid="dashboard-product-review-item-link"
            className="-mx-2 flex items-start justify-between gap-4 rounded-md px-2 py-1 transition-colors hover:bg-secondary/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <div className="min-w-0 flex-1 space-y-1">
              <p className="truncate text-sm font-medium leading-tight">
                {product.name}
              </p>
              <p className="truncate text-xs text-muted-foreground">
                {product.brand ? `${product.brand} · ` : ""}
                {product.category}
              </p>
            </div>
            <div className="flex shrink-0 flex-wrap items-center justify-end gap-1.5">
              <ProductStatusBadge isActive={product.is_active} />
              <ProductComplianceBadge status={product.compliance_status} />
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function ProductReviewSection() {
  // Backend predicate: allowed_for_sale=false OR compliance_status in
  // {restricted, banned}. Same set the dashboard `products_blocked`
  // KPI counts, so the widget and the KPI strip never disagree.
  const query = useProductsQuery({ only_blocked: true, limit: 5 });

  return (
    <Card data-testid="dashboard-product-review">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-1">
          <CardTitle className="text-base">Product review</CardTitle>
          <CardDescription>
            Products flagged for compliance or operational review.
          </CardDescription>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link
            to="/app/store/products"
            data-testid="dashboard-product-review-link"
          >
            View all
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <LoadingState message="Loading product review…" />
        ) : query.isError ? (
          <ErrorState
            title="Product review failed to load."
            message={getApiErrorMessage(query.error)}
            onRetry={() => query.refetch()}
          />
        ) : query.data && query.data.length === 0 ? (
          <EmptyState
            icon={PackageSearch}
            title="No product review items"
            message="No products are blocked from sale right now."
          />
        ) : query.data ? (
          <ProductReviewList products={query.data} />
        ) : null}
      </CardContent>
    </Card>
  );
}

// --------------------------------------------------------------------- //
// Recent inventory activity
// --------------------------------------------------------------------- //

function actorLabel(actorId: string | null): string {
  // `performed_by_user_id` is the only actor field on the wire (no
  // user-name resolution endpoint is consumed here). Show a short id
  // prefix when an actor is present so the operator can cross-reference
  // the audit page, and "SYSTEM" when null (movement happened with no
  // bound user — e.g. soft-deleted actor or background process).
  if (actorId === null || actorId.length === 0) return "SYSTEM";
  return actorId.slice(0, 8);
}

function RecentInventoryActivityList({
  logs,
}: {
  logs: StoreInventoryLogEntry[];
}) {
  return (
    <ol
      className="relative space-y-3 pl-5"
      data-testid="dashboard-inventory-activity-list"
    >
      <span
        aria-hidden="true"
        className="pointer-events-none absolute left-[5px] top-2 bottom-2 w-px bg-border"
      />
      {logs.map((log) => (
        <li
          key={log.id}
          className="relative flex items-start justify-between gap-4 text-sm"
          data-testid="dashboard-inventory-activity-item"
        >
          <span
            aria-hidden="true"
            className={cn(
              "absolute left-[-19px] top-1.5 h-2.5 w-2.5 rounded-full ring-4 ring-card shrink-0",
              movementDotClass(log.movement_type),
            )}
          />
          <div className="min-w-0 flex-1 space-y-0.5">
            <p className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
              {log.movement_type}
            </p>
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <UserIcon className="h-3 w-3" aria-hidden="true" />
              <span
                className="font-mono"
                data-testid="dashboard-inventory-activity-actor"
              >
                {actorLabel(log.performed_by_user_id)}
              </span>
              <span aria-hidden="true">·</span>
              <span>{log.created_at}</span>
            </p>
            {log.reason ? (
              <p className="truncate text-xs text-muted-foreground">
                {log.reason}
              </p>
            ) : null}
          </div>
          <div className="flex shrink-0 items-center gap-3 text-xs tabular-nums">
            <span className="font-mono font-semibold">
              {SIGNED_QTY_FORMAT.format(log.quantity_delta)}
            </span>
            <span className="text-muted-foreground">
              after {log.quantity_after}
            </span>
          </div>
        </li>
      ))}
    </ol>
  );
}

function RecentInventoryActivitySection() {
  const { currentStoreId } = useStoreContext();
  const query = useStoreInventoryLogsQuery({
    storeId: currentStoreId,
    limit: 5,
  });

  return (
    <Card data-testid="dashboard-inventory-activity">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div className="space-y-1">
          <CardTitle className="text-base">Recent inventory activity</CardTitle>
          <CardDescription>
            Recent stock adjustments and inventory log entries for this store.
          </CardDescription>
        </div>
        <Button variant="ghost" size="sm" asChild>
          <Link
            to="/app/store/audit"
            data-testid="dashboard-inventory-activity-link"
          >
            View audit
          </Link>
        </Button>
      </CardHeader>
      <CardContent>
        {query.isLoading ? (
          <LoadingState message="Loading recent inventory activity…" />
        ) : query.isError ? (
          <ErrorState
            title="Recent inventory activity failed to load."
            message={getApiErrorMessage(query.error)}
            onRetry={() => query.refetch()}
          />
        ) : query.data && query.data.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="No inventory activity"
            message="No inventory activity returned yet."
          />
        ) : query.data ? (
          <RecentInventoryActivityList logs={query.data} />
        ) : null}
      </CardContent>
    </Card>
  );
}

// --------------------------------------------------------------------- //
// Page
// --------------------------------------------------------------------- //

export default function DashboardHomePage() {
  return (
    <div className="px-4 py-5 md:px-8 md:py-7 max-w-[1320px] mx-auto w-full space-y-5 md:space-y-6">
      <PageHeader />

      <KpiStripSection />

      <StoreEarningsWidget />

      <OperationalAlertsSection />

      <QuickActionsSection />

      <div className="grid gap-4 lg:grid-cols-2 md:gap-5">
        <LowStockInventorySection />

        <OrdersToReviewSection />

        <ProductReviewSection />

        <RecentInventoryActivitySection />
      </div>
    </div>
  );
}
