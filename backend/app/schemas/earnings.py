"""Pydantic v2 schemas for the earnings surfaces.

Two wire contracts:

  GET /admin/earnings              -> AdminEarningsSummary
  GET /stores/{store_id}/earnings  -> StoreEarningsSummary

Both are read-only, computed on request from `orders` + `order_items`
filtered to `status = delivered`. No persistence layer backs these
shapes — see `app.services.earnings` for the computation.

Pricing model encoded in the admin response (per product spec):

  customer_paid_total = subtotal + delivery + tip + taxes + commission
  commission          = 0.20 * (subtotal + delivery + tip + taxes)
  gross_base_total    = subtotal + delivery + tip + taxes

Delivery is currently a flat $10 per delivered order; tip is $0 since
neither field is tracked on the `Order` row yet. The service exposes
those constants so a future migration can replace them with summed
columns without changing this contract.

The store response intentionally surfaces ONLY what the store earns
from products sold — quantity_sold + product_revenue — and does NOT
expose delivery / tip / tax / commission totals (per user request).
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class AdminEarningsStoreBreakdown(BaseModel):
    """Per-store contribution to platform commission.

    `gross_base` is the sum (subtotal + delivery + tip + taxes) for that
    store's delivered orders; `commission` is `0.20 * gross_base`.
    """

    model_config = ConfigDict(extra="forbid")

    store_id: UUID
    store_name: str
    delivered_orders: int = Field(ge=0)
    gross_base: Decimal
    commission: Decimal


class AdminEarningsSummary(BaseModel):
    """Top-level response for `GET /admin/earnings`.

    All amounts are USD `Decimal` values with two decimal places on the
    wire (serialised as JSON strings to preserve precision). The
    `by_store` list is bounded server-side to the top 10 stores by
    commission descending.
    """

    model_config = ConfigDict(extra="forbid")

    delivered_orders: int = Field(ge=0)
    subtotal_total: Decimal
    delivery_total: Decimal
    tip_total: Decimal
    tax_total: Decimal
    gross_base_total: Decimal
    commission_total: Decimal
    customer_paid_total: Decimal
    commission_rate: Decimal
    delivery_fee: Decimal
    by_store: list[AdminEarningsStoreBreakdown]


class StoreEarningsTopProduct(BaseModel):
    """One row in the store's "top products by revenue" breakdown."""

    model_config = ConfigDict(extra="forbid")

    variant_id: UUID
    product_name: str
    variant_label: str | None
    quantity_sold: int = Field(ge=0)
    revenue: Decimal


class StoreEarningsSummary(BaseModel):
    """Top-level response for `GET /stores/{store_id}/earnings`.

    Earnings as seen by the store: how many products they have sold
    (units) and how much revenue those products generated (sum of
    `OrderItem.line_total` for delivered orders only). The platform
    commission, delivery fee, tips and taxes are intentionally absent
    from this surface — those belong to the admin earnings view.

    `top_products` is bounded server-side to 10 rows, ordered by
    revenue descending.
    """

    model_config = ConfigDict(extra="forbid")

    delivered_orders: int = Field(ge=0)
    total_items_sold: int = Field(ge=0)
    product_revenue: Decimal
    top_products: list[StoreEarningsTopProduct]
