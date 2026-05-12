// F2.11-M2.2: tests for ReceiveStockModal.
//
// Strategy mirrors features/users/components/__tests__/CreateUserForm.test.tsx
// — stub `../../hooks` so the modal renders the mocked
// `useReceiveStockMutation` result without touching TanStack Query,
// the api layer, or the network. We assert the form lifecycle
// (open/close, reset on open, auto-close on success), every UX
// validation gate, the exact wire payload (including null vs trimmed
// optionals), the pending UX, and the inline ApiError surfacing —
// plus three source-level architecture guards.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { ReceiveStockModal } from "../ReceiveStockModal";
import * as inventoryHooks from "../../hooks";
import type { ReceiveStockParams } from "../../api";
import type { InventoryItem } from "../../types";

vi.mock("../../hooks", () => ({
  useReceiveStockMutation: vi.fn(),
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
): UseMutationResult<InventoryItem, Error, ReceiveStockParams> & {
  mutate: ReturnType<typeof vi.fn>;
  reset: ReturnType<typeof vi.fn>;
} {
  const mutate = vi.fn();
  const reset = vi.fn();
  return {
    mutate,
    reset,
    isPending: o.isPending ?? false,
    isSuccess: o.isSuccess ?? false,
    isError: o.isError ?? false,
    error: o.error ?? null,
  } as unknown as UseMutationResult<
    InventoryItem,
    Error,
    ReceiveStockParams
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
  vi.mocked(inventoryHooks.useReceiveStockMutation).mockReset();
  vi.mocked(inventoryHooks.useReceiveStockMutation).mockReturnValue(
    makeMutation(),
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Open / closed
// --------------------------------------------------------------------- //

describe("ReceiveStockModal — render gating", () => {
  it("renders the form fields when open=true", () => {
    render(
      <ReceiveStockModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );

    expect(screen.getByLabelText(/^quantity/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^reason/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/reference type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/reference id/i)).toBeInTheDocument();
    expect(screen.getByTestId("receive-stock-submit")).toBeInTheDocument();
  });

  it("does not render dialog content when open=false", () => {
    render(
      <ReceiveStockModal
        open={false}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );

    expect(screen.queryByLabelText(/^quantity/i)).toBeNull();
    expect(screen.queryByTestId("receive-stock-submit")).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// UX validation
// --------------------------------------------------------------------- //

describe("ReceiveStockModal — quantity validation", () => {
  it("disables submit when quantity is empty", () => {
    render(
      <ReceiveStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    expect(screen.getByTestId("receive-stock-submit")).toBeDisabled();
  });

  it.each([
    ["zero", "0"],
    ["negative", "-5"],
    ["non-integer", "1.5"],
    ["non-numeric", "abc"],
  ] as const)("disables submit when quantity is %s", (_label, value) => {
    render(
      <ReceiveStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    fireEvent.change(screen.getByLabelText(/^quantity/i), {
      target: { value },
    });
    expect(screen.getByTestId("receive-stock-submit")).toBeDisabled();
  });

  it("enables submit when quantity is a positive integer", () => {
    render(
      <ReceiveStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    fireEvent.change(screen.getByLabelText(/^quantity/i), {
      target: { value: "12" },
    });
    expect(screen.getByTestId("receive-stock-submit")).not.toBeDisabled();
  });
});

// --------------------------------------------------------------------- //
// Submit payload
// --------------------------------------------------------------------- //

describe("ReceiveStockModal — submit payload", () => {
  it("forwards required-only payload with null optionals when fields are empty", () => {
    const mutation = makeMutation();
    vi.mocked(inventoryHooks.useReceiveStockMutation).mockReturnValue(mutation);

    render(
      <ReceiveStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^quantity/i), {
      target: { value: "5" },
    });
    fireEvent.click(screen.getByTestId("receive-stock-submit"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      inventoryItemId: ITEM_ID,
      body: {
        quantity: 5,
        reason: null,
        reference_type: null,
        reference_id: null,
      },
    });
  });

  it("trims non-empty optional fields and sends them verbatim", () => {
    const mutation = makeMutation();
    vi.mocked(inventoryHooks.useReceiveStockMutation).mockReturnValue(mutation);

    render(
      <ReceiveStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^quantity/i), {
      target: { value: "7" },
    });
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "  Inbound shipment  " },
    });
    fireEvent.change(screen.getByLabelText(/reference type/i), {
      target: { value: "  purchase_order  " },
    });
    fireEvent.change(screen.getByLabelText(/reference id/i), {
      target: { value: "  po-7  " },
    });
    fireEvent.click(screen.getByTestId("receive-stock-submit"));

    expect(mutation.mutate).toHaveBeenCalledWith({
      inventoryItemId: ITEM_ID,
      body: {
        quantity: 7,
        reason: "Inbound shipment",
        reference_type: "purchase_order",
        reference_id: "po-7",
      },
    });
  });

  it("treats whitespace-only optional fields as null", () => {
    const mutation = makeMutation();
    vi.mocked(inventoryHooks.useReceiveStockMutation).mockReturnValue(mutation);

    render(
      <ReceiveStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^quantity/i), {
      target: { value: "3" },
    });
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "   " },
    });
    fireEvent.click(screen.getByTestId("receive-stock-submit"));

    expect(mutation.mutate).toHaveBeenCalledWith({
      inventoryItemId: ITEM_ID,
      body: {
        quantity: 3,
        reason: null,
        reference_type: null,
        reference_id: null,
      },
    });
  });

  it("treats whitespace-only reference_type and reference_id as null", () => {
    const mutation = makeMutation();
    vi.mocked(inventoryHooks.useReceiveStockMutation).mockReturnValue(mutation);

    render(
      <ReceiveStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );
    fireEvent.change(screen.getByLabelText(/^quantity/i), {
      target: { value: "9" },
    });
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "inbound count" },
    });
    fireEvent.change(screen.getByLabelText(/reference type/i), {
      target: { value: "   " },
    });
    fireEvent.change(screen.getByLabelText(/reference id/i), {
      target: { value: "   " },
    });
    fireEvent.click(screen.getByTestId("receive-stock-submit"));

    expect(mutation.mutate).toHaveBeenCalledWith({
      inventoryItemId: ITEM_ID,
      body: {
        quantity: 9,
        reason: "inbound count",
        reference_type: null,
        reference_id: null,
      },
    });
  });
});

// --------------------------------------------------------------------- //
// Pending / error / success
// --------------------------------------------------------------------- //

describe("ReceiveStockModal — server feedback", () => {
  it("disables every input + flips submit text while pending", () => {
    vi.mocked(inventoryHooks.useReceiveStockMutation).mockReturnValue(
      makeMutation({ isPending: true }),
    );

    render(
      <ReceiveStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    expect(screen.getByLabelText(/^quantity/i)).toBeDisabled();
    expect(screen.getByLabelText(/^reason/i)).toBeDisabled();
    expect(screen.getByLabelText(/reference type/i)).toBeDisabled();
    expect(screen.getByLabelText(/reference id/i)).toBeDisabled();

    const submit = screen.getByTestId("receive-stock-submit");
    expect(submit).toBeDisabled();
    expect(submit).toHaveTextContent(/receiving/i);
  });

  it("renders the backend ApiError detail inline", () => {
    vi.mocked(inventoryHooks.useReceiveStockMutation).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 422,
          message: "quantity must be a positive integer",
        }),
      }),
    );

    render(
      <ReceiveStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    expect(screen.getByTestId("receive-stock-error")).toHaveTextContent(
      /quantity must be a positive integer/i,
    );
  });

  it("calls onOpenChange(false) when the mutation reports success", () => {
    vi.mocked(inventoryHooks.useReceiveStockMutation).mockReturnValue(
      makeMutation({ isSuccess: true }),
    );

    const onOpenChange = vi.fn();
    render(
      <ReceiveStockModal
        open={true}
        onOpenChange={onOpenChange}
        item={makeItem()}
      />,
    );

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("calls mutation.reset on (re)open", () => {
    const mutation = makeMutation();
    vi.mocked(inventoryHooks.useReceiveStockMutation).mockReturnValue(mutation);

    render(
      <ReceiveStockModal open={true} onOpenChange={vi.fn()} item={makeItem()} />,
    );

    expect(mutation.reset).toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------- //
// Source-level architecture guards
// --------------------------------------------------------------------- //

describe("ReceiveStockModal — architecture", () => {
  it("does NOT import or reference useAuth / currentUser / role checks / fetch / axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "ReceiveStockModal.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/\buseAuth\b/);
    expect(code).not.toMatch(/\bcurrentUser\b/);
    expect(code).not.toMatch(/\.role\s*===/);
    expect(code).not.toMatch(/\bcanView\b/);
    expect(code).not.toMatch(/\bcanManage\b/);
    expect(code).not.toMatch(/\bcanCreate\b/);
    expect(code).not.toMatch(/\bhasPermission\b/);
    expect(code).not.toMatch(/\ballowedRoles\b/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
  });

  it("does NOT recompute stock authority", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "ReceiveStockModal.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/quantity_on_hand\s*[-+*/]/);
    expect(code).not.toMatch(/quantity_reserved\s*[-+*/]/);
    expect(code).not.toMatch(/quantity_after\s*=/);
  });

  it("does NOT use optimistic update / setQueryData / onMutate", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "ReceiveStockModal.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/setQueryData\s*\(/);
    expect(code).not.toMatch(/onMutate\s*:/);
    expect(code).not.toMatch(/\boptimistic\b/i);
  });
});
