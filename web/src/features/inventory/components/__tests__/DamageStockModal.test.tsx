// F2.11-M2.2: tests for DamageStockModal.
//
// Mirror of ReceiveStockModal tests with these wire-contract differences:
//   - Wire payload: { quantity, reason }; no reference fields.
//   - quantity is UNSIGNED (positive integer). The frontend sends a
//     POSITIVE number; the backend service applies the negative sign
//     when reducing stock. This test file deliberately verifies the
//     positive-on-the-wire behavior — the brief explicitly forbids
//     a frontend negative-stock conversion.
//   - reason is REQUIRED and non-empty after trim.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { DamageStockModal } from "../DamageStockModal";
import * as inventoryHooks from "../../hooks";
import type { DamageStockParams } from "../../api";
import type { InventoryItem } from "../../types";

vi.mock("../../hooks", () => ({
  useDamageStockMutation: vi.fn(),
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
): UseMutationResult<InventoryItem, Error, DamageStockParams> & {
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
    DamageStockParams
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
  vi.mocked(inventoryHooks.useDamageStockMutation).mockReset();
  vi.mocked(inventoryHooks.useDamageStockMutation).mockReturnValue(
    makeMutation(),
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Open / closed
// --------------------------------------------------------------------- //

describe("DamageStockModal — render gating", () => {
  it("renders fields when open=true", () => {
    render(
      <DamageStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    expect(screen.getByLabelText(/^quantity/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^reason/i)).toBeInTheDocument();
    expect(screen.getByTestId("damage-stock-submit")).toBeInTheDocument();
  });

  it("does not render when open=false", () => {
    render(
      <DamageStockModal open={false} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    expect(screen.queryByLabelText(/^quantity/i)).toBeNull();
    expect(screen.queryByTestId("damage-stock-submit")).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// Validation
// --------------------------------------------------------------------- //

describe("DamageStockModal — validation", () => {
  it.each([
    ["empty", ""],
    ["zero", "0"],
    ["negative", "-3"],
    ["non-integer", "1.5"],
    ["non-numeric", "abc"],
  ] as const)(
    "disables submit when quantity is %s",
    (_label, value) => {
      render(
        <DamageStockModal
          open={true}
          onOpenChange={vi.fn()}
          item={makeItem()}
        />,
      );
      fireEvent.change(screen.getByLabelText(/^quantity/i), {
        target: { value },
      });
      fireEvent.change(screen.getByLabelText(/^reason/i), {
        target: { value: "any reason" },
      });
      expect(screen.getByTestId("damage-stock-submit")).toBeDisabled();
    },
  );

  it("disables submit when reason is empty / whitespace-only", () => {
    render(
      <DamageStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^quantity/i), {
      target: { value: "5" },
    });
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "   " },
    });
    expect(screen.getByTestId("damage-stock-submit")).toBeDisabled();
  });

  it("enables submit with positive quantity + non-empty reason", () => {
    render(
      <DamageStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^quantity/i), {
      target: { value: "5" },
    });
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "lost in transit" },
    });
    expect(screen.getByTestId("damage-stock-submit")).not.toBeDisabled();
  });
});

// --------------------------------------------------------------------- //
// Submit payload
// --------------------------------------------------------------------- //

describe("DamageStockModal — submit payload", () => {
  it("forwards { quantity, reason } with the unsigned positive quantity", () => {
    const mutation = makeMutation();
    vi.mocked(inventoryHooks.useDamageStockMutation).mockReturnValue(mutation);

    render(
      <DamageStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^quantity/i), {
      target: { value: "8" },
    });
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "  damaged in shelf collapse  " },
    });
    fireEvent.click(screen.getByTestId("damage-stock-submit"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      inventoryItemId: ITEM_ID,
      body: {
        quantity: 8,
        reason: "damaged in shelf collapse",
      },
    });
  });

  it("never sends a negative quantity (no client-side flip)", () => {
    // Backend service applies the negative sign when reducing stock.
    // Frontend's job is to capture the unsigned damage count and let
    // the server interpret it. Verifying the value is positive on the
    // wire locks the contract documented in DamageStockModal.tsx.
    const mutation = makeMutation();
    vi.mocked(inventoryHooks.useDamageStockMutation).mockReturnValue(mutation);

    render(
      <DamageStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^quantity/i), {
      target: { value: "12" },
    });
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "broken" },
    });
    fireEvent.click(screen.getByTestId("damage-stock-submit"));

    const call = mutation.mutate.mock.calls[0][0] as { body: { quantity: number } };
    expect(call.body.quantity).toBe(12);
    expect(call.body.quantity).toBeGreaterThan(0);
  });
});

// --------------------------------------------------------------------- //
// Pending / error / success
// --------------------------------------------------------------------- //

describe("DamageStockModal — server feedback", () => {
  it("disables every input + flips submit text while pending", () => {
    vi.mocked(inventoryHooks.useDamageStockMutation).mockReturnValue(
      makeMutation({ isPending: true }),
    );

    render(
      <DamageStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    expect(screen.getByLabelText(/^quantity/i)).toBeDisabled();
    expect(screen.getByLabelText(/^reason/i)).toBeDisabled();
    const submit = screen.getByTestId("damage-stock-submit");
    expect(submit).toBeDisabled();
    expect(submit).toHaveTextContent(/recording/i);
  });

  it("renders backend ApiError detail inline", () => {
    vi.mocked(inventoryHooks.useDamageStockMutation).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 422,
          message: "quantity exceeds available stock",
        }),
      }),
    );

    render(
      <DamageStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    expect(screen.getByTestId("damage-stock-error")).toHaveTextContent(
      /quantity exceeds available stock/i,
    );
  });

  it("calls onOpenChange(false) on success", () => {
    vi.mocked(inventoryHooks.useDamageStockMutation).mockReturnValue(
      makeMutation({ isSuccess: true }),
    );

    const onOpenChange = vi.fn();
    render(
      <DamageStockModal
        open={true}
        onOpenChange={onOpenChange}
        item={makeItem()}
      />,
    );

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("calls mutation.reset on (re)open", () => {
    const mutation = makeMutation();
    vi.mocked(inventoryHooks.useDamageStockMutation).mockReturnValue(mutation);

    render(
      <DamageStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    expect(mutation.reset).toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------- //
// Source-level architecture guards
// --------------------------------------------------------------------- //

describe("DamageStockModal — architecture", () => {
  it("does NOT import useAuth / currentUser / role checks / fetch / axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "DamageStockModal.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\bcurrentUser\b/);
    expect(code).not.toMatch(/\.role\s*===/);
    expect(code).not.toMatch(/\bhasPermission\b/);
    expect(code).not.toMatch(/\ballowedRoles\b/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
  });

  it("does NOT flip quantity sign client-side (no -1 multiplication)", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "DamageStockModal.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    // Forbidden — would mean the frontend converts the user's positive
    // input into a negative wire value. The backend owns that semantic.
    // Patterns target arithmetic contexts; the JSX literal
    // `id="damage-quantity"` is not a violation, so we do not grep for
    // the bare token.
    expect(code).not.toMatch(/quantity\s*\*\s*-?1/);
    expect(code).not.toMatch(/-1\s*\*\s*\w*[Qq]uantity/);
    expect(code).not.toMatch(/-\s*parsedQuantity/);
    // The body builder must never send `quantity: -...` to the wire.
    expect(code).not.toMatch(/quantity\s*:\s*-/);
  });

  it("does NOT recompute stock authority", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "DamageStockModal.tsx");
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
    const here = path.resolve(__dirname, "..", "DamageStockModal.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/setQueryData\s*\(/);
    expect(code).not.toMatch(/onMutate\s*:/);
  });
});
