// F2.26.4.C: human-readable display labels for the order status enum.
//
// Presentation only. Turns the raw snake_case `OrderStatus` tokens the
// backend sends into operator-facing copy for Store surfaces (lists,
// detail, action bar, audit trail). The underlying wire values are NEVER
// altered — filters and status transitions keep sending/receiving the raw
// tokens. Unknown values fall back to the raw token so a future backend
// addition renders verbatim rather than blank.

import type { OrderStatus } from "./types";

const ORDER_STATUS_LABEL: Record<OrderStatus, string> = {
  pending: "Pending",
  accepted: "Accepted",
  preparing: "Preparing",
  ready: "Ready",
  out_for_delivery: "Out for delivery",
  delivered: "Delivered",
  canceled: "Canceled",
  returned: "Returned",
};

export function orderStatusLabel(status: OrderStatus | null | undefined): string {
  if (status === null || status === undefined) return status ?? "";
  return ORDER_STATUS_LABEL[status] ?? status;
}
