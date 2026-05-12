// F2.11-M2.5: tests for TransitionStatusDialog.
//
// The dialog confirms an operator-selected target status and forwards
// only { new_status } to the mutation. Backend transition validity,
// authorization, totals, stock effects and audit logs remain
// server-owned.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import type { UseMutationResult } from "@tanstack/react-query";

import { ApiError } from "@/api";
import { TransitionStatusDialog } from "../TransitionStatusDialog";
import * as ordersHooks from "../../hooks";
import type { TransitionOrderStatusParams } from "../../api";
import type { OrderRead } from "../../types";

vi.mock("../../hooks", () => ({
  useTransitionOrderStatusMutation: vi.fn(),
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
): UseMutationResult<OrderRead, Error, TransitionOrderStatusParams> & {
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
    OrderRead,
    Error,
    TransitionOrderStatusParams
  > & {
    mutate: ReturnType<typeof vi.fn>;
    reset: ReturnType<typeof vi.fn>;
  };
}

function makeOrder(overrides: Partial<OrderRead> = {}): OrderRead {
  return {
    id: ORDER_ID,
    store_id: STORE_ID,
    customer_user_id: null,
    idempotency_key: "transition-dialog-fixture",
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
  vi.mocked(ordersHooks.useTransitionOrderStatusMutation).mockReset();
  vi.mocked(ordersHooks.useTransitionOrderStatusMutation).mockReturnValue(
    makeMutation(),
  );
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("TransitionStatusDialog - render gating", () => {
  it("renders confirmation content when open=true and targetStatus is provided", () => {
    render(
      <TransitionStatusDialog
        open={true}
        onOpenChange={vi.fn()}
        order={makeOrder()}
        targetStatus="accepted"
      />,
    );

    expect(
      screen.getByRole("heading", { name: /confirm status change/i }),
    ).toBeInTheDocument();
    expect(screen.getByText(ORDER_ID)).toBeInTheDocument();
    expect(screen.getByText("accepted")).toBeInTheDocument();
    expect(screen.getByTestId("transition-status-confirm")).toBeEnabled();
  });

  it("does not render actionable content when open=false", () => {
    render(
      <TransitionStatusDialog
        open={false}
        onOpenChange={vi.fn()}
        order={makeOrder()}
        targetStatus="accepted"
      />,
    );

    expect(screen.queryByTestId("transition-status-confirm")).toBeNull();
    expect(
      screen.queryByRole("heading", { name: /confirm status change/i }),
    ).toBeNull();
  });

  it("disables confirm when targetStatus is null", () => {
    render(
      <TransitionStatusDialog
        open={true}
        onOpenChange={vi.fn()}
        order={makeOrder()}
        targetStatus={null}
      />,
    );

    expect(screen.getByTestId("transition-status-confirm")).toBeDisabled();
  });
});

describe("TransitionStatusDialog - submit payload", () => {
  it("calls mutate with orderId and new_status targetStatus", () => {
    const mutation = makeMutation();
    vi.mocked(ordersHooks.useTransitionOrderStatusMutation).mockReturnValue(
      mutation,
    );

    render(
      <TransitionStatusDialog
        open={true}
        onOpenChange={vi.fn()}
        order={makeOrder()}
        targetStatus="preparing"
      />,
    );
    fireEvent.click(screen.getByTestId("transition-status-confirm"));

    expect(mutation.mutate).toHaveBeenCalledTimes(1);
    expect(mutation.mutate).toHaveBeenCalledWith({
      orderId: ORDER_ID,
      body: {
        new_status: "preparing",
      },
    });
  });

  it("does not call mutate when targetStatus is null", () => {
    const mutation = makeMutation();
    vi.mocked(ordersHooks.useTransitionOrderStatusMutation).mockReturnValue(
      mutation,
    );

    render(
      <TransitionStatusDialog
        open={true}
        onOpenChange={vi.fn()}
        order={makeOrder()}
        targetStatus={null}
      />,
    );
    fireEvent.click(screen.getByTestId("transition-status-confirm"));

    expect(mutation.mutate).not.toHaveBeenCalled();
  });
});

describe("TransitionStatusDialog - server feedback", () => {
  it("disables cancel and confirm controls while pending", () => {
    vi.mocked(ordersHooks.useTransitionOrderStatusMutation).mockReturnValue(
      makeMutation({ isPending: true }),
    );

    render(
      <TransitionStatusDialog
        open={true}
        onOpenChange={vi.fn()}
        order={makeOrder()}
        targetStatus="accepted"
      />,
    );

    expect(screen.getByRole("button", { name: /^cancel$/i })).toBeDisabled();
    const confirm = screen.getByTestId("transition-status-confirm");
    expect(confirm).toBeDisabled();
    expect(confirm).toHaveTextContent(/updating/i);
  });

  it("does not close from the disabled Cancel button while pending", () => {
    vi.mocked(ordersHooks.useTransitionOrderStatusMutation).mockReturnValue(
      makeMutation({ isPending: true }),
    );
    const onOpenChange = vi.fn();

    render(
      <TransitionStatusDialog
        open={true}
        onOpenChange={onOpenChange}
        order={makeOrder()}
        targetStatus="accepted"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: /^cancel$/i }));
    expect(onOpenChange).not.toHaveBeenCalled();
  });

  it("renders backend ApiError detail inline", () => {
    vi.mocked(ordersHooks.useTransitionOrderStatusMutation).mockReturnValue(
      makeMutation({
        isError: true,
        error: new ApiError({
          status: 422,
          message: "status transition not permitted",
        }),
      }),
    );

    render(
      <TransitionStatusDialog
        open={true}
        onOpenChange={vi.fn()}
        order={makeOrder()}
        targetStatus="ready"
      />,
    );

    expect(screen.getByTestId("transition-status-error")).toHaveTextContent(
      /status transition not permitted/i,
    );
  });

  it("calls onOpenChange(false) when the mutation reports success", () => {
    vi.mocked(ordersHooks.useTransitionOrderStatusMutation).mockReturnValue(
      makeMutation({ isSuccess: true }),
    );
    const onOpenChange = vi.fn();

    render(
      <TransitionStatusDialog
        open={true}
        onOpenChange={onOpenChange}
        order={makeOrder()}
        targetStatus="accepted"
      />,
    );

    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("calls mutation.reset on open", () => {
    const mutation = makeMutation();
    vi.mocked(ordersHooks.useTransitionOrderStatusMutation).mockReturnValue(
      mutation,
    );

    render(
      <TransitionStatusDialog
        open={true}
        onOpenChange={vi.fn()}
        order={makeOrder()}
        targetStatus="accepted"
      />,
    );

    expect(mutation.reset).toHaveBeenCalled();
  });
});

describe("TransitionStatusDialog - architecture", () => {
  it("does NOT import auth, role checks, transition matrices, order totals, fetch, or axios", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "TransitionStatusDialog.tsx");
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
    expect(code).not.toMatch(/NEXT_FORWARD_TRANSITIONS\s*=/);
    expect(code).not.toMatch(/CANCELABLE_STATUSES\s*=/);
    expect(code).not.toMatch(/RETURNABLE_STATUSES\s*=/);
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
    const here = path.resolve(__dirname, "..", "TransitionStatusDialog.tsx");
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
