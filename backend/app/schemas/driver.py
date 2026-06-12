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
