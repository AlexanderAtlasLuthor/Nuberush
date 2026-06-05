// F2.7.5 (subfases 1-4): create-order page.
//
// Subfase 4 closes the loop:
//   - `isBusy` is the single source of truth for the disabled state of
//     every interactive control (items, picker, notes, cancel, submit).
//   - Backend errors auto-clear when the user edits items or notes via
//     `clearErrorOnEdit` → `mutation.reset()`. Idempotency key stays
//     stable across resets so a same-body resubmit replays cleanly per
//     orders_rules §4. The key only regenerates on re-mount (e.g.
//     after navigating to /app/store/orders/new again).
//   - No totals preview is rendered: `InventoryProductSummary` does
//     not expose `price` (variant.price lives only on the full
//     ProductVariant model), so any client-side total would be
//     fabricated. Backend computes totals server-side and the user
//     sees them on the detail page after the auto-navigation.
//
// Hard rules in force (orders_rules §2 trust boundary):
//   - useCreateOrderMutation owns the cache invalidations (orders.list
//     + orders.item(data.id) + orders.auditLogs(data.id) + inventory
//     .list). This page does NOT touch queryClient.
//   - No client-side validation of stock, compliance, totals or
//     permissions. Backend authorises and computes; errors surface
//     inline via getApiErrorMessage.
//   - No fetch, no Zustand, no useAuth.
//   - The Submit button is disabled until items.length > 0; the form
//     wiring is otherwise complete and ready for subfase 2 to plug
//     real items into.
//
// Idempotency: `idempotency_key` is generated once per mount via
// `crypto.randomUUID()` and stays stable across re-renders. Same key +
// same body → backend replays the existing order (orders_rules §4).
// Same key + DIFFERENT body → 409 inline. The hooks layer regenerates
// the key on a successful create-and-navigate cycle by virtue of the
// page unmounting; if the user wants a clean second order they navigate
// back from /app/store/orders/{id} to /app/store/orders/new and the
// page remounts.

import { useEffect, useState, type FormEvent } from "react";
import { ArrowLeft, ClipboardList, Package, Plus, Trash2 } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";

import { getApiErrorMessage } from "@/api";
import { useStoreContext } from "@/auth";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";

import { useInventoryList } from "@/features/inventory/hooks";
import {
  complianceStatusLabel,
  inventoryStatusLabel,
} from "@/features/inventory/labels";
import type { InventoryItem } from "@/features/inventory/types";

import { useCreateOrderMutation } from "../hooks";

// --------------------------------------------------------------------- //
// Local types
// --------------------------------------------------------------------- //

/**
 * Local UI line. Wire fields (`variant_id`, `quantity`) are mandatory
 * because they're sent to the backend. The display-only fields are
 * cached at pick time so the table can render product name / SKU /
 * variant modifiers without re-fetching, and are STRIPPED before
 * submit (see `handleSubmit`).
 */
interface CreateOrderLine {
  variant_id: string;
  quantity: number;
  // Display-only — NEVER sent to backend.
  productName?: string;
  sku?: string;
  flavor?: string | null;
  sizeLabel?: string | null;
}

// --------------------------------------------------------------------- //
// Pure helpers (file-scope, testable in isolation)
// --------------------------------------------------------------------- //

/**
 * Merge a new line into the existing list. If the variant_id is
 * already present, sum quantities; otherwise append. Backend rejects
 * orders with duplicate variant_id ("merge quantities into a single
 * line") so this prevents an avoidable 422.
 *
 * Subfase 3 will call this from the variant-picker `onSelect` handler
 * via `addOrMergeLine` (component-level wrapper).
 */
function mergeLine(
  lines: CreateOrderLine[],
  newLine: CreateOrderLine,
): CreateOrderLine[] {
  const idx = lines.findIndex((l) => l.variant_id === newLine.variant_id);
  if (idx === -1) return [...lines, newLine];
  return lines.map((l, i) =>
    i === idx ? { ...l, quantity: l.quantity + newLine.quantity } : l,
  );
}

// --------------------------------------------------------------------- //
// Sub-components
// --------------------------------------------------------------------- //

interface ItemsTableProps {
  items: CreateOrderLine[];
  disabled: boolean;
  onQuantityChange: (index: number, quantity: number) => void;
  onRemove: (index: number) => void;
}

function variantLabel(line: CreateOrderLine): string {
  const parts = [line.flavor, line.sizeLabel].filter(
    (part): part is string => typeof part === "string" && part.length > 0,
  );
  return parts.length > 0 ? parts.join(" • ") : "—";
}

function ItemsTable({
  items,
  disabled,
  onQuantityChange,
  onRemove,
}: ItemsTableProps) {
  return (
    <div className="rounded-md border border-border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Product</TableHead>
            <TableHead>SKU</TableHead>
            <TableHead>Variant</TableHead>
            <TableHead className="w-32 text-right">Quantity</TableHead>
            <TableHead className="w-12 text-right">
              <span className="sr-only">Actions</span>
            </TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {items.map((item, index) => (
            <TableRow key={item.variant_id}>
              <TableCell className="font-medium">
                {item.productName ?? "—"}
              </TableCell>
              <TableCell className="font-mono text-xs">
                {item.sku ?? "—"}
              </TableCell>
              <TableCell className="text-sm text-muted-foreground">
                {variantLabel(item)}
              </TableCell>
              <TableCell className="text-right">
                <Input
                  type="number"
                  min={1}
                  step={1}
                  inputMode="numeric"
                  value={item.quantity > 0 ? item.quantity : ""}
                  onChange={(e) => {
                    const raw = e.target.value;
                    // Empty / non-numeric → 0 (UX guard rejects via canSubmit).
                    const parsed = raw === "" ? 0 : Number(raw);
                    onQuantityChange(
                      index,
                      Number.isFinite(parsed) ? parsed : 0,
                    );
                  }}
                  disabled={disabled}
                  className="ml-auto w-24 text-right tabular-nums"
                  aria-label={`Quantity for ${item.productName ?? `variant ${item.variant_id}`}`}
                  data-testid={`create-order-line-quantity-${index}`}
                />
              </TableCell>
              <TableCell className="text-right">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => onRemove(index)}
                  disabled={disabled}
                  aria-label={`Remove ${item.productName ?? `variant ${item.variant_id}`}`}
                  data-testid={`create-order-line-remove-${index}`}
                >
                  <Trash2 className="h-4 w-4" aria-hidden="true" />
                </Button>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}

// --------------------------------------------------------------------- //
// VariantPicker (subfase 3)
// --------------------------------------------------------------------- //

const PICKER_LIMIT = 50;

interface VariantPickerProps {
  /** True while the create-order mutation is in flight. Disables every
   * picker control so the user cannot mutate the items list mid-submit. */
  disabled: boolean;
  /** Called when the user clicks Add on a row. Page wires this to
   * `addOrMergeLine` so duplicate variant_ids are merged. */
  onAdd: (item: InventoryItem) => void;
}

/**
 * Compose a variant's flavor + size_label into a single display label.
 * Returns em-dash when both are null/empty (e.g. SKU alone identifies
 * the variant, no further modifiers).
 */
function variantModifierLabel(item: InventoryItem): string {
  const parts = [item.variant.flavor, item.variant.size_label].filter(
    (p): p is string => typeof p === "string" && p.length > 0,
  );
  return parts.length > 0 ? parts.join(" • ") : "—";
}

function complianceClassName(status: string): string {
  // Cosmetic only. Backend enforces sellability via assert_product_sellable.
  if (status === "banned") return "text-destructive font-medium";
  if (status === "restricted") return "text-yellow-600 font-medium";
  return "text-muted-foreground";
}

function VariantPicker({ disabled, onAdd }: VariantPickerProps) {
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");

  const query = useInventoryList({ limit: PICKER_LIMIT, offset });

  if (query.isLoading) {
    return <LoadingState message="Loading variants..." />;
  }

  if (query.isError) {
    return (
      <ErrorState
        title="Variants failed to load"
        message={getApiErrorMessage(query.error)}
        onRetry={() => query.refetch()}
      />
    );
  }

  const allItems = query.data?.items ?? [];
  const total = query.data?.total ?? 0;

  // Client-side filter over the current page only. Backend has no
  // search endpoint; this narrows the visible rows without changing
  // pagination math.
  const trimmed = search.trim().toLowerCase();
  const filteredItems =
    trimmed.length === 0
      ? allItems
      : allItems.filter((item) => {
          const haystack = [
            item.variant.product.name,
            item.variant.sku,
            item.variant.flavor ?? "",
            item.variant.size_label ?? "",
          ]
            .join(" ")
            .toLowerCase();
          return haystack.includes(trimmed);
        });

  const canPrev = offset > 0;
  const canNext = offset + PICKER_LIMIT < total;

  const handlePrev = () => {
    setOffset((current) => Math.max(0, current - PICKER_LIMIT));
  };
  const handleNext = () => {
    setOffset((current) => {
      const candidate = current + PICKER_LIMIT;
      return candidate < total ? candidate : current;
    });
  };

  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="create-order-picker-search">Search</Label>
        <Input
          id="create-order-picker-search"
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          disabled={disabled}
          placeholder="Filter by product, SKU, flavor or size"
          data-testid="create-order-picker-search"
        />
      </div>

      {allItems.length === 0 ? (
        <EmptyState
          icon={Package}
          title="No inventory in this store"
          message="There are no variants to pick from yet."
        />
      ) : filteredItems.length === 0 ? (
        <EmptyState
          icon={Package}
          title="No matches"
          message={`No variants on this page match "${search.trim()}".`}
        />
      ) : (
        <div className="rounded-md border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Product</TableHead>
                <TableHead>SKU</TableHead>
                <TableHead>Variant</TableHead>
                <TableHead className="text-right">Available</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Compliance</TableHead>
                <TableHead className="w-16 text-right">
                  <span className="sr-only">Action</span>
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredItems.map((item) => {
                const available =
                  item.quantity_on_hand - item.quantity_reserved;
                const compliance = item.variant.product.compliance_status;
                const sellable = item.variant.product.allowed_for_sale;

                return (
                  <TableRow key={item.id}>
                    <TableCell className="font-medium">
                      {item.variant.product.name}
                    </TableCell>
                    <TableCell className="font-mono text-xs">
                      {item.variant.sku}
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {variantModifierLabel(item)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {available}
                    </TableCell>
                    <TableCell>
                      <span className="text-xs uppercase tracking-wide text-muted-foreground">
                        {inventoryStatusLabel(item.status)}
                      </span>
                    </TableCell>
                    <TableCell>
                      <span
                        className={`text-xs uppercase tracking-wide ${complianceClassName(
                          compliance,
                        )}`}
                      >
                        {complianceStatusLabel(compliance)}
                        {!sellable ? " · not available for sale" : ""}
                      </span>
                    </TableCell>
                    <TableCell className="text-right">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => onAdd(item)}
                        disabled={disabled}
                        data-testid={`create-order-picker-add-${item.variant.id}`}
                      >
                        <Plus
                          className="mr-1 h-3.5 w-3.5"
                          aria-hidden="true"
                        />
                        Add
                      </Button>
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      <div className="flex items-center justify-between gap-2">
        <p
          className="text-xs text-muted-foreground tabular-nums"
          data-testid="create-order-picker-total"
        >
          {total} variants · page offset {offset}
        </p>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handlePrev}
            disabled={!canPrev || disabled}
            data-testid="create-order-picker-prev"
          >
            Previous
          </Button>
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={handleNext}
            disabled={!canNext || disabled}
            data-testid="create-order-picker-next"
          >
            Next
          </Button>
        </div>
      </div>
    </div>
  );
}

function PageHeader() {
  return (
    <header className="flex flex-col gap-3">
      <Button variant="ghost" size="sm" asChild className="self-start">
        <Link to="/app/store/orders" data-testid="create-order-back">
          <ArrowLeft className="mr-2 h-4 w-4" aria-hidden="true" />
          Back to orders
        </Link>
      </Button>
      <div>
        <h1 className="text-xl font-semibold">Create order</h1>
        <p className="text-sm text-muted-foreground">
          Add items, optionally include notes, and submit. Totals are
          computed by the server.
        </p>
      </div>
    </header>
  );
}

// --------------------------------------------------------------------- //
// Page
// --------------------------------------------------------------------- //

export default function CreateOrderPage() {
  const navigate = useNavigate();
  const { currentStoreId } = useStoreContext();

  // Generated once at mount; stable across re-renders. See header
  // comment for the idempotency contract.
  const [idempotencyKey] = useState<string>(() => crypto.randomUUID());
  // Subfase 2: state owns add/remove/quantity. Subfase 3 wires the
  // picker callback to `addOrMergeLine` below; in this subfase the
  // table renders only when subfase 3 has populated items.
  const [items, setItems] = useState<CreateOrderLine[]>([]);
  const [notes, setNotes] = useState("");

  const mutation = useCreateOrderMutation();

  // Single source of truth for "is the form locked". Propagated to
  // every interactive control (picker, items table, notes, cancel,
  // submit). Currently driven only by mutation.isPending; future
  // states (e.g. saving as draft) can OR into here without touching
  // the JSX.
  const isBusy = mutation.isPending;

  // Clear the inline backend error as soon as the user edits items or
  // notes. The mutation hook's reset() is a no-op when no error is
  // present, but we still gate to avoid an unnecessary re-render on
  // every keystroke. The idempotency_key stays untouched across
  // resets — same body → same key → backend replays per orders_rules
  // §4; different body → 409 surfaces inline again.
  const clearErrorOnEdit = () => {
    if (mutation.isError) {
      mutation.reset();
    }
  };

  // Auto-navigate to the new order's detail page on success. The
  // page unmounts on navigation, which naturally resets all local
  // state — including the idempotency key — so a second create starts
  // fresh. Effect deps ensure the navigate fires exactly once per
  // mutation cycle (isSuccess flips false→true once; data is stable
  // after that).
  useEffect(() => {
    if (mutation.isSuccess && mutation.data) {
      navigate(`/app/store/orders/${mutation.data.id}`);
    }
  }, [mutation.isSuccess, mutation.data, navigate]);

  // UX guards (NOT business validation):
  //   - items.length > 0   →  backend would 422 with "items must have
  //                           at least 1 element"; cheaper to disable.
  //   - allQuantitiesValid → cheap pre-check; backend re-validates.
  //   - !isBusy            → anti-double-submit.
  //   - currentStoreId !== null → narrowed by the early-return branch
  //                           below, but kept here for TS narrowing
  //                           inside handleSubmit.
  const allQuantitiesValid = items.every(
    (line) => Number.isInteger(line.quantity) && line.quantity > 0,
  );
  const canSubmit =
    items.length > 0 &&
    allQuantitiesValid &&
    !isBusy &&
    currentStoreId !== null;

  // Wired to the variant-picker `onSelect` callback. Pure delegation
  // to the file-scope mergeLine; clears any inline backend error so
  // the user sees the items list update without stale 4xx noise.
  const addOrMergeLine = (line: CreateOrderLine) => {
    clearErrorOnEdit();
    setItems((prev) => mergeLine(prev, line));
  };

  const updateQuantity = (index: number, quantity: number) => {
    clearErrorOnEdit();
    setItems((prev) =>
      prev.map((line, i) => (i === index ? { ...line, quantity } : line)),
    );
  };

  const removeLine = (index: number) => {
    clearErrorOnEdit();
    setItems((prev) => prev.filter((_, i) => i !== index));
  };

  const handleNotesChange = (next: string) => {
    clearErrorOnEdit();
    setNotes(next);
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!canSubmit || currentStoreId === null) return;

    const trimmedNotes = notes.trim();

    mutation.mutate({
      storeId: currentStoreId,
      body: {
        idempotency_key: idempotencyKey,
        // Strip display-only fields. Backend rejects unknown fields
        // (extra="forbid") and orders_rules §2 trust boundary forbids
        // any monetary / inventory_item_id / customer_user_id leak.
        items: items.map((line) => ({
          variant_id: line.variant_id,
          quantity: line.quantity,
        })),
        notes: trimmedNotes.length > 0 ? trimmedNotes : null,
      },
    });
  };

  // Admin / no-store branch — keep the back link visible so the user
  // can navigate away cleanly.
  if (currentStoreId === null) {
    return (
      <div className="p-6 md:p-8 space-y-6 max-w-7xl">
        <PageHeader />
        <EmptyState
          icon={ClipboardList}
          title="No store selected"
          message="Order creation operates inside a store context. Admin store selection is not yet supported."
        />
      </div>
    );
  }

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-7xl">
      <PageHeader />

      <form onSubmit={handleSubmit} noValidate className="space-y-6">
        {/* Items section — empty state when no items, editable table
            otherwise. Quantity editor and remove button per row;
            disabled while the mutation is pending. */}
        <Card>
          <CardHeader>
            <CardTitle>Items</CardTitle>
            <CardDescription>
              Selected variants and quantities for this order.
            </CardDescription>
          </CardHeader>
          {items.length === 0 ? (
            <CardContent>
              <EmptyState
                icon={ClipboardList}
                title="No items yet"
                message="Add variants from the picker to build this order."
              />
            </CardContent>
          ) : (
            <CardContent className="p-0">
              <ItemsTable
                items={items}
                disabled={isBusy}
                onQuantityChange={updateQuantity}
                onRemove={removeLine}
              />
            </CardContent>
          )}
        </Card>

        {/* Variant picker section — drives the items table via
            addOrMergeLine. Stock / compliance / status are shown for
            operator awareness only; backend is the authority on
            sellability and stock. */}
        <Card>
          <CardHeader>
            <CardTitle>Variant picker</CardTitle>
            <CardDescription>
              Browse current store inventory to add line items.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <VariantPicker
              disabled={isBusy}
              onAdd={(item) =>
                addOrMergeLine({
                  variant_id: item.variant.id,
                  quantity: 1,
                  productName: item.variant.product.name,
                  sku: item.variant.sku,
                  flavor: item.variant.flavor,
                  sizeLabel: item.variant.size_label,
                })
              }
            />
          </CardContent>
        </Card>

        {/* Notes section — already real (no picker needed). Optional;
            whitespace-only entries are normalised to null at submit. */}
        <Card>
          <CardHeader>
            <CardTitle>Notes</CardTitle>
            <CardDescription>
              Optional. Trimmed before submit.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              <Label htmlFor="create-order-notes">Notes</Label>
              <Textarea
                id="create-order-notes"
                value={notes}
                onChange={(e) => handleNotesChange(e.target.value)}
                disabled={isBusy}
                rows={3}
                placeholder="Optional notes about this order"
              />
            </div>
          </CardContent>
        </Card>

        {mutation.isError ? (
          <p
            role="alert"
            aria-live="polite"
            className="text-sm text-destructive"
            data-testid="create-order-error"
          >
            {getApiErrorMessage(mutation.error)}
          </p>
        ) : null}

        <div className="flex items-center justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => navigate("/app/store/orders")}
            disabled={isBusy}
            data-testid="create-order-cancel"
          >
            Cancel
          </Button>
          <Button
            type="submit"
            disabled={!canSubmit}
            data-testid="create-order-submit"
          >
            <Plus className="mr-2 h-4 w-4" aria-hidden="true" />
            {isBusy ? "Creating..." : "Create order"}
          </Button>
        </div>
      </form>
    </div>
  );
}
