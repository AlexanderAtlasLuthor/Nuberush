"""Pydantic v2 schemas for products, variants and compliance.

These schemas are the API contract for the products module. They
deliberately split input from output and keep compliance changes on a
separate schema so the audit-log invariant from
`app.domain.products_rules` can be enforced at the service layer without
exception.

Design rules baked into this file:

- ProductCreate/ProductUpdate never accept timestamps, ids or
  `last_compliance_check`; those are set by the database/server.
- ProductUpdate intentionally omits compliance fields. Callers must use
  ProductComplianceUpdate so the audit log fires.
- ProductComplianceUpdate enforces banned -> not allowed_for_sale at
  the schema layer. The same invariant is also enforced by a CHECK
  constraint at the DB layer (see migration 5c3f52060b2f).
- All money is `Decimal` with NUMERIC(10, 2) limits to mirror the DB.
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

from app.db.models import ComplianceStatus
from app.db.models import ProductApprovalStatus


# --------------------------------------------------------------------- #
# Reusable money types
# --------------------------------------------------------------------- #
# The DB uses NUMERIC(10, 2). We mirror that so a request with too many
# decimal places or an out-of-range value is rejected at the API layer
# with a clean 422 instead of bubbling up as an IntegrityError later.

Money = Annotated[
    Decimal,
    Field(ge=0, max_digits=10, decimal_places=2),
]
OptionalMoney = Annotated[
    Decimal | None,
    Field(default=None, ge=0, max_digits=10, decimal_places=2),
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


def _enforce_banned_invariant(
    compliance_status: ComplianceStatus, allowed_for_sale: bool
) -> None:
    if (
        compliance_status == ComplianceStatus.banned
        and allowed_for_sale is True
    ):
        raise ValueError("A banned product cannot be allowed_for_sale.")


# --------------------------------------------------------------------- #
# Product schemas
# --------------------------------------------------------------------- #


class ProductCreate(BaseModel):
    """Payload accepted by POST /products."""

    name: str = Field(min_length=1, max_length=200)
    brand: str | None = Field(default=None, max_length=120)
    category: str = Field(min_length=1, max_length=100)
    description: str | None = None
    jurisdiction: str = Field(default="FL", min_length=1, max_length=50)
    compliance_status: ComplianceStatus = ComplianceStatus.allowed
    allowed_for_sale: bool = True

    @field_validator("name", "category", "jurisdiction")
    @classmethod
    def _strip_text_fields(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("brand", "description")
    @classmethod
    def _strip_optional_text_fields(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @model_validator(mode="after")
    def _check_banned_invariant(self) -> "ProductCreate":
        _enforce_banned_invariant(
            self.compliance_status, self.allowed_for_sale
        )
        return self


class ProductUpdate(BaseModel):
    """Partial update for non-compliance product fields.

    Compliance fields (compliance_status, allowed_for_sale, hold_reason)
    are intentionally absent. Use ProductComplianceUpdate for those so
    the audit log is written.
    """

    name: str | None = Field(default=None, min_length=1, max_length=200)
    brand: str | None = Field(default=None, max_length=120)
    category: str | None = Field(
        default=None, min_length=1, max_length=100
    )
    description: str | None = None
    jurisdiction: str | None = Field(
        default=None, min_length=1, max_length=50
    )
    is_active: bool | None = None

    @field_validator("name", "category", "jurisdiction")
    @classmethod
    def _strip_required_when_present(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator("brand", "description")
    @classmethod
    def _strip_optional_text_fields(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class ProductComplianceUpdate(BaseModel):
    """Payload accepted by PATCH /products/{id}/compliance.

    Every successful call must produce one row in
    product_compliance_audit_logs. The service layer is responsible
    for that write; this schema only validates the inputs.
    """

    compliance_status: ComplianceStatus
    allowed_for_sale: bool
    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        return _strip_required(value)

    @model_validator(mode="after")
    def _check_banned_invariant(self) -> "ProductComplianceUpdate":
        _enforce_banned_invariant(
            self.compliance_status, self.allowed_for_sale
        )
        return self


class ProductRead(BaseModel):
    """Response shape for any endpoint returning a product.

    Approval fields surface the proposal/review workflow alongside the
    existing compliance fields. The two gates are independent:
    `approval_status` tracks whether the catalog row is curated;
    `compliance_status` tracks regulatory state. A product must be
    approved AND compliant AND active AND allowed_for_sale to sell.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    brand: str | None
    category: str
    description: str | None
    compliance_status: ComplianceStatus
    allowed_for_sale: bool
    is_active: bool
    hold_reason: str | None
    jurisdiction: str
    last_compliance_check: datetime | None
    approval_status: ProductApprovalStatus
    proposed_by_store_id: UUID | None
    proposed_by_user_id: UUID | None
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    rejection_reason: str | None
    created_at: datetime
    updated_at: datetime


class ProductReject(BaseModel):
    """Payload accepted by POST /products/{id}/reject.

    `reason` is required and stored verbatim on the product so the
    proposing store can see why their submission was declined.
    """

    reason: str = Field(min_length=1)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        return _strip_required(value)


# --------------------------------------------------------------------- #
# Variant schemas
# --------------------------------------------------------------------- #


class VariantCreate(BaseModel):
    """Payload accepted by POST /products/{id}/variants."""

    product_id: UUID
    sku: str = Field(min_length=1, max_length=100)
    barcode: str | None = Field(default=None, max_length=100)
    flavor: str | None = Field(default=None, max_length=100)
    size_label: str | None = Field(default=None, max_length=50)
    unit_count: int | None = Field(default=None, gt=0)
    puff_count: int | None = Field(default=None, gt=0)
    thc_strength: str | None = Field(default=None, max_length=50)
    price: Money
    cost: OptionalMoney = None
    is_active: bool = True

    @field_validator("sku")
    @classmethod
    def _strip_sku(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator(
        "barcode", "flavor", "size_label", "thc_strength"
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class VariantUpdate(BaseModel):
    """Partial update for variant fields. product_id is immutable."""

    sku: str | None = Field(default=None, min_length=1, max_length=100)
    barcode: str | None = Field(default=None, max_length=100)
    flavor: str | None = Field(default=None, max_length=100)
    size_label: str | None = Field(default=None, max_length=50)
    unit_count: int | None = Field(default=None, gt=0)
    puff_count: int | None = Field(default=None, gt=0)
    thc_strength: str | None = Field(default=None, max_length=50)
    price: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )
    cost: Decimal | None = Field(
        default=None, ge=0, max_digits=10, decimal_places=2
    )
    is_active: bool | None = None

    @field_validator("sku")
    @classmethod
    def _strip_sku(cls, value: str | None) -> str | None:
        return _strip_optional(value)

    @field_validator(
        "barcode", "flavor", "size_label", "thc_strength"
    )
    @classmethod
    def _strip_optional_text(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class VariantRead(BaseModel):
    """Response shape for any endpoint returning a variant."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    sku: str
    barcode: str | None
    flavor: str | None
    size_label: str | None
    unit_count: int | None
    puff_count: int | None
    thc_strength: str | None
    price: Decimal
    cost: Decimal | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------- #
# Audit log schema
# --------------------------------------------------------------------- #


class ProductComplianceAuditLogRead(BaseModel):
    """Response shape for an audit log entry.

    Audit rows are append-only by convention and are produced by the
    service layer when compliance changes. Clients only ever read them.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_id: UUID
    previous_compliance_status: ComplianceStatus
    new_compliance_status: ComplianceStatus
    previous_allowed_for_sale: bool
    new_allowed_for_sale: bool
    reason: str
    changed_by_user_id: UUID | None
    created_at: datetime
