// F2.11-M2.2: tests for UpdateThresholdModal.
//
// Single-field form (`reorder_threshold`) with backend constraint
// `int >= 0`. Pre-fills from item.reorder_threshold on open. The
// frontend NEVER decides whether the item is "low stock" — that
// classification belongs to the backend / list filter, locked by
// architecture guard.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { UpdateThresholdModal } from "../UpdateThresholdModal";
import * as inventoryHooks from "../../hooks";
import type { UpdateInventoryThresholdParams } from "../../api";
import type { InventoryItem } from "../../types";

vi.mock("../../hooks", () => ({
  useUpdateInventoryThresholdMutation: vi.fn(),
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
): UseMutationResult<
  InventoryItem,
  Error,
  UpdateInventoryThresholdParams
> & {
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
    UpdateInventoryThresholdParams
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
  vi.mocked(
    inventoryHooks.useUpdateInventoryThresholdMutation,
  ).mockReset();
  vi.mocked(
    inventoryHooks.useUpdateInventoryThresholdMutation,
  ).mockReturnValue(makeMutation());
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Open / closed
// --------------------------------------------------------------------- //

describe("UpdateThresholdModal — render gating", () => {
  it("renders the threshold field when open=true", () => {
    render(
      <UpdateThresholdModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );

    expect(screen.getByLabelText(/^threshold/i)).toBeInTheDocument();
    expect(screen.getByTestId("update-threshold-submit")).toBeInTheDocument();
  });

  it("does not render when open=false", () => {
    render(
      <UpdateThresholdModal
        open={false}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );

    expect(screen.queryByLabelText(/^threshold/i)).toBeNull();
    expect(screen.queryByTestId("update-threshold-submit")).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// Pre-fill
// --------------------------------------------------------------------- //

describe("UpdateThresholdModal — pre-fill", () => {
  it("pre-fills the input from item.reorder_threshold on open", () => {
    render(
      <UpdateThresholdModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem({ reorder_threshold: 25 })}
      />,
    );

    expect(screen.getByLabelText(/^threshold/i)).toHaveValue(25);
  });

  it("pre-fills 0 when item.reorder_threshold is 0", () => {
    render(
      <UpdateThresholdModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem({ reorder_threshold: 0 })}
      />,
    );

    expect(screen.getByLabelText(/^threshold/i)).toHaveValue(0);
  });
});

// --------------------------------------------------------------------- //
// Validation
// --------------------------------------------------------------------- //

describe("UpdateThresholdModal — validation", () => {
  it("disables submit when threshold is empty", () => {
    render(
      <UpdateThresholdModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^threshold/i), {
      target: { value: "" },
    });
    expect(screen.getByTestId("update-threshold-submit")).toBeDisabled();
  });

  it("disables submit when threshold is negative", () => {
    render(
      <UpdateThresholdModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^threshold/i), {
      target: { value: "-1" },
    });
    expect(screen.getByTestId("update-threshold-submit")).toBeDisabled();
  });

  it("disables submit when threshold is non-integer", () => {
    render(
      <UpdateThresholdModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^threshold/i), {
      target: { value: "1.5" },
    });
    expect(screen.getByTestId("update-threshold-submit")).toBeDisabled();
  });

  it("accepts threshold = 0 (disables low-stock alerts)", () => {
    render(
      <UpdateThresholdModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem({ reorder_threshold: 5 })}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^threshold/i), {
      target: { value: "0" },
    });
    expect(screen.getByTestId("update-threshold-submit")).not.toBeDisabled();
  });

  it("accepts a positive integer threshold", () => {
    render(
      <UpdateThresholdModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^threshold/i), {
      target: { value: "20" },
    });
    expect(screen.getByTestId("update-threshold-submit")).not.toBeDisabled();
  });
});

// --------------------------------------------------------------------- //
// Submit payload
// --------------------------------------------------------------------- //

describe("UpdateThresholdModal — submit payload", () => {
  it("forwards { reorder_threshold } verbatim", () => {
    const mutation = makeMutation();
    vi.mocked(
      inventoryHooks.useUpdateInventoryThresholdMutation,
    ).mockReturnValue(mutation);

    render(
      <UpdateThresholdModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^threshold/i), {
      target: { value: "15" },
    });
    fireEvent.click(screen.getByTestId("update-threshold-submit"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      inventoryItemId: ITEM_ID,
      body: {
        reorder_threshold: 15,
      },
    });
  });
});

// --------------------------------------------------------------------- //
// Pending / error / success
// --------------------------------------------------------------------- //

describe("UpdateThresholdModal — server feedback", () => {
  it("disables the input + flips submit text while pending", () => {
    vi.mocked(
      inventoryHooks.useUpdateInventoryThresholdMutation,
    ).mockReturnValue(makeMutation({ isPending: true }));

    render(
      <UpdateThresholdModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );

    expect(screen.getByLabelText(/^threshold/i)).toBeDisabled();
    const submit = screen.getByTestId("update-threshold-submit");
    expect(submit).toBeDisabled();
    expect(submit).toHaveTextContent(/saving/i);
  });

  it("renders backend ApiError detail inline", () => {
    vi.mocked(
      inventoryHooks.useUpdateInventoryThresholdMutation,
    ).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 422,
          message: "reorder_threshold must be >= 0",
        }),
      }),
    );

    render(
      <UpdateThresholdModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );

    expect(screen.getByTestId("update-threshold-error")).toHaveTextContent(
      /reorder_threshold must be >= 0/i,
    );
  });

  it("calls onOpenChange(false) on success", () => {
    vi.mocked(
      inventoryHooks.useUpdateInventoryThresholdMutation,
    ).mockReturnValue(makeMutation({ isSuccess: true }));

    const onOpenChange = vi.fn();
    render(
      <UpdateThresholdModal
        open={true}
        onOpenChange={onOpenChange}
        item={makeItem()}
      />,
    );

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("calls mutation.reset on (re)open", () => {
    const mutation = makeMutation();
    vi.mocked(
      inventoryHooks.useUpdateInventoryThresholdMutation,
    ).mockReturnValue(mutation);

    render(
      <UpdateThresholdModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );

    expect(mutation.reset).toHaveBeenCalled();
  });
});

// --------------------------------------------------------------------- //
// Source-level architecture guards
// --------------------------------------------------------------------- //

describe("UpdateThresholdModal — architecture", () => {
  it("does NOT import useAuth / currentUser / role checks / fetch / axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "UpdateThresholdModal.tsx");
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

  it("does NOT compute a local low-stock decision", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "UpdateThresholdModal.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    // Forbidden — these would mean the frontend classifies the item
    // as "low stock", which is a backend / list-filter decision.
    expect(code).not.toMatch(/\bisLowStock\b/);
    expect(code).not.toMatch(/\blowStock\b/);
    expect(code).not.toMatch(/quantity_on_hand\s*<=/);
    expect(code).not.toMatch(/quantity_on_hand\s*<\s/);
    expect(code).not.toMatch(/quantity_on_hand\s*[-+*/]/);
    expect(code).not.toMatch(/quantity_reserved\s*[-+*/]/);
  });

  it("does NOT use optimistic update / setQueryData", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "UpdateThresholdModal.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/setQueryData\s*\(/);
    expect(code).not.toMatch(/onMutate\s*:/);
  });
});
