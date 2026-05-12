// F2.7.1: real orders list page.
//
// Read-only in this subphase: detail, create, cancel, return and status
// actions intentionally remain out of scope.

import { useState } from "react";
import { ClipboardList, Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { getApiErrorMessage } from "@/api";
import { useStoreContext } from "@/auth";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { LoadingState } from "@/components/common/loading-state";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

import { useOrdersList } from "../hooks";
import type { OrderRead, OrderStatus } from "../types";

const DEFAULT_LIMIT = 20;
const ALL_STATUSES = "all";

const ORDER_STATUSES: OrderStatus[] = [
  "pending",
  "accepted",
  "preparing",
  "ready",
  "out_for_delivery",
  "delivered",
  "canceled",
  "returned",
];

function PageHeader() {
  return (
    <header className="flex items-center justify-between gap-4">
      <h1 className="text-xl font-semibold">Orders</h1>
      <Button asChild data-testid="orders-create-link">
        <Link to="/app/store/orders/new">
          <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
          Create order
        </Link>
      </Button>
    </header>
  );
}

interface FilterBarProps {
  status: OrderStatus | undefined;
  createdFrom: string;
  createdTo: string;
  disabled?: boolean;
  onStatusChange: (next: OrderStatus | undefined) => void;
  onCreatedFromChange: (next: string) => void;
  onCreatedToChange: (next: string) => void;
}

function FilterBar({
  status,
  createdFrom,
  createdTo,
  disabled,
  onStatusChange,
  onCreatedFromChange,
  onCreatedToChange,
}: FilterBarProps) {
  return (
    <div className="grid gap-4 md:grid-cols-[minmax(12rem,14rem)_minmax(12rem,16rem)_minmax(12rem,16rem)]">
      <div className="space-y-2">
        <Label htmlFor="orders-status">Status</Label>
        <Select
          value={status ?? ALL_STATUSES}
          disabled={disabled}
          onValueChange={(value) =>
            onStatusChange(
              value === ALL_STATUSES ? undefined : (value as OrderStatus),
            )
          }
        >
          <SelectTrigger id="orders-status">
            <SelectValue placeholder="All statuses" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value={ALL_STATUSES}>All statuses</SelectItem>
            {ORDER_STATUSES.map((option) => (
              <SelectItem key={option} value={option}>
                {option}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="space-y-2">
        <Label htmlFor="orders-created-from">Created from</Label>
        <Input
          id="orders-created-from"
          type="datetime-local"
          value={createdFrom}
          disabled={disabled}
          onChange={(event) => onCreatedFromChange(event.target.value)}
        />
      </div>

      <div className="space-y-2">
        <Label htmlFor="orders-created-to">Created to</Label>
        <Input
          id="orders-created-to"
          type="datetime-local"
          value={createdTo}
          disabled={disabled}
          onChange={(event) => onCreatedToChange(event.target.value)}
        />
      </div>
    </div>
  );
}

function OrdersTable({ orders }: { orders: OrderRead[] }) {
  return (
    <div className="rounded-md border border-border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Order ID</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Total</TableHead>
            <TableHead className="text-right">Items</TableHead>
            <TableHead>First item</TableHead>
            <TableHead>Created</TableHead>
            <TableHead className="w-20 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {orders.map((order) => {
            const firstItem = order.items[0];

            return (
              <TableRow key={order.id}>
                <TableCell className="max-w-56 break-all font-mono text-xs">
                  {order.id}
                </TableCell>
                <TableCell>
                  <span className="text-xs uppercase tracking-wide text-muted-foreground">
                    {order.status}
                  </span>
                </TableCell>
                <TableCell className="tabular-nums">
                  {order.total_amount}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {order.items.length}
                </TableCell>
                <TableCell>
                  {firstItem ? (
                    <div className="space-y-1">
                      <p className="font-medium">
                        {firstItem.variant.product.name}
                      </p>
                      <p className="font-mono text-xs text-muted-foreground">
                        {firstItem.variant.sku}
                      </p>
                    </div>
                  ) : (
                    <span className="text-sm text-muted-foreground">
                      No items
                    </span>
                  )}
                </TableCell>
                <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
                  {order.created_at}
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    variant="ghost"
                    size="sm"
                    asChild
                    data-testid="orders-row-view"
                  >
                    <Link to={`/app/store/orders/${order.id}`}>View</Link>
                  </Button>
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}

interface PaginationBarProps {
  limit: number;
  offset: number;
  total: number;
  onPrev: () => void;
  onNext: () => void;
}

function PaginationBar({
  limit,
  offset,
  total,
  onPrev,
  onNext,
}: PaginationBarProps) {
  const canPrev = offset > 0;
  const canNext = offset + limit < total;

  return (
    <div className="flex items-center justify-end gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={onPrev}
        disabled={!canPrev}
      >
        Previous
      </Button>
      <Button
        variant="outline"
        size="sm"
        onClick={onNext}
        disabled={!canNext}
      >
        Next
      </Button>
    </div>
  );
}

export default function OrdersPage() {
  const { currentStoreId } = useStoreContext();

  const [limit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState<OrderStatus | undefined>(undefined);
  const [createdFrom, setCreatedFrom] = useState("");
  const [createdTo, setCreatedTo] = useState("");

  const query = useOrdersList({
    limit,
    offset,
    status,
    created_from: createdFrom || undefined,
    created_to: createdTo || undefined,
  });

  const resetOffset = () => {
    setOffset(0);
  };

  const handleStatusChange = (next: OrderStatus | undefined) => {
    setStatus(next);
    resetOffset();
  };

  const handleCreatedFromChange = (next: string) => {
    setCreatedFrom(next);
    resetOffset();
  };

  const handleCreatedToChange = (next: string) => {
    setCreatedTo(next);
    resetOffset();
  };

  const handlePrev = () => {
    setOffset((current) => Math.max(0, current - limit));
  };

  const handleNext = () => {
    const total = query.data?.total ?? 0;
    setOffset((current) => {
      const candidate = current + limit;
      return candidate < total ? candidate : current;
    });
  };

  if (currentStoreId === null) {
    return (
      <div className="p-6 md:p-8 space-y-6 max-w-7xl">
        <PageHeader />
        <EmptyState
          icon={ClipboardList}
          title="No store selected"
          message="Orders operate inside a store context."
        />
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl">
      <PageHeader />

      <FilterBar
        status={status}
        createdFrom={createdFrom}
        createdTo={createdTo}
        onStatusChange={handleStatusChange}
        onCreatedFromChange={handleCreatedFromChange}
        onCreatedToChange={handleCreatedToChange}
        disabled={query.isLoading}
      />

      {query.isLoading ? (
        <LoadingState message="Loading orders..." />
      ) : query.isError ? (
        <ErrorState
          title="Orders failed to load"
          message={getApiErrorMessage(query.error)}
          onRetry={() => query.refetch()}
        />
      ) : query.data ? (
        <>
          <p className="text-sm text-muted-foreground" data-testid="orders-total">
            Total: {query.data.total}
          </p>

          {query.data.items.length === 0 ? (
            <EmptyState
              icon={ClipboardList}
              title="No orders found"
              message="This store has no matching orders."
            />
          ) : (
            <>
              <OrdersTable orders={query.data.items} />
              <PaginationBar
                limit={limit}
                offset={offset}
                total={query.data.total}
                onPrev={handlePrev}
                onNext={handleNext}
              />
            </>
          )}
        </>
      ) : null}
    </div>
  );
}
