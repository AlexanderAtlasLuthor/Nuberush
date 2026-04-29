"""Pydantic v2 schemas for inventory items, logs and movement requests.

Mirrors the rules in `app.domain.inventory_rules` (FROZEN for S4) and
the model layer from S1. Each movement type has its own request
schema so callers cannot send invalid payloads for a given operation
(empty reason on an adjustment, negative quantity on a sale, etc.).

Conventions:

- Read schemas use ConfigDict(from_attributes=True) so they hydrate
  directly from SQLAlchemy rows.
- Create/Update schemas never include `id`, `store_id` (taken from
  the URL path), `last_counted_at`, or any timestamps.
- Quantities are integers. Deltas may be negative only for
  `AdjustStockRequest`; every other movement carries a positive
  `quantity` and the service layer applies the sign.
- `reason` is mandatory and non-empty for `adjust`, `damage` and
  `return`; optional (but trimmed if provided) for `receive`,
  `sale`, `reserve` and `release`.
- The polymorphic reference fields (`reference_type` +
  `reference_id`) must come paired or both NULL, mirroring the DB
  CHECK on `inventory_logs`.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator
from pydantic import model_validator

from app.db.models import ComplianceStatus
from app.db.models import InventoryMovementType
from app.db.models import InventoryStatus


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #


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


def _enforce_reference_pair(
    reference_type: str | None, reference_id: UUID | None
) -> None:
    type_set = reference_type is not None
    id_set = reference_id is not None
    if type_set != id_set:
        raise ValueError(
            "reference_type and reference_id must be both set or both null"
        )


# --------------------------------------------------------------------- #
# Inventory item
# --------------------------------------------------------------------- #


class InventoryItemCreate(BaseModel):
    """Body for POST /stores/{store_id}/inventory/items.

    `store_id` comes from the URL path, never the body. The service
    layer enforces UNIQUE(store_id, variant_id) and surfaces a 409 on
    duplicates.
    """

    variant_id: UUID
    quantity_on_hand: int = Field(default=0, ge=0)
    quantity_reserved: int = Field(default=0, ge=0)
    reorder_threshold: int = Field(default=0, ge=0)
    status: InventoryStatus = InventoryStatus.available

    @model_validator(mode="after")
    def _check_reserved_lte_on_hand(self) -> "InventoryItemCreate":
        if self.quantity_reserved > self.quantity_on_hand:
            raise ValueError(
                "quantity_reserved cannot exceed quantity_on_hand"
            )
        return self


class InventoryItemUpdate(BaseModel):
    """Partial update for an inventory item.

    Quantities are NEVER mutated through this schema; they only
    change via the dedicated movement endpoints (receive, adjust,
    sale, etc.). Only the operational threshold and status are
    editable here.
    """

    reorder_threshold: int | None = Field(default=None, ge=0)
    status: InventoryStatus | None = None


class InventoryProductSummary(BaseModel):
    """Curated subset of `Product` surfaced inside an inventory response.

    Only fields the inventory UI needs to render rows and pre-warn the
    user about sellability. Description, hold_reason, jurisdiction,
    last_compliance_check and timestamps are deliberately excluded —
    those belong to a product-detail page.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    brand: str | None
    category: str
    compliance_status: ComplianceStatus
    allowed_for_sale: bool
    is_active: bool


class InventoryVariantSummary(BaseModel):
    """Curated subset of `ProductVariant` surfaced inside an inventory
    response, with the parent product nested.

    Pricing, cost, barcode, unit_count, puff_count and thc_strength
    are deliberately excluded — variant-detail or order-line concerns.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sku: str
    flavor: str | None
    size_label: str | None
    is_active: bool
    product: InventoryProductSummary


class InventoryItemRead(BaseModel):
    """Response shape for any endpoint returning an inventory item.

    The nested `variant` (with `variant.product`) is populated from the
    SQLAlchemy relationships and lets the frontend render labels
    without a follow-up call. The service layer eager-loads both legs
    via `selectinload` to avoid N+1 on list endpoints; see
    `app.services.inventory._inventory_item_load_options`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    store_id: UUID
    variant_id: UUID
    quantity_on_hand: int
    quantity_reserved: int
    reorder_threshold: int
    status: InventoryStatus
    last_counted_at: datetime | None
    created_at: datetime
    updated_at: datetime
    variant: InventoryVariantSummary


class InventoryItemListResponse(BaseModel):
    """Paginated response for GET /stores/{store_id}/inventory."""

    items: list[InventoryItemRead]
    total: int
    limit: int
    offset: int


# --------------------------------------------------------------------- #
# Inventory log
# --------------------------------------------------------------------- #


class InventoryLogRead(BaseModel):
    """Response shape for an inventory log entry. Append-only by
    convention; there is no Create/Update counterpart."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    inventory_item_id: UUID
    store_id: UUID
    variant_id: UUID
    performed_by_user_id: UUID | None
    movement_type: InventoryMovementType
    quantity_delta: int
    quantity_after: int
    reason: str | None
    reference_type: str | None
    reference_id: UUID | None
    created_at: datetime


# --------------------------------------------------------------------- #
# Movement requests
# --------------------------------------------------------------------- #
# Each movement carries its own validation profile. The service layer
# turns these requests into atomic mutations + log writes. Path
# parameters (item_id, store_id) are not in the body.


class _MovementBase(BaseModel):
    """Shared optional polymorphic reference fields."""

    reference_type: str | None = Field(default=None, max_length=50)
    reference_id: UUID | None = None

    @field_validator("reference_type")
    @classmethod
    def _strip_reference_type(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @model_validator(mode="after")
    def _check_reference_pair(self):
        _enforce_reference_pair(self.reference_type, self.reference_id)
        return self


class ReceiveStockRequest(_MovementBase):
    quantity: int = Field(gt=0)
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class AdjustStockRequest(_MovementBase):
    """Signed adjustment. Positive `delta` adds, negative removes;
    zero is rejected because adjustments must change something."""

    delta: int
    reason: str = Field(min_length=1)

    @field_validator("delta")
    @classmethod
    def _delta_non_zero(cls, value: int) -> int:
        if value == 0:
            raise ValueError("delta must not be zero")
        return value

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        return _strip_required(value)


class DamageStockRequest(_MovementBase):
    """Records units lost (broken / expired / spilled). The service
    layer applies the negative sign when reducing stock."""

    quantity: int = Field(gt=0)
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        return _strip_required(value)


class SaleStockRequest(_MovementBase):
    quantity: int = Field(gt=0)
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class ReserveStockRequest(_MovementBase):
    quantity: int = Field(gt=0)
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class ReleaseReservationRequest(_MovementBase):
    quantity: int = Field(gt=0)
    reason: str | None = None

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class ReturnStockRequest(_MovementBase):
    """Customer return. Reason is mandatory because the audit trail
    must explain why stock came back (warranty, change of mind,
    defective unit, etc.)."""

    quantity: int = Field(gt=0)
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        return _strip_required(value)
