// F2.6.1: real inventory list page.
//
// Store App inventory page mounted under /app/store/inventory. Read-only in
// this subphase: receive / adjust modals ship in F2.6.2 against the mutations
// already wired in F2.6.0.
//
// Architecture rules in force here (see brief):
//   - No fetch, no mutations yet, no Zustand, no business logic.
//   - useState only for limit / offset / lowStockOnly UX state.
//   - Data shape stays the wire shape — no client-side derivations,
//     no formatting beyond what shadcn primitives apply.
//   - Hooks order is fixed: every hook (useStoreContext, useState,
//     useInventoryList) runs on every render. The `currentStoreId`
//     null branch is rendering-only, never an early return.

import { useState } from "react";
import { Boxes } from "lucide-react";

import { useStoreContext } from "@/auth";
import { LoadingState } from "@/components/common/loading-state";
import { ErrorState } from "@/components/common/error-state";
import { EmptyState } from "@/components/common/empty-state";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { getApiErrorMessage } from "@/api";

import { useInventoryList } from "../hooks";
import { InventoryActions } from "../components/InventoryActions";
import type { InventoryItem } from "../types";

const DEFAULT_LIMIT = 20;

// --------------------------------------------------------------------- //
// Sub-components
// --------------------------------------------------------------------- //

function PageHeader() {
  return (
    <header>
      <h1 className="text-xl font-semibold">Inventory</h1>
      <p className="text-sm text-muted-foreground">
        Stock levels per store. Receive and adjust ship in the next subphase.
      </p>
    </header>
  );
}

interface FilterBarProps {
  lowStockOnly: boolean;
  onLowStockOnlyChange: (next: boolean) => void;
  disabled?: boolean;
}

function FilterBar({
  lowStockOnly,
  onLowStockOnlyChange,
  disabled,
}: FilterBarProps) {
  return (
    <div className="flex items-center gap-2">
      <Checkbox
        id="low-stock-only"
        checked={lowStockOnly}
        disabled={disabled}
        onCheckedChange={(value) => onLowStockOnlyChange(value === true)}
      />
      <Label htmlFor="low-stock-only" className="text-sm cursor-pointer">
        Low stock only
      </Label>
    </div>
  );
}

function InventoryTable({ items }: { items: InventoryItem[] }) {
  return (
    <div className="rounded-md border border-border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Product</TableHead>
            <TableHead>SKU</TableHead>
            <TableHead className="text-right">Stock</TableHead>
            <TableHead className="text-right">Reserved</TableHead>
            <TableHead className="text-right">Threshold</TableHead>
            <TableHead>Status</TableHead>
            <TableHead className="w-12 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
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
              <TableCell className="text-right tabular-nums">
                {item.quantity_on_hand}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {item.quantity_reserved}
              </TableCell>
              <TableCell className="text-right tabular-nums">
                {item.reorder_threshold}
              </TableCell>
              <TableCell>
                <span className="text-xs uppercase tracking-wide text-muted-foreground">
                  {item.status}
                </span>
              </TableCell>
              <TableCell className="text-right">
                <InventoryActions item={item} />
              </TableCell>
            </TableRow>
          ))}
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
  // Per the brief: "no ir < 0", "no ir más allá de total". These two
  // booleans encode exactly that — Previous disabled at the top, Next
  // disabled when the next page would start past the last row.
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

// --------------------------------------------------------------------- //
// Page
// --------------------------------------------------------------------- //

export default function InventoryPage() {
  const { currentStoreId } = useStoreContext();

  const [limit] = useState(DEFAULT_LIMIT);
  const [offset, setOffset] = useState(0);
  const [lowStockOnly, setLowStockOnly] = useState(false);

  // Always called: useInventoryList internally short-circuits via
  // `enabled: currentStoreId !== null` so admin / no-store users
  // don't fire a network request. This keeps Rules of Hooks happy.
  const query = useInventoryList({
    limit,
    offset,
    low_stock_only: lowStockOnly,
  });

  const handleLowStockOnlyChange = (next: boolean) => {
    setLowStockOnly(next);
    // Reset to first page so a filter change can't leave the user on
    // an offset past the filtered total.
    setOffset(0);
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

  // ------------------------- render branches ------------------------- //

  if (currentStoreId === null) {
    // Admin in global scope (no store_id) — non-admin without store_id
    // is already blocked upstream by StoreGate.
    return (
      <div className="p-6 md:p-8 space-y-6 max-w-6xl">
        <PageHeader />
        <EmptyState
          icon={Boxes}
          title="No store selected"
          message="Inventory operates inside a store context. Admin store selection is not yet supported."
        />
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-6xl">
      <PageHeader />

      <FilterBar
        lowStockOnly={lowStockOnly}
        onLowStockOnlyChange={handleLowStockOnlyChange}
        disabled={query.isLoading}
      />

      {query.isLoading ? (
        <LoadingState message="Loading inventory…" />
      ) : query.isError ? (
        <ErrorState
          title="Inventory failed to load"
          message={getApiErrorMessage(query.error)}
          onRetry={() => query.refetch()}
        />
      ) : query.data && query.data.items.length === 0 ? (
        <EmptyState
          icon={Boxes}
          title={lowStockOnly ? "No low-stock items" : "No inventory yet"}
          message={
            lowStockOnly
              ? "No items are currently below their reorder threshold."
              : "This store has no inventory items yet."
          }
        />
      ) : query.data ? (
        <>
          <p
            className="text-sm text-muted-foreground"
            data-testid="inventory-total"
          >
            Total: {query.data.total}
          </p>
          <InventoryTable items={query.data.items} />
          <PaginationBar
            limit={limit}
            offset={offset}
            total={query.data.total}
            onPrev={handlePrev}
            onNext={handleNext}
          />
        </>
      ) : null}
    </div>
  );
}
