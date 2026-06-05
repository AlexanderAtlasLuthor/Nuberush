// F2.11-M2.5: tests for OrderActionsBar.
//
// OrderActionsBar owns UI affordances and open-state wiring only. The
// child dialog/modal components are replaced with small test doubles so
// this file does not exercise mutation hooks or modal internals.

import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

import { OrderActionsBar } from "../OrderActionsBar";
import { orderStatusLabel } from "../../labels";
import type { OrderRead, OrderStatus } from "../../types";

vi.mock("../TransitionStatusDialog", () => ({
  TransitionStatusDialog: ({
    open,
    order,
    targetStatus,
  }: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    order: OrderRead;
    targetStatus: OrderStatus | null;
  }) =>
    open ? (
      <div
        data-testid="mock-transition-status-dialog"
        data-order-id={order.id}
        data-target-status={targetStatus ?? ""}
      >
        transition
      </div>
    ) : null,
}));

vi.mock("../CancelOrderModal", () => ({
  CancelOrderModal: ({
    open,
    order,
  }: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    order: OrderRead;
  }) =>
    open ? (
      <div data-testid="mock-cancel-order-modal" data-order-id={order.id}>
        cancel
      </div>
    ) : null,
}));

vi.mock("../ReturnOrderModal", () => ({
  ReturnOrderModal: ({
    open,
    order,
  }: {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    order: OrderRead;
  }) =>
    open ? (
      <div data-testid="mock-return-order-modal" data-order-id={order.id}>
        return
      </div>
    ) : null,
}));

const ORDER_ID = "11111111-1111-1111-1111-111111111111";
const STORE_ID = "22222222-2222-2222-2222-222222222222";
const VARIANT_ID = "33333333-3333-3333-3333-333333333333";
const ITEM_ID = "44444444-4444-4444-4444-444444444444";
const PRODUCT_ID = "55555555-5555-5555-5555-555555555555";
const ALL_FORWARD_TARGETS: readonly OrderStatus[] = [
  "accepted",
  "preparing",
  "ready",
  "out_for_delivery",
  "delivered",
];

function makeOrder(overrides: Partial<OrderRead> = {}): OrderRead {
  return {
    id: ORDER_ID,
    store_id: STORE_ID,
    customer_user_id: null,
    idempotency_key: "order-actions-fixture",
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
    items: [
      {
        id: "line-1",
        order_id: ORDER_ID,
        variant_id: VARIANT_ID,
        inventory_item_id: ITEM_ID,
        quantity: 2,
        unit_price: "10.00",
        line_total: "20.00",
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
      },
    ],
    ...overrides,
  };
}

afterEach(() => {
  vi.clearAllMocks();
});

describe("OrderActionsBar - UI affordances", () => {
  it.each([
    [
      "pending",
      { transitions: ["accepted"], cancel: true, return: false, terminal: false },
    ],
    [
      "accepted",
      { transitions: ["preparing"], cancel: true, return: false, terminal: false },
    ],
    [
      "preparing",
      { transitions: ["ready"], cancel: true, return: false, terminal: false },
    ],
    [
      "ready",
      {
        transitions: ["out_for_delivery", "delivered"],
        cancel: true,
        return: false,
        terminal: false,
      },
    ],
    [
      "out_for_delivery",
      { transitions: ["delivered"], cancel: true, return: false, terminal: false },
    ],
    [
      "delivered",
      { transitions: [], cancel: false, return: true, terminal: false },
    ],
    [
      "canceled",
      { transitions: [], cancel: false, return: false, terminal: true },
    ],
    [
      "returned",
      { transitions: [], cancel: false, return: false, terminal: true },
    ],
  ] as Array<
    [
      OrderStatus,
      {
        transitions: OrderStatus[];
        cancel: boolean;
        return: boolean;
        terminal: boolean;
      },
    ]
  >)(
    "renders documented UI affordances for %s without asserting backend validity",
    (status, expected) => {
      render(<OrderActionsBar order={makeOrder({ status })} />);

      expect(screen.getByTestId("order-actions-current-status")).toHaveTextContent(
        orderStatusLabel(status),
      );

      for (const target of expected.transitions) {
        expect(
          screen.getByTestId(`order-action-transition-${target}`),
        ).toBeInTheDocument();
      }

      const absentTargets = ALL_FORWARD_TARGETS.filter(
        (target) => !expected.transitions.includes(target),
      );
      for (const target of absentTargets) {
        expect(
          screen.queryByTestId(`order-action-transition-${target}`),
        ).toBeNull();
      }

      if (expected.cancel) {
        expect(screen.getByTestId("order-action-cancel")).toBeInTheDocument();
      } else {
        expect(screen.queryByTestId("order-action-cancel")).toBeNull();
      }

      if (expected.return) {
        expect(screen.getByTestId("order-action-return")).toBeInTheDocument();
      } else {
        expect(screen.queryByTestId("order-action-return")).toBeNull();
      }

      if (expected.terminal) {
        expect(screen.getByTestId("order-actions-terminal")).toHaveTextContent(
          /no further actions are available/i,
        );
      } else {
        expect(screen.queryByTestId("order-actions-terminal")).toBeNull();
      }
    },
  );
});

describe("OrderActionsBar - action wiring", () => {
  it("clicking a forward transition opens TransitionStatusDialog with order and targetStatus", () => {
    render(<OrderActionsBar order={makeOrder({ status: "ready" })} />);

    fireEvent.click(screen.getByTestId("order-action-transition-delivered"));

    const dialog = screen.getByTestId("mock-transition-status-dialog");
    expect(dialog).toHaveAttribute("data-order-id", ORDER_ID);
    expect(dialog).toHaveAttribute("data-target-status", "delivered");
    expect(screen.queryByTestId("mock-cancel-order-modal")).toBeNull();
    expect(screen.queryByTestId("mock-return-order-modal")).toBeNull();
  });

  it("clicking Cancel opens CancelOrderModal with the order prop only", () => {
    render(<OrderActionsBar order={makeOrder({ status: "accepted" })} />);

    fireEvent.click(screen.getByTestId("order-action-cancel"));

    const modal = screen.getByTestId("mock-cancel-order-modal");
    expect(modal).toHaveAttribute("data-order-id", ORDER_ID);
    expect(screen.queryByTestId("mock-transition-status-dialog")).toBeNull();
    expect(screen.queryByTestId("mock-return-order-modal")).toBeNull();
  });

  it("clicking Return opens ReturnOrderModal with the order prop only", () => {
    render(<OrderActionsBar order={makeOrder({ status: "delivered" })} />);

    fireEvent.click(screen.getByTestId("order-action-return"));

    const modal = screen.getByTestId("mock-return-order-modal");
    expect(modal).toHaveAttribute("data-order-id", ORDER_ID);
    expect(screen.queryByTestId("mock-transition-status-dialog")).toBeNull();
    expect(screen.queryByTestId("mock-cancel-order-modal")).toBeNull();
  });
});

describe("OrderActionsBar - architecture", () => {
  it("does NOT call mutation hooks, API helpers, fetch, axios, or auth/permission logic", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "OrderActionsBar.tsx");
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
    expect(code).not.toMatch(/\buseTransitionOrderStatusMutation\b/);
    expect(code).not.toMatch(/\buseCancelOrderMutation\b/);
    expect(code).not.toMatch(/\buseReturnOrderMutation\b/);
    expect(code).not.toMatch(/\buseMutation\b/);
    expect(code).not.toMatch(/from\s+["']\.\.\/api["']/);
    expect(code).not.toMatch(/\bapiRequest\b/);
    expect(code).not.toMatch(/\bfetch\s*\(/);
    expect(code).not.toMatch(/\baxios\b/);
  });

  it("does NOT expose backend-authoritative transition matrix tokens", async () => {
    const fs = await import("node:fs");
    const path = await import("node:path");
    const here = path.resolve(__dirname, "..", "OrderActionsBar.tsx");
    const source = fs.readFileSync(here, "utf-8");

    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .replace(/(^|[^:\\])\/\/[^\n]*/g, "$1");

    expect(code).not.toMatch(/_ALLOWED_TRANSITIONS\s*=/);
    expect(code).not.toMatch(/transitionMatrix\s*=/);
    expect(code).not.toMatch(/canTransitionTo\s*\(/);
    expect(code).not.toMatch(/isTransitionValid\s*\(/);
    expect(code).not.toMatch(/\bassertCan\b/);
  });
});
