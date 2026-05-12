// Operational home for the /app/store dashboard.
//
// Each operational widget consumes a real backend list endpoint
// (inventory, orders, products, store-scoped inventory logs).
// Aggregate KPIs / store-wide summaries are NOT computed in the
// frontend — those need backend summary endpoints that do not exist
// yet, so BackendRequiredSection calls that gap out explicitly rather
// than faking metrics, charts, scores, or a unified activity feed.

import {
  AlertTriangle,
  ArrowRight,
  Boxes,
  ClipboardList,
  LayoutDashboard,
  ListChecks,
  PackageSearch,
  Plus,
  Server,
  Settings,
  ShieldCheck,
  ShoppingBag,
  UserPlus,
  type LucideIcon,
} from "lucide-react";
import { Link } from "react-router-dom";

import { getApiErrorMessage } from "@/api";
import { useStoreContext } from "@/auth";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { useStoreInventoryLogsQuery } from "@/features/audit/hooks";
import type { StoreInventoryLogEntry } from "@/features/audit/types";
import { useInventoryList } from "@/features/inventory/hooks";
import type { InventoryItem } from "@/features/inventory/types";
import { useOrdersList } from "@/features/orders/hooks";
import type { OrderRead } from "@/features/orders/types";
import { ProductComplianceBadge } from "@/features/products/components/ProductComplianceBadge";
import { ProductStatusBadge } from "@/features/products/components/ProductStatusBadge";
import { useProductsQuery } from "@/features/products/hooks";
import type { Product } from "@/features/products/types";

const FUTURE_ENDPOINTS: ReadonlyArray<string> = [
  "GET /stores/:storeId/dashboard",
  "GET /stores/:storeId/dashboard/kpis",
  "GET /stores/:storeId/orders/summary",
  "GET /stores/:storeId/inventory/summary",
  "GET /stores/:storeId/products/summary",
  "GET /stores/:storeId/activity",
  "GET /stores/:storeId/alerts",
];

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

function PageHeader() {
  return (
    <header className="space-y-2">
      <div className="flex items-center gap-2">
        <LayoutDashboard
          className="h-5 w-5 text-muted-foreground"
          aria-hidden="true"
        />
        <h1 className="text-xl font-semibold">Store Dashboard</h1>
      </div>
      <p className="text-sm font-medium text-foreground">
        Operational home for this store
      </p>
      <p className="text-sm text-muted-foreground">
        Review orders, inventory, product review items, and recent inventory
        activity for this store.
      </p>
    </header>
  );
}

function QuickActionTile({ action }: { action: QuickAction }) {
  const Icon = action.icon;

  return (
    <Link
      to={action.href}
      data-testid={action.testId}
      className="group flex items-start gap-3 rounded-md border border-border p-3 text-left transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <span
        className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground group-hover:bg-background"
        aria-hidden="true"
      >
        <Icon className="h-4 w-4" />
      </span>
      <span className="min-w-0 flex-1 space-y-1">
        <span className="block text-sm font-medium leading-tight">
          {action.title}
        </span>
        <span className="block text-xs text-muted-foreground">
          {action.description}
        </span>
      </span>
      <ArrowRight
        className="mt-1 h-4 w-4 shrink-0 text-muted-foreground transition-transform group-hover:translate-x-0.5"
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

function LowStockInventoryList({ items }: { items: InventoryItem[] }) {
  return (
    <ul
      className="divide-y divide-border"
      data-testid="dashboard-low-stock-list"
    >
      {items.map((item) => (
        <li
          key={item.id}
          className="flex items-start justify-between gap-4 py-3 first:pt-0 last:pb-0"
          data-testid="dashboard-low-stock-item"
        >
          <div className="min-w-0 space-y-1">
            <p className="truncate text-sm font-medium leading-tight">
              {item.variant.product.name}
            </p>
            <p className="font-mono text-xs text-muted-foreground">
              {item.variant.sku}
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-3 text-xs">
            <span className="tabular-nums">
              <span className="font-medium">{item.quantity_on_hand}</span>
              <span className="text-muted-foreground">
                {" "}
                / {item.reorder_threshold}
              </span>
            </span>
            <span className="uppercase tracking-wide text-muted-foreground">
              {item.status}
            </span>
          </div>
        </li>
      ))}
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
          <Link
            to="/app/store/inventory"
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

function OrdersToReviewList({ orders }: { orders: OrderRead[] }) {
  return (
    <ul
      className="divide-y divide-border"
      data-testid="dashboard-orders-to-review-list"
    >
      {orders.map((order) => (
        <li
          key={order.id}
          className="py-3 first:pt-0 last:pb-0"
          data-testid="dashboard-orders-to-review-item"
        >
          <Link
            to={`/app/store/orders/${order.id}`}
            data-testid="dashboard-orders-to-review-item-link"
            className="-mx-2 flex items-start justify-between gap-4 rounded-md px-2 py-1 transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <div className="min-w-0 space-y-1">
              <p className="truncate font-mono text-xs">{order.id}</p>
              <p className="text-xs text-muted-foreground">
                {order.created_at}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-3 text-xs">
              <span className="tabular-nums text-muted-foreground">
                {order.items.length}{" "}
                {order.items.length === 1 ? "item" : "items"}
              </span>
              <span className="uppercase tracking-wide text-muted-foreground">
                {order.status}
              </span>
            </div>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function OrdersToReviewSection() {
  const query = useOrdersList({
    limit: 5,
    offset: 0,
  });

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
            className="-mx-2 flex items-start justify-between gap-4 rounded-md px-2 py-1 transition-colors hover:bg-accent hover:text-accent-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          >
            <div className="min-w-0 space-y-1">
              <p className="truncate text-sm font-medium leading-tight">
                {product.name}
              </p>
              <p className="truncate text-xs text-muted-foreground">
                {product.brand ? `${product.brand} · ` : ""}
                {product.category}
              </p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
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
  const query = useProductsQuery({ limit: 5 });

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
            message="No product review items returned by the current filters."
          />
        ) : query.data ? (
          <ProductReviewList products={query.data} />
        ) : null}
      </CardContent>
    </Card>
  );
}

function RecentInventoryActivityList({
  logs,
}: {
  logs: StoreInventoryLogEntry[];
}) {
  return (
    <ul
      className="divide-y divide-border"
      data-testid="dashboard-inventory-activity-list"
    >
      {logs.map((log) => (
        <li
          key={log.id}
          className="flex items-start justify-between gap-4 py-3 first:pt-0 last:pb-0"
          data-testid="dashboard-inventory-activity-item"
        >
          <div className="min-w-0 space-y-1">
            <p className="text-sm font-medium uppercase tracking-wide text-muted-foreground">
              {log.movement_type}
            </p>
            <p className="text-xs text-muted-foreground">
              {log.created_at}
            </p>
            {log.reason ? (
              <p className="truncate text-xs text-muted-foreground">
                {log.reason}
              </p>
            ) : null}
          </div>
          <div className="flex shrink-0 items-center gap-3 text-xs tabular-nums">
            <span className="font-mono">
              {SIGNED_QTY_FORMAT.format(log.quantity_delta)}
            </span>
            <span className="text-muted-foreground">
              after {log.quantity_after}
            </span>
          </div>
        </li>
      ))}
    </ul>
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
            icon={ListChecks}
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

function BackendRequiredSection() {
  return (
    <Card data-testid="dashboard-backend-summary">
      <CardHeader>
        <div className="flex items-center gap-2">
          <Server
            className="h-4 w-4 text-muted-foreground"
            aria-hidden="true"
          />
          <CardTitle className="text-base">
            Dashboard summaries require backend support
          </CardTitle>
        </div>
        <CardDescription>
          The widgets above use real list endpoints (inventory, orders,
          products, inventory activity). Aggregate KPIs and store-wide
          summaries need backend endpoints that do not exist yet — the
          frontend does not simulate them.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <Alert>
          <AlertTriangle className="h-4 w-4" aria-hidden="true" />
          <AlertTitle>Dashboard summaries require backend support.</AlertTitle>
          <AlertDescription>
            No KPIs are simulated in the frontend.
          </AlertDescription>
        </Alert>
        <div className="space-y-2">
          <h4 className="text-sm font-semibold">Future backend endpoints</h4>
          <ul
            className="list-disc space-y-1 pl-5 text-sm text-muted-foreground"
            data-testid="dashboard-future-endpoints"
          >
            {FUTURE_ENDPOINTS.map((endpoint) => (
              <li key={endpoint}>
                <code className="font-mono text-xs">{endpoint}</code>
              </li>
            ))}
          </ul>
        </div>
      </CardContent>
    </Card>
  );
}

export default function DashboardHomePage() {
  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl">
      <PageHeader />

      <QuickActionsSection />

      <div className="grid gap-6 lg:grid-cols-2">
        <LowStockInventorySection />

        <OrdersToReviewSection />

        <ProductReviewSection />

        <RecentInventoryActivitySection />
      </div>

      <BackendRequiredSection />
    </div>
  );
}
