"""Dr.1.1.E — OrderDriverAssignment model / DB constraint tests.

Exercises the `order_driver_assignments` table directly: creation, the full
status vocabulary, the status CHECK (including that delivery operational
states are rejected), FK integrity, relationships, timestamps, the
ON DELETE RESTRICT on driver_profile, and two structural guards (Order has no
assigned_driver_id, OrderStatus carries no assignment statuses).
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Order
from app.db.models import OrderDriverAssignment
from app.db.models import OrderStatus
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order_driver_assignment


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "ODA-Store") -> Store:
        store = Store(name=name, code=f"oda-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_order(db_session: Session) -> Callable[..., Order]:
    def _create(store: Store) -> Order:
        order = Order(
            store_id=store.id,
            idempotency_key=f"oda-{uuid.uuid4().hex}",
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        return order

    return _create


@pytest.fixture
def assignment_setup(db_session: Session, make_store, make_order):
    """A store + order + driver profile, all in the same store."""

    def _setup():
        store = make_store()
        order = make_order(store)
        user = central_make_user(
            db_session, role=UserRole.driver, store_id=store.id
        )
        profile = make_driver_profile(db_session, user=user, store=store)
        return store, order, profile

    return _setup


# --------------------------------------------------------------------- #
# A. Valid creation
# --------------------------------------------------------------------- #


def test_valid_creation(db_session: Session, assignment_setup) -> None:
    store, order, profile = assignment_setup()
    assignment = make_order_driver_assignment(
        db_session,
        order=order,
        driver_profile=profile,
        store=store,
        status="assigned",
    )

    assert assignment.id is not None
    assert assignment.order_id == order.id
    assert assignment.driver_profile_id == profile.id
    assert assignment.store_id == store.id
    assert assignment.status == "assigned"


# --------------------------------------------------------------------- #
# B. Valid statuses
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "status",
    [
        "offered",
        "accepted",
        "declined",
        "expired",
        "assigned",
        "started",
        "completed",
        "canceled",
    ],
)
def test_valid_statuses_persist(
    db_session: Session, assignment_setup, status: str
) -> None:
    store, order, profile = assignment_setup()
    assignment = make_order_driver_assignment(
        db_session,
        order=order,
        driver_profile=profile,
        store=store,
        status=status,
    )
    assert assignment.status == status


# --------------------------------------------------------------------- #
# C / D. Invalid + delivery-operational statuses rejected by CHECK
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "bad_status",
    [
        "invalid",
        # Delivery operational micro-states must NEVER be assignment status.
        "pickup_confirmed",
        "en_route_to_customer",
        "delivered",
        "id_verified",
        "proof_collected",
    ],
)
def test_invalid_status_rejected(
    db_session: Session, assignment_setup, bad_status: str
) -> None:
    store, order, profile = assignment_setup()
    with pytest.raises(IntegrityError):
        db_session.add(
            OrderDriverAssignment(
                order_id=order.id,
                driver_profile_id=profile.id,
                store_id=store.id,
                status=bad_status,
            )
        )
        db_session.commit()
    db_session.rollback()


# --------------------------------------------------------------------- #
# E. FK integrity
# --------------------------------------------------------------------- #


def test_invalid_order_fk_rejected(
    db_session: Session, assignment_setup
) -> None:
    store, _order, profile = assignment_setup()
    with pytest.raises(IntegrityError):
        db_session.add(
            OrderDriverAssignment(
                order_id=uuid.uuid4(),
                driver_profile_id=profile.id,
                store_id=store.id,
                status="assigned",
            )
        )
        db_session.commit()
    db_session.rollback()


def test_invalid_driver_profile_fk_rejected(
    db_session: Session, assignment_setup
) -> None:
    store, order, _profile = assignment_setup()
    with pytest.raises(IntegrityError):
        db_session.add(
            OrderDriverAssignment(
                order_id=order.id,
                driver_profile_id=uuid.uuid4(),
                store_id=store.id,
                status="assigned",
            )
        )
        db_session.commit()
    db_session.rollback()


def test_invalid_store_fk_rejected(
    db_session: Session, assignment_setup
) -> None:
    _store, order, profile = assignment_setup()
    with pytest.raises(IntegrityError):
        db_session.add(
            OrderDriverAssignment(
                order_id=order.id,
                driver_profile_id=profile.id,
                store_id=uuid.uuid4(),
                status="assigned",
            )
        )
        db_session.commit()
    db_session.rollback()


# --------------------------------------------------------------------- #
# F. Relationships
# --------------------------------------------------------------------- #


def test_relationships(db_session: Session, assignment_setup) -> None:
    store, order, profile = assignment_setup()
    assignment = make_order_driver_assignment(
        db_session, order=order, driver_profile=profile, store=store
    )

    assert assignment.order.id == order.id
    assert assignment.driver_profile.id == profile.id
    assert assignment.store.id == store.id

    db_session.refresh(order)
    db_session.refresh(profile)
    db_session.refresh(store)
    assert assignment.id in {a.id for a in order.driver_assignments}
    assert assignment.id in {a.id for a in profile.assignments}
    assert assignment.id in {a.id for a in store.driver_assignments}


# --------------------------------------------------------------------- #
# G. Timestamps
# --------------------------------------------------------------------- #


def test_timestamps(db_session: Session, assignment_setup) -> None:
    store, order, profile = assignment_setup()
    assignment = make_order_driver_assignment(
        db_session, order=order, driver_profile=profile, store=store
    )

    assert assignment.created_at is not None
    assert assignment.updated_at is not None
    assert assignment.assigned_at is None
    assert assignment.accepted_at is None
    assert assignment.declined_at is None
    assert assignment.canceled_at is None
    assert assignment.completed_at is None


# --------------------------------------------------------------------- #
# H. DriverProfile delete restriction (ON DELETE RESTRICT)
# --------------------------------------------------------------------- #


def test_driver_profile_delete_restricted(
    db_session: Session, assignment_setup
) -> None:
    store, order, profile = assignment_setup()
    make_order_driver_assignment(
        db_session, order=order, driver_profile=profile, store=store
    )

    with pytest.raises(IntegrityError):
        db_session.delete(profile)
        db_session.commit()
    db_session.rollback()


# --------------------------------------------------------------------- #
# I. Order must NOT carry a direct driver column (Dr.1.1.A §10)
# --------------------------------------------------------------------- #


def test_order_has_no_direct_driver_column() -> None:
    order_columns = set(Order.__table__.columns.keys())
    assert "assigned_driver_id" not in order_columns
    assert "driver_id" not in order_columns


# --------------------------------------------------------------------- #
# J. OrderStatus must NOT leak assignment statuses (Dr.1.1.A §11)
# --------------------------------------------------------------------- #


def test_order_status_excludes_assignment_statuses() -> None:
    order_status_values = {s.value for s in OrderStatus}
    for leaked in ("offered", "assigned", "started", "expired"):
        assert leaked not in order_status_values
