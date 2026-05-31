"""Pydantic v2 schemas for the store-applications domain (F2.24.C1).

This module freezes the base wire contract for professional store
sign-up / merchant onboarding. It is the data-layer foundation only:

- `StoreApplicationStatus` is re-exported from `app.db.models` so the
  schema layer and the ORM share a single enum definition (the same
  pattern `app.schemas.products` uses for `ProductApprovalStatus`).

- `StoreApplicationBase` holds the applicant-provided intake fields with
  no normalization, so it can both seed the internal create model and be
  inherited by the read model without mutating stored values.

- `StoreApplicationCreateInternal` is the server-side construction model
  the intake service (C2) will build from a validated public request. It
  is the home of the owner-email normalization (lowercase + trim) the
  F2.24 plan defers to the service layer — NOT a public request schema.
  The public submit request (with `extra="forbid"`) deliberately lands in
  C2, not here.

- `StoreApplicationRead` / `StoreApplicationListItem` are read-only
  projections. Following the repo convention (see `app.schemas.audit`,
  `StoreRead`, `UserRead`) read schemas do NOT set `extra="forbid"`:
  unknown ORM attributes are silently dropped during `from_attributes`
  hydration.

- `StoreApplicationAuditLogRead` mirrors one append-only audit row.

No submit / approve / reject behavior lives here — this subphase ships
inert data structures only.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import EmailStr
from pydantic import Field
from pydantic import field_validator

from app.db.models import StoreApplicationStatus


# Re-exported so callers can `from app.schemas.store_applications import
# StoreApplicationStatus` without reaching into the ORM module.
__all__ = [
    "StoreApplicationStatus",
    "StoreApplicationBase",
    "StoreApplicationCreateInternal",
    "StoreApplicationSubmitRequest",
    "StoreApplicationSubmitResponse",
    "StoreApplicationRead",
    "StoreApplicationListItem",
    "StoreApplicationListResponse",
    "StoreApplicationDetailResponse",
    "StoreApplicationRejectRequest",
    "StoreApplicationReviewResponse",
    "StoreApplicationAuditLogRead",
]


class StoreApplicationBase(BaseModel):
    """Applicant-provided intake fields, shared by create + read.

    No trimming or normalization here on purpose: this base hydrates the
    read model straight from ORM rows, so it must not rewrite stored
    values. Normalization is applied in `StoreApplicationCreateInternal`.
    Field lengths mirror the DB VARCHAR limits so an out-of-bounds value
    surfaces as a clean 422 rather than an IntegrityError downstream.
    """

    model_config = ConfigDict(from_attributes=True)

    business_name: str = Field(min_length=1, max_length=200)
    business_type: str = Field(min_length=1, max_length=100)
    owner_full_name: str = Field(min_length=1, max_length=150)
    owner_email: EmailStr
    owner_phone: str = Field(min_length=1, max_length=30)
    business_phone: str | None = Field(default=None, max_length=30)
    address_line_1: str = Field(min_length=1, max_length=200)
    address_line_2: str | None = Field(default=None, max_length=200)
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=1, max_length=120)
    postal_code: str = Field(min_length=1, max_length=20)
    country: str = Field(default="US", min_length=2, max_length=2)
    location_count: int = Field(default=1, ge=1)
    estimated_weekly_orders: int | None = Field(default=None, ge=0)
    hours_of_operation: str | None = None
    website_url: str | None = Field(default=None, max_length=255)
    social_url: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    terms_accepted: bool = False


class StoreApplicationCreateInternal(StoreApplicationBase):
    """Internal create model the intake service builds (C2 consumer).

    Adds the service-layer normalization the F2.24 plan defers:
    `owner_email` is lowercased and trimmed so the unique/index lookups in
    C2 are stable. Required string fields are trimmed and re-checked
    non-empty so a whitespace-only value cannot slip past the DB CHECKs.
    Constructed in code from an already-validated request, so it carries
    no `extra="forbid"` — that guard belongs to the public request schema
    in C2.
    """

    @field_validator("owner_email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator(
        "business_name",
        "business_type",
        "owner_full_name",
        "owner_phone",
        "address_line_1",
        "city",
        "state",
        "postal_code",
    )
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("country")
    @classmethod
    def _normalize_country(cls, value: str) -> str:
        return value.strip().upper()


class StoreApplicationSubmitRequest(BaseModel):
    """Public, unauthenticated submit payload for POST /public/store-applications
    (F2.24.C2).

    Strict mass-assignment protection: `extra="forbid"` rejects ANY field
    outside the applicant-provided set — including every server-owned
    column (`id`, `status`, `submitted_at`, `reviewed_*`,
    `rejection_reason`, `provisioned_*`, `public_lookup_token`, timestamps)
    and every privilege field an attacker might try to smuggle in
    (`role`, `store_id`, `user_id`, `auth_user_id`, `is_admin`). A rejected
    extra surfaces as a clean 422; the route never reads such a value.

    Normalization mirrors `StoreApplicationCreateInternal`: `owner_email`
    is lowercased + trimmed, `country` uppercased, and required string
    fields are trimmed and re-checked non-empty so a whitespace-only value
    can never reach the DB CHECK constraints. `terms_accepted` MUST be
    true — a submission that has not accepted the terms is a 422, never a
    stored row.

    Field lengths mirror the DB VARCHAR limits so an out-of-bounds value is
    a 422 rather than an IntegrityError.
    """

    model_config = ConfigDict(extra="forbid")

    # Required intake fields.
    business_name: str = Field(min_length=1, max_length=200)
    business_type: str = Field(min_length=1, max_length=100)
    owner_full_name: str = Field(min_length=1, max_length=150)
    owner_email: EmailStr
    owner_phone: str = Field(min_length=1, max_length=30)
    business_phone: str = Field(min_length=1, max_length=30)
    address_line_1: str = Field(min_length=1, max_length=200)
    city: str = Field(min_length=1, max_length=120)
    state: str = Field(min_length=1, max_length=120)
    postal_code: str = Field(min_length=1, max_length=20)
    country: str = Field(min_length=2, max_length=2)
    location_count: int = Field(ge=1)
    estimated_weekly_orders: int = Field(ge=0)
    hours_of_operation: str = Field(min_length=1)
    terms_accepted: bool

    # Optional intake fields.
    address_line_2: str | None = Field(default=None, max_length=200)
    website_url: str | None = Field(default=None, max_length=255)
    social_url: str | None = Field(default=None, max_length=255)
    notes: str | None = None

    @field_validator("owner_email")
    @classmethod
    def _normalize_email(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("country")
    @classmethod
    def _normalize_country(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator(
        "business_name",
        "business_type",
        "owner_full_name",
        "owner_phone",
        "business_phone",
        "address_line_1",
        "city",
        "state",
        "postal_code",
        "hours_of_operation",
    )
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped

    @field_validator("address_line_2", "website_url", "social_url", "notes")
    @classmethod
    def _strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("terms_accepted")
    @classmethod
    def _require_terms_accepted(cls, value: bool) -> bool:
        if value is not True:
            raise ValueError("Terms must be accepted to submit an application.")
        return value


class StoreApplicationSubmitResponse(BaseModel):
    """Minimal, non-leaking response for a public submission.

    Returns only what the applicant needs to know — the new application's
    id, its review status, and a human message. Server-owned fields
    (provisioning links, the lookup token, reviewer info) are deliberately
    NOT exposed here; the public status-lookup surface is a separate
    subphase.
    """

    id: UUID
    status: StoreApplicationStatus
    message: str


class StoreApplicationRead(StoreApplicationBase):
    """Full application row, including lifecycle + provisioning fields.

    Inherits every intake field from the base and adds the server-owned
    columns. Hydrates from an ORM `StoreApplication` via
    `from_attributes`.
    """

    id: UUID
    status: StoreApplicationStatus
    terms_accepted_at: datetime | None
    submitted_at: datetime | None
    reviewed_at: datetime | None
    reviewed_by_user_id: UUID | None
    rejection_reason: str | None
    provisioned_store_id: UUID | None
    provisioned_owner_user_id: UUID | None
    public_lookup_token: str
    created_at: datetime
    updated_at: datetime


class StoreApplicationListItem(BaseModel):
    """Condensed row for the admin application queue (C3 consumer).

    Carries only the columns a review list renders, so the list endpoint
    never over-fetches the full intake payload.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_name: str
    business_type: str
    owner_full_name: str
    owner_email: EmailStr
    status: StoreApplicationStatus
    location_count: int
    estimated_weekly_orders: int | None
    city: str
    state: str
    submitted_at: datetime | None
    reviewed_at: datetime | None
    created_at: datetime


class StoreApplicationListResponse(BaseModel):
    """Paginated envelope for the admin application list.

    Mirrors `StoreListResponse` / `AuditEventListResponse`: `items`
    carries the page rows, `total` is the pre-pagination count.
    """

    items: list[StoreApplicationListItem]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class StoreApplicationAuditLogRead(BaseModel):
    """Read projection of one append-only store-application audit row."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    application_id: UUID
    event_type: str
    actor_user_id: UUID | None
    message: str | None
    payload: dict[str, Any] | None
    created_at: datetime


class StoreApplicationDetailResponse(StoreApplicationRead):
    """Admin detail view (F2.24.C3): the full application plus its audit
    trail.

    Inherits every field of `StoreApplicationRead` and appends the
    append-only audit events so the admin review screen can render the
    history (created / rejected / …) without a second request. Hydrates
    from the ORM `StoreApplication` via `from_attributes`, reading the
    `audit_logs` relationship.
    """

    audit_logs: list[StoreApplicationAuditLogRead] = Field(
        default_factory=list
    )


class StoreApplicationRejectRequest(BaseModel):
    """Admin reject payload (F2.24.C3).

    `extra="forbid"` blocks any attempt to smuggle a status / reviewer /
    provisioning field through the reject body — the only thing an admin
    supplies is the reason. The reason is trimmed and required non-empty so
    the DB `ck_store_applications_rejected_iff_reason` constraint is always
    satisfied with a meaningful value.
    """

    model_config = ConfigDict(extra="forbid")

    rejection_reason: str = Field(min_length=1, max_length=2000)

    @field_validator("rejection_reason")
    @classmethod
    def _strip_required(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty")
        return stripped


class StoreApplicationReviewResponse(BaseModel):
    """Response for an admin review action (approve / reject).

    Minimal, non-leaking: the outcome status, the reviewer + timestamp,
    the provisioning links (populated on approve, null on reject), the
    rejection reason when present, and a human message. No secrets, no
    Supabase data, no public lookup token.
    """

    id: UUID
    status: StoreApplicationStatus
    reviewed_by_user_id: UUID | None
    reviewed_at: datetime | None
    provisioned_store_id: UUID | None = None
    provisioned_owner_user_id: UUID | None = None
    rejection_reason: str | None
    message: str
