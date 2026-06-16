"""Pydantic v2 schemas for the driver module (Dr.1.1.C).

`DriverProfileRead` is the canonical response shape for GET /driver/me. It
mirrors the columns of `app.db.models.DriverProfile` and hydrates from ORM
rows via `from_attributes=True`.

It is intentionally minimal and read-only. It exposes ONLY the driver
profile's own fields. It deliberately does NOT surface identity already
served by /auth/me (email, role) or anything out of Dr.1.1.C scope —
documents, vehicles, background checks, payout, earnings, assignments,
orders, customer data, audit logs, compliance internals, admin notes, or
metadata. No Create/Update schema exists in this subphase: the driver app
cannot mutate its own profile, and provisioning is a future backend concern.
"""

import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import model_validator

from app.db.models import DriverDeliveryFailureReason
from app.db.models import DriverDeliveryVerificationFailureReason
from app.db.models import DriverDeliveryVerificationOutcome


class DriverProfileRead(BaseModel):
    """Self-scoped view of a driver's own operational profile."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    store_id: UUID
    status: str
    approval_status: str
    created_at: datetime
    updated_at: datetime
    activated_at: datetime | None
    deactivated_at: datetime | None
    approved_at: datetime | None


# --------------------------------------------------------------------- #
# Eligibility read model (Dr.1.1.D)
# --------------------------------------------------------------------- #
#
# GET /driver/eligibility is a backend-authoritative, read-only computation
# of whether the current driver may go online. It is a SKELETON: it reads the
# user, store, and driver-profile state that already exists and reports
# structured `blockers`. It never mutates anything and never decides an
# actual go-online transition (that is a later subphase).


class DriverEligibilityBlockerCode(str, enum.Enum):
    """Why a driver cannot currently go online."""

    driver_profile_missing = "driver_profile_missing"
    user_inactive = "user_inactive"
    store_missing = "store_missing"
    store_inactive = "store_inactive"
    driver_profile_inactive = "driver_profile_inactive"
    driver_approval_pending = "driver_approval_pending"
    driver_approval_rejected = "driver_approval_rejected"


class DriverEligibilityBlockerSource(str, enum.Enum):
    """Which domain the blocker originates from."""

    user = "user"
    store = "store"
    driver_profile = "driver_profile"


class DriverEligibilityBlockerSeverity(str, enum.Enum):
    """Severity of an eligibility finding.

    Only `blocker` exists in Dr.1.1.D — every finding hard-blocks going
    online. A softer `warning` tier may be added in a later subphase.
    """

    blocker = "blocker"


class DriverEligibilityBlocker(BaseModel):
    """A single reason the driver cannot go online."""

    code: DriverEligibilityBlockerCode
    message: str
    source: DriverEligibilityBlockerSource
    severity: DriverEligibilityBlockerSeverity


class DriverEligibilityRead(BaseModel):
    """Backend-computed go-online eligibility for the current driver."""

    can_go_online: bool
    blockers: list[DriverEligibilityBlocker]
    driver_status: str | None
    driver_approval_status: str | None
    user_active: bool
    store_active: bool | None
    evaluated_at: datetime


# --------------------------------------------------------------------- #
# Assigned-delivery read model (Dr.1.1.F)
# --------------------------------------------------------------------- #
#
# GET /driver/assignments and GET /driver/assignments/{id} are read-only,
# self-scoped views of a driver's own `OrderDriverAssignment` rows. They are
# deliberately NOT `OrderRead`: the driver app must never see customer PII,
# money, line items, addresses, compliance internals, or audit data. These
# schemas surface ONLY the assignment lifecycle plus a deliberately thin
# order/store summary. Dispatch, accept/decline, delivery operational state,
# proof of delivery, and GPS are all later subphases and absent here.


class DriverAssignmentStoreSummary(BaseModel):
    """Minimal store context for a driver-facing assignment view."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    timezone: str


class DriverAssignmentOrderSummary(BaseModel):
    """Thin, PII-free order summary for a driver-facing assignment view.

    Carries only the order's lifecycle status and timestamps. It deliberately
    omits customer identity, notes, money (subtotal/tax/total), items,
    address, idempotency key, cancel reason, and every compliance/audit
    internal.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    created_at: datetime
    updated_at: datetime
    accepted_at: datetime | None
    canceled_at: datetime | None
    delivered_at: datetime | None
    returned_at: datetime | None


class DriverAssignmentRead(BaseModel):
    """Self-scoped view of one of the driver's own order assignments."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_id: UUID
    store_id: UUID
    driver_profile_id: UUID
    status: str
    assigned_at: datetime | None
    accepted_at: datetime | None
    declined_at: datetime | None
    canceled_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    order: DriverAssignmentOrderSummary
    store: DriverAssignmentStoreSummary


class DriverAssignmentListResponse(BaseModel):
    """Paginated envelope for a driver's own assignments."""

    items: list[DriverAssignmentRead]
    total: int
    limit: int
    offset: int


# --------------------------------------------------------------------- #
# Delivery operational state read model (Dr.1.1.G.3)
# --------------------------------------------------------------------- #
#
# Internal / read-safe view of a `DriverDeliveryOperationalState` row — the
# THIRD domain axis (physical driver flow), distinct from OrderStatus and the
# assignment lifecycle. G.3 is FOUNDATION only: this schema exists for service
# returns, but is deliberately NOT yet wired into `DriverAssignmentRead` or any
# endpoint. There is no transition request schema (pickup / proof / fail /
# return / ID-verification) — those belong to future action subphases.


class DriverDeliveryOperationalStateRead(BaseModel):
    """Self-scoped view of an assignment's delivery operational state."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assignment_id: UUID
    order_id: UUID
    driver_profile_id: UUID
    store_id: UUID
    state: str
    state_started_at: datetime
    last_transition_at: datetime
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------- #
# Delivery-time 21+ / age verification (Dr.1.2.C)
# --------------------------------------------------------------------- #
#
# POST /driver/assignments/{id}/verify-age submits a backend-authorized,
# redaction-safe manual 21+ checklist result. The MVP is a manual checklist
# only — no OCR, scan, vendor, or liveness. The request and response carry
# ONLY redaction-safe metadata: outcome, a structured failure reason, boolean
# checklist flags, a safe note, the method (server-set to `manual_checklist`),
# timestamps, and association IDs. They never carry a raw ID image, full ID
# number, OCR/barcode payload, biometric data, signature, customer photo, or
# any artifact path/URL — and never `Order.status`, `Order.age_verified_at`,
# inventory, proof, or customer PII.


class DriverVerifyAgeRequest(BaseModel):
    """Body for POST /driver/assignments/{id}/verify-age.

    `outcome` is required. `failure_reason_code` is required when the outcome
    is `fail` and must be null when the outcome is `pass`; for `manual_review`
    it is optional. `method` is NOT accepted from the client — the backend
    sets it to `manual_checklist`. No sensitive field is accepted.
    """

    outcome: DriverDeliveryVerificationOutcome
    failure_reason_code: DriverDeliveryVerificationFailureReason | None = None
    age_over_21_confirmed: bool | None = None
    id_expiration_checked: bool | None = None
    id_not_expired: bool | None = None
    note: str | None = None

    @model_validator(mode="after")
    def _validate_failure_reason(self) -> "DriverVerifyAgeRequest":
        if (
            self.outcome == DriverDeliveryVerificationOutcome.fail
            and self.failure_reason_code is None
        ):
            raise ValueError(
                "failure_reason_code is required when outcome is 'fail'"
            )
        if (
            self.outcome == DriverDeliveryVerificationOutcome.pass_
            and self.failure_reason_code is not None
        ):
            raise ValueError(
                "failure_reason_code must be null when outcome is 'pass'"
            )
        return self


class DriverDeliveryVerificationRead(BaseModel):
    """Redaction-safe view of a recorded 21+ verification (Dr.1.2.C)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assignment_id: UUID
    order_id: UUID
    driver_profile_id: UUID
    store_id: UUID
    performed_by_user_id: UUID | None
    outcome: str
    failure_reason_code: str | None
    method: str
    age_over_21_confirmed: bool | None
    id_expiration_checked: bool | None
    id_not_expired: bool | None
    note: str | None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------- #
# Proof of delivery (Dr.1.2.D)
# --------------------------------------------------------------------- #
#
# POST /driver/assignments/{id}/proof submits a backend-authorized,
# redaction-safe manual proof-of-delivery checklist on an id_verified
# assignment. The MVP is a manual checklist of a compliant in-person handoff —
# no photo, signature, or uploaded artifact. The request and response carry
# ONLY redaction-safe metadata: the three handoff confirmation flags, a safe
# note, the method (server-set to `manual_checklist`), timestamps, and
# association IDs. They never carry a photo, signature, artifact path/URL,
# customer name/address, ID/OCR/barcode/biometric data, or any other PII — and
# never `Order.status`, `Order.age_verified_at`, or inventory.


class DriverProofSubmitRequest(BaseModel):
    """Body for POST /driver/assignments/{id}/proof.

    All three handoff confirmations are required and must be `True` — a proof
    asserts that a compliant in-person handoff occurred, so any missing or
    `False` confirmation is a 422. `method` is NOT accepted from the client
    (the backend sets it to `manual_checklist`). No sensitive field is
    accepted.
    """

    recipient_present_confirmed: bool
    handoff_confirmed: bool
    restricted_not_left_unattended: bool
    note: str | None = None

    @model_validator(mode="after")
    def _require_all_confirmations_true(self) -> "DriverProofSubmitRequest":
        if not (
            self.recipient_present_confirmed
            and self.handoff_confirmed
            and self.restricted_not_left_unattended
        ):
            raise ValueError(
                "recipient_present_confirmed, handoff_confirmed, and "
                "restricted_not_left_unattended must all be true"
            )
        return self


class DriverDeliveryProofRead(BaseModel):
    """Redaction-safe view of a recorded proof of delivery (Dr.1.2.D)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assignment_id: UUID
    order_id: UUID
    driver_profile_id: UUID
    store_id: UUID
    submitted_by_user_id: UUID | None
    method: str
    recipient_present_confirmed: bool
    handoff_confirmed: bool
    restricted_not_left_unattended: bool
    note: str | None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------- #
# Failed delivery (Dr.1.2.F)
# --------------------------------------------------------------------- #
#
# POST /driver/assignments/{id}/fail records an operational-only failed
# delivery on an in-custody assignment (picked_up .. id_verified). It records
# a `DriverDeliveryFailure` and advances the operational state to
# delivery_failed; it NEVER mutates Order.status, OrderAuditLog, the assignment
# status, or inventory (the commercial/physical resolution — return-to-store,
# store confirmation, cancel/return — is a later subphase). The request and
# response carry ONLY redaction-safe metadata: a structured reason code, a safe
# note, timestamps, and association IDs — never a photo, signature, artifact
# path/URL, ID/OCR/barcode/biometric data, customer name/address, DOB, or any
# other PII.


class DriverFailDeliveryRequest(BaseModel):
    """Body for POST /driver/assignments/{id}/fail.

    `reason_code` is required and must be one of the existing
    `DriverDeliveryFailureReason` codes. `note` is an optional safe note capped
    at 500 chars. No sensitive field is accepted.
    """

    reason_code: DriverDeliveryFailureReason
    note: str | None = Field(default=None, max_length=500)


class DriverDeliveryFailureRead(BaseModel):
    """Redaction-safe view of a recorded failed delivery (Dr.1.2.F)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assignment_id: UUID
    order_id: UUID
    driver_profile_id: UUID
    store_id: UUID
    reported_by_user_id: UUID | None
    reason_code: str
    note: str | None
    created_at: datetime
    updated_at: datetime


# --------------------------------------------------------------------- #
# Return to store (Dr.1.2.G)
# --------------------------------------------------------------------- #
#
# POST /driver/assignments/{id}/return-to-store records the driver's
# operational return-to-store custody progress after a failed delivery:
# `start` (delivery_failed -> returning_to_store, return_state `returning`) and
# `arrive` (returning_to_store -> returned_to_store, return_state
# `returned_pending_confirmation`). It is operational-only — it NEVER mutates
# Order.status, OrderAuditLog, the assignment status, or inventory, and the
# driver NEVER confirms receipt (`return_state=confirmed` / confirmed_at /
# confirmed_by_user_id are reserved for the store-confirmation runtime, Dr.1.2.H).
# The request and response carry ONLY redaction-safe metadata: the action, a
# safe note, timestamps, and association IDs — never a photo, signature,
# artifact path/URL, ID/OCR/barcode/biometric data, customer name/address, or
# any other PII or exact sensitive location detail.


class DriverReturnToStoreAction(str, enum.Enum):
    """The two driver-side return-to-store custody steps (Dr.1.2.G)."""

    start = "start"
    arrive = "arrive"


class DriverReturnToStoreRequest(BaseModel):
    """Body for POST /driver/assignments/{id}/return-to-store.

    `action` is required and must be `start` or `arrive`. `note` is an optional
    safe note capped at 500 chars. No sensitive field is accepted.
    """

    action: DriverReturnToStoreAction
    note: str | None = Field(default=None, max_length=500)


class DriverDeliveryReturnRead(BaseModel):
    """Redaction-safe view of a return-to-store custody record (Dr.1.2.G).

    The `confirmed_*` fields are exposed for forward-compatibility with the
    store-confirmation runtime (Dr.1.2.H) but are always null in G — the driver
    never confirms receipt.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assignment_id: UUID
    order_id: UUID
    driver_profile_id: UUID
    store_id: UUID
    driver_user_id: UUID | None
    confirmed_by_user_id: UUID | None
    return_state: str
    confirmed_at: datetime | None
    note: str | None
    created_at: datetime
    updated_at: datetime
