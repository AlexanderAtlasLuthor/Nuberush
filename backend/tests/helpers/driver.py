"""Test helpers for the driver domain (Dr.1.1.C / Dr.1.1.E).

Chokepoints for building `DriverProfile` (Dr.1.1.C) and
`OrderDriverAssignment` (Dr.1.1.E) rows in tests. They persist the minimal
foundation rows only — no documents, vehicles, delivery state, dispatch
logic, eligibility data, payout, or earnings.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.db.models import DriverProfile
from app.db.models import Order
from app.db.models import OrderDriverAssignment
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


def make_order_driver_assignment(
    db: Session,
    *,
    order: Order,
    driver_profile: DriverProfile,
    store: Store,
    status: str = "assigned",
) -> OrderDriverAssignment:
    """Persist and return an ``OrderDriverAssignment`` for tests (Dr.1.1.E).

    The caller passes explicit order / driver_profile / store so tenancy
    setup stays visible in the test. This builds ONLY the assignment row: it
    runs no dispatch logic, mutates no order status, and triggers no driver
    actions. Commits and refreshes so server-side defaults are populated.
    """
    assignment = OrderDriverAssignment(
        order_id=order.id,
        driver_profile_id=driver_profile.id,
        store_id=store.id,
        status=status,
    )
    db.add(assignment)
    db.commit()
    db.refresh(assignment)
    return assignment
