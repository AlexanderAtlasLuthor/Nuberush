// F2.11-M2.2: tests for UpdateStatusModal.
//
// Differences from the other inventory modals:
//   - Form fields: a Radix `<Select>` constrained to the MVP-settable
//     subset (available / flagged / quarantined) + reason (required).
//   - Pre-fills `status` from item.status when current is one of the
//     MVP options; falls back to placeholder when current is "reserved"
//     or "sold" (derived states the backend rejects on this endpoint).
//   - Optional cosmetic warning when chosen status differs from
//     current — purely informational, doesn't gate submit.
//
// Radix Select interaction follows the proven Products / Audit
// pattern: click trigger by `id="status-select"` (or by accessible
// role), then click the option by accessible name.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { UpdateStatusModal } from "../UpdateStatusModal";
import * as inventoryHooks from "../../hooks";
import type { UpdateInventoryStatusParams } from "../../api";
import type { InventoryItem } from "../../types";

vi.mock("../../hooks", () => ({
  useUpdateInventoryStatusMutation: vi.fn(),
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
  UpdateInventoryStatusParams
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
    UpdateInventoryStatusParams
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
    inventoryHooks.useUpdateInventoryStatusMutation,
  ).mockReset();
  vi.mocked(
    inventoryHooks.useUpdateInventoryStatusMutation,
  ).mockReturnValue(makeMutation());
});

afterEach(() => {
  vi.clearAllMocks();
});

// --------------------------------------------------------------------- //
// Open / closed
// --------------------------------------------------------------------- //

describe("UpdateStatusModal — render gating", () => {
  it("renders fields when open=true", () => {
    render(
      <UpdateStatusModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );

    expect(screen.getByLabelText(/^status/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^reason/i)).toBeInTheDocument();
    expect(screen.getByTestId("update-status-submit")).toBeInTheDocument();
  });

  it("does not render when open=false", () => {
    render(
      <UpdateStatusModal
        open={false}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );

    expect(screen.queryByLabelText(/^status/i)).toBeNull();
    expect(screen.queryByTestId("update-status-submit")).toBeNull();
  });
});

// --------------------------------------------------------------------- //
// Status options + pre-fill
// --------------------------------------------------------------------- //

describe("UpdateStatusModal — status options", () => {
  it("renders exactly the three MVP-settable options (available / flagged / quarantined)", () => {
    render(
      <UpdateStatusModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );

    fireEvent.click(screen.getByLabelText(/^status/i));

    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(3);
    expect(options.map((option) => option.textContent)).toEqual([
      "Available",
      "Flagged",
      "Quarantined",
    ]);
    // No "reserved" or "sold" — those are derived states the backend
    // rejects on this endpoint.
    expect(
      screen.queryByRole("option", { name: /^reserved$/i }),
    ).toBeNull();
    expect(
      screen.queryByRole("option", { name: /^sold$/i }),
    ).toBeNull();
  });
});

describe("UpdateStatusModal — pre-fill", () => {
  it("pre-fills the select with item.status when it is in the MVP subset", () => {
    render(
      <UpdateStatusModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem({ status: "flagged" })}
      />,
    );

    // Radix Select shows the selected value text inside the trigger.
    expect(screen.getByLabelText(/^status/i)).toHaveTextContent(/flagged/i);
  });

  it.each(["reserved", "sold"] as const)(
    "leaves the select empty (placeholder visible) when item.status is %s (derived state)",
    (derivedStatus) => {
      render(
        <UpdateStatusModal
          open={true}
          onOpenChange={vi.fn()}
          item={makeItem({ status: derivedStatus })}
        />,
      );

      // Trigger renders the placeholder copy when no MVP option is
      // selected. The placeholder text is "Select a status".
      expect(
        screen.getByLabelText(/^status/i),
      ).toHaveTextContent(/select a status/i);
    },
  );
});

// --------------------------------------------------------------------- //
// Validation
// --------------------------------------------------------------------- //

describe("UpdateStatusModal — validation", () => {
  it("disables submit when status is not picked (placeholder shown)", () => {
    render(
      <UpdateStatusModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem({ status: "reserved" })}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "any reason" },
    });
    expect(screen.getByTestId("update-status-submit")).toBeDisabled();
  });

  it("disables submit when reason is empty / whitespace-only", () => {
    render(
      <UpdateStatusModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem({ status: "available" })}
      />,
    );
    // Reason left empty.
    expect(screen.getByTestId("update-status-submit")).toBeDisabled();

    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "   " },
    });
    expect(screen.getByTestId("update-status-submit")).toBeDisabled();
  });

  it("enables submit with status selected + non-empty reason", () => {
    render(
      <UpdateStatusModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem({ status: "available" })}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "compliance hold" },
    });
    expect(screen.getByTestId("update-status-submit")).not.toBeDisabled();
  });
});

// --------------------------------------------------------------------- //
// Cosmetic warning when status changes
// --------------------------------------------------------------------- //

describe("UpdateStatusModal — cosmetic warning", () => {
  it("does NOT render the warning when chosen status equals item.status", () => {
    render(
      <UpdateStatusModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem({ status: "available" })}
      />,
    );

    expect(screen.queryByTestId("update-status-warning")).toBeNull();
  });

  it("renders the warning when chosen status differs from item.status", () => {
    render(
      <UpdateStatusModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem({ status: "available" })}
      />,
    );

    // Change select to "flagged".
    fireEvent.click(screen.getByLabelText(/^status/i));
    fireEvent.click(screen.getByRole("option", { name: /flagged/i }));

    expect(screen.getByTestId("update-status-warning")).toBeInTheDocument();
    expect(
      screen.getByTestId("update-status-warning"),
    ).toHaveTextContent(/may affect/i);
  });

  it("warning is cosmetic — does NOT disable submit when status differs", () => {
    render(
      <UpdateStatusModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem({ status: "available" })}
      />,
    );

    fireEvent.click(screen.getByLabelText(/^status/i));
    fireEvent.click(screen.getByRole("option", { name: /flagged/i }));
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "compliance hold" },
    });

    expect(screen.getByTestId("update-status-warning")).toBeInTheDocument();
    expect(screen.getByTestId("update-status-submit")).not.toBeDisabled();
  });
});

// --------------------------------------------------------------------- //
// Submit payload
// --------------------------------------------------------------------- //

describe("UpdateStatusModal — submit payload", () => {
  it("forwards { status, reason } verbatim", () => {
    const mutation = makeMutation();
    vi.mocked(
      inventoryHooks.useUpdateInventoryStatusMutation,
    ).mockReturnValue(mutation);

    render(
      <UpdateStatusModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem({ status: "available" })}
      />,
    );

    fireEvent.click(screen.getByLabelText(/^status/i));
    fireEvent.click(screen.getByRole("option", { name: /quarantined/i }));
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "  FDA recall  " },
    });
    fireEvent.click(screen.getByTestId("update-status-submit"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      inventoryItemId: ITEM_ID,
      body: {
        status: "quarantined",
        reason: "FDA recall",
      },
    });
  });
});

// --------------------------------------------------------------------- //
// Pending / error / success
// --------------------------------------------------------------------- //

describe("UpdateStatusModal — server feedback", () => {
  it("disables every input + flips submit text while pending", () => {
    vi.mocked(
      inventoryHooks.useUpdateInventoryStatusMutation,
    ).mockReturnValue(makeMutation({ isPending: true }));

    render(
      <UpdateStatusModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem({ status: "available" })}
      />,
    );

    expect(screen.getByLabelText(/^status/i)).toBeDisabled();
    expect(screen.getByLabelText(/^reason/i)).toBeDisabled();
    const submit = screen.getByTestId("update-status-submit");
    expect(submit).toBeDisabled();
    expect(submit).toHaveTextContent(/updating/i);
  });

  it("renders backend ApiError detail inline", () => {
    vi.mocked(
      inventoryHooks.useUpdateInventoryStatusMutation,
    ).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 422,
          message: "status transition not permitted",
        }),
      }),
    );

    render(
      <UpdateStatusModal
        open={true}
        onOpenChange={vi.fn()}
        item={makeItem()}
      />,
    );

    expect(screen.getByTestId("update-status-error")).toHaveTextContent(
      /status transition not permitted/i,
    );
  });

  it("calls onOpenChange(false) on success", () => {
    vi.mocked(
      inventoryHooks.useUpdateInventoryStatusMutation,
    ).mockReturnValue(makeMutation({ isSuccess: true }));

    const onOpenChange = vi.fn();
    render(
      <UpdateStatusModal
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
      inventoryHooks.useUpdateInventoryStatusMutation,
    ).mockReturnValue(mutation);

    render(
      <UpdateStatusModal
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

describe("UpdateStatusModal — architecture", () => {
  it("does NOT import useAuth / currentUser / role checks / fetch / axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "UpdateStatusModal.tsx");
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

  it("does NOT encode a frontend status-transition matrix", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "UpdateStatusModal.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    // Forbidden — would mean the frontend decides which status changes
    // are allowed. Backend enforces transition rules; the static
    // STATUS_OPTIONS list is fine (those are the operator-pickable
    // values, not a transition matrix).
    expect(code).not.toMatch(/_ALLOWED_TRANSITIONS\s*=/);
    expect(code).not.toMatch(/transitionMatrix\s*=/);
    expect(code).not.toMatch(/canTransitionTo\s*\(/);
    expect(code).not.toMatch(/isTransitionValid\s*\(/);
  });

  it("does NOT use compliance/stock decisions or optimistic updates", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "UpdateStatusModal.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/quantity_on_hand\s*[-+*/]/);
    expect(code).not.toMatch(/quantity_reserved\s*[-+*/]/);
    expect(code).not.toMatch(/compliance_status\s*===\s*["']banned/);
    expect(code).not.toMatch(/setQueryData\s*\(/);
    expect(code).not.toMatch(/onMutate\s*:/);
  });
});
