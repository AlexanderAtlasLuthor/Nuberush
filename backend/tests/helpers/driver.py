"""Test helper for driver profiles (Dr.1.1.C).

Single chokepoint for building `DriverProfile` rows in tests. It persists the
minimal profile only — no documents, vehicles, assignments, delivery state,
eligibility data, payout, or earnings (none of which exist in Dr.1.1.C).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import DriverProfile
from app.db.models import Store
from app.db.models import User


def make_driver_profile(
    db: Session,
    *,
    user: User,
    store: Store,
    status: str = "active",
    approval_status: str = "approved",
    activated_at: datetime | None = None,
    deactivated_at: datetime | None = None,
    approved_at: datetime | None = None,
) -> DriverProfile:
    """Persist and return a ``DriverProfile`` for tests.

    Commits and refreshes so the returned row has its server-side defaults
    (``id``, timestamps) populated.
    """
    profile = DriverProfile(
        user_id=user.id,
        store_id=store.id,
        status=status,
        approval_status=approval_status,
        activated_at=activated_at,
        deactivated_at=deactivated_at,
        approved_at=approved_at,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile
