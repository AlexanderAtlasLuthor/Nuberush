// F2.7.4 (subfases 1-4): order action bar.
//
// Forward transitions open TransitionStatusDialog (subfase 2).
// Cancel opens CancelOrderModal (subfase 3).
// Return opens ReturnOrderModal (subfase 4).
// Three independent state flags, three independent mutation hooks.
//
// Affordance map vs. business logic:
//   The three constants below decide WHICH buttons to render — they
//   are NOT business logic. Backend remains the authority on whether
//   a transition is permitted (orders_rules §3, FROZEN for S5). If
//   the backend matrix drifts ahead of this file, the worst outcome
//   is a 422 with a clear backend message; we never replicate the
//   validation here. Same precedent already established by
//   `ORDER_STATUSES` in OrdersPage.tsx (filter dropdown).
//
// Hard rules in force:
//   - No mutation hooks, no useMutation, no API calls.
//   - No fetch, no Zustand, no permissions check.
//   - No state machine logic beyond the affordance map.

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

import { CancelOrderModal } from "./CancelOrderModal";
import { ReturnOrderModal } from "./ReturnOrderModal";
import { TransitionStatusDialog } from "./TransitionStatusDialog";
import type { OrderRead, OrderStatus } from "../types";

// --------------------------------------------------------------------- //
// Affordance map (UI-only — backend is the authority)
// --------------------------------------------------------------------- //

/**
 * Forward transitions accepted by `PATCH /orders/{id}/status`.
 *
 * Mirrors backend `_ALLOWED_TRANSITIONS` (services/orders.py) FILTERED
 * to exclude `canceled` and `returned` — those go via dedicated
 * `POST /cancel` and `POST /return` endpoints (orders_rules §6).
 *
 * Source of truth: backend/app/domain/orders_rules.py §3 (FROZEN S5).
 */
const NEXT_FORWARD_TRANSITIONS: Record<
  OrderStatus,
  readonly OrderStatus[]
> = {
  pending: ["accepted"],
  accepted: ["preparing"],
  preparing: ["ready"],
  ready: ["out_for_delivery", "delivered"],
  out_for_delivery: ["delivered"],
  delivered: [],
  canceled: [],
  returned: [],
};

/**
 * Statuses from which `POST /orders/{id}/cancel` is accepted. Mirrors
 * `_CANCELABLE_STATUSES` in services/orders.py.
 */
const CANCELABLE_STATUSES: ReadonlySet<OrderStatus> = new Set([
  "pending",
  "accepted",
  "preparing",
  "ready",
  "out_for_delivery",
]);

/**
 * Statuses from which `POST /orders/{id}/return` is accepted. Returns
 * only happen after delivery (orders_rules §3 — `delivered → returned`).
 */
const RETURNABLE_STATUSES: ReadonlySet<OrderStatus> = new Set<OrderStatus>([
  "delivered",
]);

/**
 * Display label for a forward-transition button. Cosmetic only —
 * never branched on. Falls back to the raw status if an unexpected
 * target slips through (drift defense).
 */
function forwardButtonLabel(target: OrderStatus): string {
  switch (target) {
    case "accepted":
      return "Accept order";
    case "preparing":
      return "Mark as preparing";
    case "ready":
      return "Mark as ready";
    case "out_for_delivery":
      return "Send out for delivery";
    case "delivered":
      return "Mark as delivered";
    default:
      return target;
  }
}

// --------------------------------------------------------------------- //
// Component
// --------------------------------------------------------------------- //

interface OrderActionsBarProps {
  order: OrderRead;
}

export function OrderActionsBar({ order }: OrderActionsBarProps) {
  const forwardTargets = NEXT_FORWARD_TRANSITIONS[order.status];
  const isCancelable = CANCELABLE_STATUSES.has(order.status);
  const isReturnable = RETURNABLE_STATUSES.has(order.status);

  const hasAnyAction =
    forwardTargets.length > 0 || isCancelable || isReturnable;

  // Forward transitions: subfase 2 wires the AlertDialog. The single
  // `transitionTarget` state doubles as both "is the dialog open" and
  // "which target was selected" — null means closed, an OrderStatus
  // means open with that target.
  const [transitionTarget, setTransitionTarget] =
    useState<OrderStatus | null>(null);
  const [openCancel, setOpenCancel] = useState(false);
  const [openReturn, setOpenReturn] = useState(false);

  const handleForward = (target: OrderStatus) => {
    setTransitionTarget(target);
  };

  const handleCancel = () => {
    setOpenCancel(true);
  };

  const handleReturn = () => {
    setOpenReturn(true);
  };

  return (
    <>
      <Card>
        <CardContent className="flex flex-wrap items-center gap-4 p-4">
        <div className="flex flex-col">
          <span className="text-xs uppercase tracking-wide text-muted-foreground">
            Current status
          </span>
          <span
            className="text-sm font-medium uppercase tracking-wide"
            data-testid="order-actions-current-status"
          >
            {order.status}
          </span>
        </div>

        {hasAnyAction ? (
          <div className="ml-auto flex flex-wrap items-center gap-2">
            {forwardTargets.map((target) => (
              <Button
                key={target}
                variant="default"
                size="sm"
                onClick={() => handleForward(target)}
                data-testid={`order-action-transition-${target}`}
              >
                {forwardButtonLabel(target)}
              </Button>
            ))}

            {isCancelable ? (
              <Button
                variant="destructive"
                size="sm"
                onClick={handleCancel}
                data-testid="order-action-cancel"
              >
                Cancel order
              </Button>
            ) : null}

            {isReturnable ? (
              <Button
                variant="default"
                size="sm"
                onClick={handleReturn}
                data-testid="order-action-return"
              >
                Mark as returned
              </Button>
            ) : null}
          </div>
        ) : (
          <span
            className="ml-auto text-sm text-muted-foreground"
            data-testid="order-actions-terminal"
          >
            No actions available for terminal status.
          </span>
        )}
        </CardContent>
      </Card>

      <TransitionStatusDialog
        open={transitionTarget !== null}
        onOpenChange={(open) => {
          if (!open) setTransitionTarget(null);
        }}
        order={order}
        targetStatus={transitionTarget}
      />

      <CancelOrderModal
        open={openCancel}
        onOpenChange={setOpenCancel}
        order={order}
      />

      <ReturnOrderModal
        open={openReturn}
        onOpenChange={setOpenReturn}
        order={order}
      />
    </>
  );
}
