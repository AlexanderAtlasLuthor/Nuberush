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
