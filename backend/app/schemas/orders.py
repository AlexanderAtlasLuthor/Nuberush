"""Pydantic v2 schemas for orders, order items and order audit logs.

These schemas are the API contract for the orders module. They enforce
the trust boundary frozen in `app.domain.orders_rules` (§2): the
frontend MUST NOT send monetary fields, snapshots or the inventory
binding. Every input model uses ``extra="forbid"`` so unexpected keys
return a 422 instead of being silently ignored.

Design rules baked into this file:

- Create / update / action schemas reject monetary fields
  (``subtotal_amount``, ``tax_amount``, ``total_amount``, ``unit_price``,
  ``line_total``) and the inventory binding (``inventory_item_id``).
  Those values are computed or resolved server-side (orders_rules §2,
  §5).
- ``OrderCreate.idempotency_key`` is mandatory (orders_rules §4); a
  request without it is a 422.
- Read schemas use ``ConfigDict(from_attributes=True)`` so they hydrate
  directly from SQLAlchemy rows.
- All money is ``Decimal`` with NUMERIC(10, 2) limits to mirror the DB
  (orders_rules §5).
- Status transitions, cancellation and return are separate schemas so
  the API surface can wire each to the right RBAC alias and the right
  inventory effect (orders_rules §3, §6).
"""

from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from app.db.models import OrderStatus
from app.schemas.driver import DriverDeliveryReturnRead
from app.schemas.inventory import InventoryVariantSummary


# --------------------------------------------------------------------- #
# Reusable types and helpers
# --------------------------------------------------------------------- #


Money = Annotated[
    Decimal,
    Field(ge=0, max_digits=10, decimal_places=2),
]


def _strip_required(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty")
    return stripped


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty when provided")
    return stripped


# --------------------------------------------------------------------- #
# Order items — input
# --------------------------------------------------------------------- #


class OrderItemCreate(BaseModel):
    """Body element of ``OrderCreate.items``.

    The frontend supplies the variant and the quantity. The service
    layer resolves the inventory_item from ``(store_id, variant_id)``
    and snapshots ``unit_price`` from ``ProductVariant.price`` at
    creation time (orders_rules §2, §5). Any client-provided
    ``unit_price``, ``line_total`` or ``inventory_item_id`` is a
    422 thanks to ``extra="forbid"``.
    """

    model_config = ConfigDict(extra="forbid")

    variant_id: UUID
    quantity: int = Field(gt=0)


class OrderCreate(BaseModel):
    """Body for ``POST /stores/{store_id}/orders``.

    ``store_id`` is taken from the URL path and ``customer_user_id``
    is set server-side from the authenticated principal (or left null
    for walk-in customers, per orders_rules out-of-scope). Totals,
    status, idempotency lifecycle and audit log are all server-managed.

    The schema enforces:

    - At least one line item.
    - No duplicate ``variant_id`` across items: the unique constraint
      on ``order_items(order_id, variant_id)`` (S1) makes a duplicate
      a hard DB error; rejecting it here gives a clean 422 instead.
    - Every monetary field, ``inventory_item_id``, ``id``, ``status``,
      ``store_id``, ``customer_user_id`` and timestamps are forbidden
      via ``extra="forbid"``.
    """

    model_config = ConfigDict(extra="forbid")

    idempotency_key: str = Field(min_length=1, max_length=128)
    items: list[OrderItemCreate] = Field(min_length=1)
    notes: str | None = None

    @field_validator("idempotency_key")
    @classmethod
    def _strip_idempotency_key(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("notes")
    @classmethod
    def _strip_notes(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @model_validator(mode="after")
    def _check_unique_variant_ids(self) -> "OrderCreate":
        seen: set[UUID] = set()
        for item in self.items:
            if item.variant_id in seen:
                raise ValueError(
                    "items must not contain duplicate variant_id; "
                    "merge quantities into a single line"
                )
            seen.add(item.variant_id)
        return self


# --------------------------------------------------------------------- #
# Order items — output
# --------------------------------------------------------------------- #


class OrderItemRead(BaseModel):
    """Response shape for an order item.

    ``unit_price`` and ``line_total`` are server-side snapshots; the
    client receives them but never sends them (orders_rules §2). The
    ``inventory_item_id`` is the binding the orders service resolved
    from ``(store_id, variant_id)``.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    variant_id: UUID
    inventory_item_id: UUID
    quantity: int
    unit_price: Decimal
    line_total: Decimal
    created_at: datetime
    updated_at: datetime
    variant: InventoryVariantSummary


class OrderRead(BaseModel):
    """Response shape for any endpoint returning an order.

    Includes nested line items and the full lifecycle timestamps so a
    single GET call yields the complete order picture without an
    extra round-trip.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    customer_user_id: UUID | None
    idempotency_key: str
    status: OrderStatus
    subtotal_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    age_verified_at: datetime | None
    age_verified_by_user_id: UUID | None
    accepted_at: datetime | None
    canceled_at: datetime | None
    delivered_at: datetime | None
    returned_at: datetime | None
    cancel_reason: str | None
    notes: str | None
    created_at: datetime
    updated_at: datetime
    items: list[OrderItemRead]


# --------------------------------------------------------------------- #
# Aggregate responses
# --------------------------------------------------------------------- #


class OrderListResponse(BaseModel):
    """Paginated response for GET /stores/{store_id}/orders."""

    items: list[OrderRead]
    total: int
    limit: int
    offset: int


# --------------------------------------------------------------------- #
# Lifecycle action schemas
# --------------------------------------------------------------------- #


class OrderStatusUpdate(BaseModel):
    """Body for the generic status-transition endpoint.

    Used by the forward transitions that do NOT touch inventory
    (``pending → accepted → preparing → ready → out_for_delivery``)
    and the ``out_for_delivery → delivered`` transition that consumes
    reservations (orders_rules §3). Cancellation and return have
    their own schemas because they carry mandatory reasons.
    """

    model_config = ConfigDict(extra="forbid")

    new_status: OrderStatus
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class OrderCancelRequest(BaseModel):
    """Body for ``POST /orders/{id}/cancel``.

    Cancellation is manager-or-above (orders_rules §6) and releases
    the reservation without touching ``quantity_on_hand``. The reason
    is mandatory because cancellation undoes operational decisions
    and the audit trail must explain why.
    """

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        return _strip_required(value)


class OrderReturnRequest(BaseModel):
    """Body for ``POST /orders/{id}/return``.

    Returns are manager-or-above (orders_rules §6) and replenish
    inventory by raising ``quantity_on_hand``. The reason is
    mandatory because every return movement on inventory_logs
    requires one (S4).
    """

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        return _strip_required(value)


# --------------------------------------------------------------------- #
# Audit log
# --------------------------------------------------------------------- #


class OrderAuditLogRead(BaseModel):
    """Response shape for an order audit log entry.

    Audit rows are append-only by convention and are produced by the
    service layer on every state transition. Clients only ever read
    them (orders_rules §8).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    store_id: UUID
    performed_by_user_id: UUID | None
    previous_status: OrderStatus | None
    new_status: OrderStatus
    action: str
    reason: str | None
    created_at: datetime


# --------------------------------------------------------------------- #
# Store return confirmation (Dr.1.2.H)
# --------------------------------------------------------------------- #
#
# POST /orders/{order_id}/confirm-driver-return lets an authorized store actor
# (manager-or-above) confirm physical receipt of a failed-delivery return after
# the driver has reached returned_to_store / returned_pending_confirmation. The
# confirmation stamps the DriverDeliveryReturn as confirmed and cancels the
# order (releasing the held reservation without touching quantity_on_hand) via
# orders authority. The request carries ONLY a confirmation flag and a safe note
# — never customer PII, ID/proof/photo/signature/OCR/barcode, or location.


class StoreConfirmDriverReturnRequest(BaseModel):
    """Body for ``POST /orders/{id}/confirm-driver-return``.

    ``received_confirmed`` is required and must be ``True`` — it is the store
    actor's explicit assertion that the returned product was physically
    received. ``note`` is an optional safe note capped at 500 chars. No
    sensitive field is accepted.
    """

    model_config = ConfigDict(extra="forbid")

    received_confirmed: bool
    note: str | None = Field(default=None, max_length=500)

    @model_validator(mode="after")
    def _require_received_confirmed(
        self,
    ) -> "StoreConfirmDriverReturnRequest":
        if not self.received_confirmed:
            raise ValueError("received_confirmed must be true")
        return self


class StoreConfirmDriverReturnResponse(BaseModel):
    """Composite response for the store return confirmation (Dr.1.2.H).

    Surfaces both the now-canceled order and the confirmed return custody
    record so the store sees the full commercial + custody outcome in one call.
    """

    order: OrderRead
    driver_return: DriverDeliveryReturnRead
