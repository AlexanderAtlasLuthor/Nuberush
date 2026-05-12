// F2.11-M2.5: tests for CancelOrderModal.
//
// The modal is a thin form over useCancelOrderMutation. These tests
// validate UX guards and payload shape only; backend transition,
// authorization, tenancy, stock, totals and audit behavior stay
// server-owned.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { CancelOrderModal } from "../CancelOrderModal";
import * as ordersHooks from "../../hooks";
import type { CancelOrderParams } from "../../api";
import type { OrderRead } from "../../types";

vi.mock("../../hooks", () => ({
  useCancelOrderMutation: vi.fn(),
}));

const ORDER_ID = "11111111-1111-1111-1111-111111111111";
const STORE_ID = "22222222-2222-2222-2222-222222222222";

interface MutationOverrides {
  isPending?: boolean;
  isSuccess?: boolean;
  isError?: boolean;
  error?: Error | null;
}

function makeMutation(
  o: MutationOverrides = {},
): UseMutationResult<OrderRead, Error, CancelOrderParams> & {
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
  } as unknown as UseMutationResult<OrderRead, Error, CancelOrderParams> & {
    mutate: ReturnType<typeof vi.fn>;
    reset: ReturnType<typeof vi.fn>;
  };
}

function makeOrder(overrides: Partial<OrderRead> = {}): OrderRead {
  return {
    id: ORDER_ID,
    store_id: STORE_ID,
    customer_user_id: null,
    idempotency_key: "cancel-modal-fixture",
    status: "pending",
    subtotal_amount: "20.00",
    tax_amount: "1.40",
    total_amount: "21.40",
    age_verified_at: null,
    age_verified_by_user_id: null,
    accepted_at: null,
    canceled_at: null,
    delivered_at: null,
    returned_at: null,
    cancel_reason: null,
    notes: null,
    created_at: "2026-05-01T00:00:00Z",
    updated_at: "2026-05-01T00:00:00Z",
    items: [],
    ...overrides,
  };
}

beforeEach(() => {
  vi.mocked(ordersHooks.useCancelOrderMutation).mockReset();
  vi.mocked(ordersHooks.useCancelOrderMutation).mockReturnValue(
    makeMutation(),
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("CancelOrderModal - render gating", () => {
  it("renders fields when open=true", () => {
    render(
      <CancelOrderModal
        open={true}
        onOpenChange={vi.fn()}
        order={makeOrder()}
      />,
    );

    expect(screen.getByLabelText(/^reason/i)).toBeInTheDocument();
    expect(screen.getByTestId("cancel-order-confirm")).toBeInTheDocument();
  });

  it("does not render dialog content when open=false", () => {
    render(
      <CancelOrderModal
        open={false}
        onOpenChange={vi.fn()}
        order={makeOrder()}
      />,
    );

    expect(screen.queryByLabelText(/^reason/i)).toBeNull();
    expect(screen.queryByTestId("cancel-order-confirm")).toBeNull();
  });
});

describe("CancelOrderModal - validation", () => {
  it("disables submit when reason is empty or whitespace-only", () => {
    render(
      <CancelOrderModal
        open={true}
        onOpenChange={vi.fn()}
        order={makeOrder()}
      />,
    );

    expect(screen.getByTestId("cancel-order-confirm")).toBeDisabled();
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "   " },
    });
    expect(screen.getByTestId("cancel-order-confirm")).toBeDisabled();
  });

  it("enables submit when reason is non-empty after trim", () => {
    render(
      <CancelOrderModal
        open={true}
        onOpenChange={vi.fn()}
        order={makeOrder()}
      />,
    );

    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "customer requested cancellation" },
    });
    expect(screen.getByTestId("cancel-order-confirm")).not.toBeDisabled();
  });
});

describe("CancelOrderModal - submit payload", () => {
  it("calls mutate with orderId and trimmed reason", () => {
    const mutation = makeMutation();
    vi.mocked(ordersHooks.useCancelOrderMutation).mockReturnValue(mutation);

    render(
      <CancelOrderModal
        open={true}
        onOpenChange={vi.fn()}
        order={makeOrder()}
      />,
    );
    fireEvent.change(screen.getByLabelText(/^reason/i), {
      target: { value: "  customer changed plans  " },
    });
    fireEvent.click(screen.getByTestId("cancel-order-confirm"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      orderId: ORDER_ID,
      body: {
        reason: "customer changed plans",
      },
    });
  });
});

describe("CancelOrderModal - server feedback", () => {
  it("disables reason, cancel, and submit controls while pending", () => {
    vi.mocked(ordersHooks.useCancelOrderMutation).mockReturnValue(
      makeMutation({ isPending: true }),
    );

    render(
      <CancelOrderModal
        open={true}
        onOpenChange={vi.fn()}
        order={makeOrder()}
      />,
    );

    expect(screen.getByLabelText(/^reason/i)).toBeDisabled();
    expect(screen.getByRole("button", { name: /^cancel$/i })).toBeDisabled();
    const submit = screen.getByTestId("cancel-order-confirm");
    expect(submit).toBeDisabled();
    expect(submit).toHaveTextContent(/canceling/i);
  });

  it("does not close from the disabled Cancel button while pending", () => {
    vi.mocked(ordersHooks.useCancelOrderMutation).mockReturnValue(
      makeMutation({ isPending: true }),
    );
    const onOpenChange = vi.fn();

    render(
      <CancelOrderModal
        open={true}
        onOpenChange={onOpenChange}
        order={makeOrder()}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /^cancel$/i }));
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it("renders backend ApiError detail inline", () => {
    vi.mocked(ordersHooks.useCancelOrderMutation).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 422,
          message: "order cannot be canceled from this state",
        }),
      }),
    );

    render(
      <CancelOrderModal
        open={true}
        onOpenChange={vi.fn()}
        order={makeOrder()}
      />,
    );

    expect(screen.getByTestId("cancel-order-error")).toHaveTextContent(
      /order cannot be canceled from this state/i,
    );
  });

  it("calls onOpenChange(false) when the mutation reports success", () => {
    vi.mocked(ordersHooks.useCancelOrderMutation).mockReturnValue(
      makeMutation({ isSuccess: true }),
    );
    const onOpenChange = vi.fn();

    render(
      <CancelOrderModal
        open={true}
        onOpenChange={onOpenChange}
        order={makeOrder()}
      />,
    );

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("calls mutation.reset on open", () => {
    const mutation = makeMutation();
    vi.mocked(ordersHooks.useCancelOrderMutation).mockReturnValue(mutation);

    render(
      <CancelOrderModal
        open={true}
        onOpenChange={vi.fn()}
        order={makeOrder()}
      />,
    );

    expect(mutation.reset).toHaveBeenCalled();
  });
});

describe("CancelOrderModal - architecture", () => {
  it("does NOT import auth, role checks, transition logic, order totals, fetch, or axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "CancelOrderModal.tsx");
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
    expect(code).not.toMatch(/_ALLOWED_TRANSITIONS\s*=/);
    expect(code).not.toMatch(/transitionMatrix\s*=/);
    expect(code).not.toMatch(/canTransitionTo\s*\(/);
    expect(code).not.toMatch(/subtotal_amount\s*[-+*/]/);
    expect(code).not.toMatch(/tax_amount\s*[-+*/]/);
    expect(code).not.toMatch(/total_amount\s*[-+*/]/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
  });

  it("does NOT use optimistic updates or direct query cache mutation", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "CancelOrderModal.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/setQueryData\s*\(/);
    expect(code).not.toMatch(/invalidateQueries\s*\(/);
    expect(code).not.toMatch(/onMutate\s*:/);
    expect(code).not.toMatch(/\boptimistic\b/i);
  });
});
