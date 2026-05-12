// F2.11-M2.2: tests for AdjustStockModal.
//
// Mirror of ReceiveStockModal tests. Differences from Receive:
//   - Wire payload: { delta, reason }; no reference fields.
//   - delta must be a NON-ZERO integer (positive adds, negative removes).
//   - reason is REQUIRED and non-empty after trim.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { AdjustStockModal } from "../AdjustStockModal";
import * as inventoryHooks from "../../hooks";
import type { AdjustStockParams } from "../../api";
import type { InventoryItem } from "../../types";

vi.mock("../../hooks", () => ({
  useAdjustStockMutation: vi.fn(),
}));

const ITEM_ID = "11111111-1111-1111-1111-111111111111";
const STORE_ID = "22222222-2222-2222-2222-222222222222";
const VARIANT_ID = "33333333-3333-3333-3333-333333333333";
const PRODUCT_ID = "44444444-4444-4444-4444-444444444444";

interface MutationOverrides {
  isPending?: boolean;
  isSuccess?: boolean;
  isError?: boolean;
  error?: Error | null;
}

function makeMutation(
  o: MutationOverrides = {},
): UseMutationResult<InventoryItem, Error, AdjustStockParams> & {
  mutate: ReturnType<typeof vi.fn>;
  reset: ReturnType<typeof vi.fn>;
} {
  return {
    mutate: vi.fn(),
    reset: vi.fn(),
    isPending: o.isPending ?? false,
    isSuccess: o.isSuccess ?? false,
    isError: o.isError ?? false,
    error: o.error ?? null,
  } as unknown as UseMutationResult<
    InventoryItem,
    Error,
    AdjustStockParams
  > & {
    mutate: ReturnType<typeof vi.fn>;
    reset: ReturnType<typeof vi.fn>;
  };
}

function makeItem(overrides: Partial<InventoryItem> = {}): InventoryItem {
  return {
    id: ITEM_ID,
    store_id: STORE_ID,
    variant_id: VARIANT_ID,
    quantity_on_hand: 50,
    quantity_reserved: 0,
    reorder_threshold: 10,
    status: "available",
    last_counted_at: null,
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-01T00:00:00Z",
    variant: {
      id: VARIANT_ID,
      sku: "GUM-MIX-10",
      flavor: null,
      size_label: null,
      is_active: true,
      product: {
        id: PRODUCT_ID,
        name: "Cosmic Gummies",
        brand: null,
        category: "edibles",
        compliance_status: "allowed",
        allowed_for_sale: true,
        is_active: true,
      },
    },
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(inventoryHooks.useAdjustStockMutation).mockReset();
  vi.mocked(inventoryHooks.useAdjustStockMutation).mockReturnValue(
    makeMutation(),
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Open / closed
// --------------------------------------------------------------------- //

describe("AdjustStockModal — render gating", () => {
  it("renders fields when open=true", () => {
    render(
      <AdjustStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    expect(screen.getByLabelText(/^delta/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^reason/i)).toBeInTheDocument();
    expect(screen.getByTestId("adjust-stock-submit")).toBeInTheDocument();
  });

  it("does not render when open=false", () => {
    render(
      <AdjustStockModal open={false} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    expect(screen.queryByLabelText(/^delta/i)).toBeNull();
    expect(screen.queryByTestId("adjust-stock-submit")).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// Validation
// --------------------------------------------------------------------- //

describe("AdjustStockModal — validation", () => {
  it("disables submit when delta is empty", () => {
    render(
      <AdjustStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "stocktake correction" },
    });
    expect(screen.getByTestId("adjust-stock-submit")).toBeDisabled();
  });

  it("disables submit when delta is zero (backend rejects, UI mirrors)", () => {
    render(
      <AdjustStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^delta/i), {
      target: { value: "0" },
    });
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "any reason" },
    });
    expect(screen.getByTestId("adjust-stock-submit")).toBeDisabled();
  });

  it("disables submit when delta is non-integer", () => {
    render(
      <AdjustStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^delta/i), {
      target: { value: "1.5" },
    });
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "any reason" },
    });
    expect(screen.getByTestId("adjust-stock-submit")).toBeDisabled();
  });

  it("disables submit when reason is empty / whitespace-only", () => {
    render(
      <AdjustStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^delta/i), {
      target: { value: "5" },
    });
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "   " },
    });
    expect(screen.getByTestId("adjust-stock-submit")).toBeDisabled();
  });

  it("enables submit with positive delta + non-empty reason", () => {
    render(
      <AdjustStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^delta/i), {
      target: { value: "5" },
    });
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "stocktake correction" },
    });
    expect(screen.getByTestId("adjust-stock-submit")).not.toBeDisabled();
  });

  it("enables submit with negative delta + non-empty reason", () => {
    render(
      <AdjustStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^delta/i), {
      target: { value: "-3" },
    });
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "shrinkage" },
    });
    expect(screen.getByTestId("adjust-stock-submit")).not.toBeDisabled();
  });
});

// --------------------------------------------------------------------- //
// Submit payload
// --------------------------------------------------------------------- //

describe("AdjustStockModal — submit payload", () => {
  it("forwards { delta, reason } with positive delta", () => {
    const mutation = makeMutation();
    vi.mocked(inventoryHooks.useAdjustStockMutation).mockReturnValue(mutation);

    render(
      <AdjustStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^delta/i), {
      target: { value: "7" },
    });
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "  stocktake  " },
    });
    fireEvent.click(screen.getByTestId("adjust-stock-submit"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      inventoryItemId: ITEM_ID,
      body: {
        delta: 7,
        reason: "stocktake",
      },
    });
  });

  it("forwards a negative delta verbatim (no client-side flip)", () => {
    const mutation = makeMutation();
    vi.mocked(inventoryHooks.useAdjustStockMutation).mockReturnValue(mutation);

    render(
      <AdjustStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^delta/i), {
      target: { value: "-12" },
    });
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "shrinkage" },
    });
    fireEvent.click(screen.getByTestId("adjust-stock-submit"));

    expect(mutation.mutate).toHaveBeenCalledWith({
      inventoryItemId: ITEM_ID,
      body: {
        delta: -12,
        reason: "shrinkage",
      },
    });
  });
});

// --------------------------------------------------------------------- //
// Pending / error / success
// --------------------------------------------------------------------- //

describe("AdjustStockModal — server feedback", () => {
  it("disables every input + flips submit text while pending", () => {
    vi.mocked(inventoryHooks.useAdjustStockMutation).mockReturnValue(
      makeMutation({ isPending: true }),
    );

    render(
      <AdjustStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    expect(screen.getByLabelText(/^delta/i)).toBeDisabled();
    expect(screen.getByLabelText(/^reason/i)).toBeDisabled();
    const submit = screen.getByTestId("adjust-stock-submit");
    expect(submit).toBeDisabled();
    expect(submit).toHaveTextContent(/adjusting/i);
  });

  it("renders backend ApiError detail inline", () => {
    vi.mocked(inventoryHooks.useAdjustStockMutation).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 422,
          message: "delta must be non-zero",
        }),
      }),
    );

    render(
      <AdjustStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    expect(screen.getByTestId("adjust-stock-error")).toHaveTextContent(
      /delta must be non-zero/i,
    );
  });

  it("calls onOpenChange(false) on success", () => {
    vi.mocked(inventoryHooks.useAdjustStockMutation).mockReturnValue(
      makeMutation({ isSuccess: true }),
    );

    const onOpenChange = vi.fn();
    render(
      <AdjustStockModal
        open={true}
        onOpenChange={onOpenChange}
        item={makeItem()}
      />,
    );

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("calls mutation.reset on (re)open", () => {
    const mutation = makeMutation();
    vi.mocked(inventoryHooks.useAdjustStockMutation).mockReturnValue(mutation);

    render(
      <AdjustStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    expect(mutation.reset).toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------- //
// Source-level architecture guards
// --------------------------------------------------------------------- //

describe("AdjustStockModal — architecture", () => {
  it("does NOT import useAuth / currentUser / role checks / fetch / axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "AdjustStockModal.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\bcurrentUser\b/);
    expect(code).not.toMatch(/\.role\s*===/);
    expect(code).not.toMatch(/\bcanManage\b/);
    expect(code).not.toMatch(/\bhasPermission\b/);
    expect(code).not.toMatch(/\ballowedRoles\b/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
  });

  it("does NOT recompute stock authority", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "AdjustStockModal.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/quantity_on_hand\s*[-+*/]/);
    expect(code).not.toMatch(/quantity_reserved\s*[-+*/]/);
    expect(code).not.toMatch(/quantity_after\s*=/);
  });

  it("does NOT use optimistic update / setQueryData", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "AdjustStockModal.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/setQueryData\s*\(/);
    expect(code).not.toMatch(/onMutate\s*:/);
    expect(code).not.toMatch(/\boptimistic\b/i);
  });
});
