"""Dr.1.1.G.3 — delivery operational state read/ensure service tests.

Exercises `get_driver_delivery_operational_state` and
`ensure_driver_delivery_operational_state`: self-scoping by `DriverProfile`,
store binding, the anti-enumeration 404 boundaries, idempotent creation of the
initial `not_started` row, and the guarantee that ensuring state never mutates
the order, the assignment, or `OrderStatus` / `OrderDriverAssignmentStatus`.

Service layer only — no TestClient, no route, no public API.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import DriverDeliveryOperationalState
from app.db.models import Order
from app.db.models import OrderDriverAssignment
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.services.driver import ensure_driver_delivery_operational_state
from app.services.driver import get_driver_delivery_operational_state
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_delivery_operational_state
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "DDOSS-Store") -> Store:
        store = Store(name=name, code=f"ddoss-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


def _driver(db_session: Session, store: Store) -> User:
    return central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )


@pytest.fixture
def setup(db_session: Session, make_store):
    """Build a driver + their own assignment in a fresh store.

    Returns (store, user, profile, assignment).
    """

    def _setup():
        store = make_store()
        user = _driver(db_session, store)
        profile = make_driver_profile(db_session, user=user, store=store)
        order = make_order(db_session, store=store)
        assignment = make_order_driver_assignment(
            db_session, order=order, driver_profile=profile, store=store
        )
        return store, user, profile, assignment

    return _setup


# --------------------------------------------------------------------- #
# A. get returns own existing state
# --------------------------------------------------------------------- #


def test_get_returns_own_state(db_session: Session, setup) -> None:
    store, user, profile, assignment = setup()
    state = make_driver_delivery_operational_state(
        db_session, assignment=assignment
    )

    result = get_driver_delivery_operational_state(
        db_session, user, assignment.id
    )
    assert result.id == state.id
    assert result.assignment_id == assignment.id
    assert result.order_id == assignment.order_id
    assert result.driver_profile_id == profile.id
    assert result.store_id == store.id
    assert result.state == "not_started"


# --------------------------------------------------------------------- #
# B. get 404 when no state exists yet (owned assignment)
# --------------------------------------------------------------------- #


def test_get_404_when_state_missing(db_session: Session, setup) -> None:
    _store, user, _profile, assignment = setup()

    with pytest.raises(HTTPException) as exc:
        get_driver_delivery_operational_state(
            db_session, user, assignment.id
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver delivery operational state not found"


# --------------------------------------------------------------------- #
# C. get 404 for another driver's assignment (same store)
# --------------------------------------------------------------------- #


def test_get_404_other_driver(db_session: Session, make_store) -> None:
    store = make_store()

    user_a = _driver(db_session, store)
    profile_a = make_driver_profile(db_session, user=user_a, store=store)
    order_a = make_order(db_session, store=store)
    assignment_a = make_order_driver_assignment(
        db_session, order=order_a, driver_profile=profile_a, store=store
    )
    make_driver_delivery_operational_state(
        db_session, assignment=assignment_a
    )

    user_b = _driver(db_session, store)
    make_driver_profile(db_session, user=user_b, store=store)

    with pytest.raises(HTTPException) as exc:
        get_driver_delivery_operational_state(
            db_session, user_b, assignment_a.id
        )
    # Anti-enumeration: a foreign assignment is "not found", not "no state".
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver assignment not found"


# --------------------------------------------------------------------- #
# D. get 404 for another store's assignment
# --------------------------------------------------------------------- #


def test_get_404_other_store(db_session: Session, make_store) -> None:
    store_a = make_store("store-a")
    user_a = _driver(db_session, store_a)
    profile_a = make_driver_profile(db_session, user=user_a, store=store_a)
    order_a = make_order(db_session, store=store_a)
    assignment_a = make_order_driver_assignment(
        db_session, order=order_a, driver_profile=profile_a, store=store_a
    )
    make_driver_delivery_operational_state(
        db_session, assignment=assignment_a
    )

    store_b = make_store("store-b")
    user_b = _driver(db_session, store_b)
    make_driver_profile(db_session, user=user_b, store=store_b)

    with pytest.raises(HTTPException) as exc:
        get_driver_delivery_operational_state(
            db_session, user_b, assignment_a.id
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver assignment not found"


def test_get_404_nonexistent_assignment(
    db_session: Session, setup
) -> None:
    _store, user, _profile, _assignment = setup()
    with pytest.raises(HTTPException) as exc:
        get_driver_delivery_operational_state(
            db_session, user, uuid.uuid4()
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver assignment not found"


# --------------------------------------------------------------------- #
# E. ensure creates not_started with correct anchors
# --------------------------------------------------------------------- #


def test_ensure_creates_not_started(db_session: Session, setup) -> None:
    store, user, profile, assignment = setup()

    result = ensure_driver_delivery_operational_state(
        db_session, user, assignment.id
    )
    assert result.state == "not_started"
    assert result.assignment_id == assignment.id
    assert result.order_id == assignment.order_id
    assert result.driver_profile_id == profile.id
    assert result.store_id == store.id
    assert result.id is not None

    # The row is now persisted and readable via get.
    fetched = get_driver_delivery_operational_state(
        db_session, user, assignment.id
    )
    assert fetched.id == result.id


# --------------------------------------------------------------------- #
# F. ensure is idempotent
# --------------------------------------------------------------------- #


def test_ensure_is_idempotent(db_session: Session, setup) -> None:
    _store, user, _profile, assignment = setup()

    first = ensure_driver_delivery_operational_state(
        db_session, user, assignment.id
    )
    second = ensure_driver_delivery_operational_state(
        db_session, user, assignment.id
    )

    assert first.id == second.id

    count = db_session.scalar(
        select(func.count())
        .select_from(DriverDeliveryOperationalState)
        .where(
            DriverDeliveryOperationalState.assignment_id == assignment.id
        )
    )
    assert count == 1


def test_ensure_returns_existing_state(
    db_session: Session, setup
) -> None:
    _store, user, _profile, assignment = setup()
    seeded = make_driver_delivery_operational_state(
        db_session, assignment=assignment
    )

    result = ensure_driver_delivery_operational_state(
        db_session, user, assignment.id
    )
    assert result.id == seeded.id


# --------------------------------------------------------------------- #
# G. ensure does not mutate domain state
# --------------------------------------------------------------------- #


def test_ensure_does_not_mutate_domain(
    db_session: Session, setup
) -> None:
    _store, user, _profile, assignment = setup()

    order = db_session.get(Order, assignment.order_id)
    order_status_before = order.status
    assignment_status_before = assignment.status

    ensure_driver_delivery_operational_state(
        db_session, user, assignment.id
    )

    db_session.refresh(order)
    db_session.refresh(assignment)
    assert order.status == order_status_before
    assert assignment.status == assignment_status_before
    # Exactly one Order and one assignment still exist for this setup (no
    # spurious rows created); operational-state creation is the only insert.
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(OrderDriverAssignment)
            .where(OrderDriverAssignment.id == assignment.id)
        )
        == 1
    )


# --------------------------------------------------------------------- #
# H/I. ensure self-scope 404s
# --------------------------------------------------------------------- #


def test_ensure_404_other_driver(db_session: Session, make_store) -> None:
    store = make_store()
    user_a = _driver(db_session, store)
    profile_a = make_driver_profile(db_session, user=user_a, store=store)
    order_a = make_order(db_session, store=store)
    assignment_a = make_order_driver_assignment(
        db_session, order=order_a, driver_profile=profile_a, store=store
    )

    user_b = _driver(db_session, store)
    make_driver_profile(db_session, user=user_b, store=store)

    with pytest.raises(HTTPException) as exc:
        ensure_driver_delivery_operational_state(
            db_session, user_b, assignment_a.id
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver assignment not found"

    # No state was created for the foreign assignment.
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(DriverDeliveryOperationalState)
            .where(
                DriverDeliveryOperationalState.assignment_id
                == assignment_a.id
            )
        )
        == 0
    )


def test_ensure_404_other_store(db_session: Session, make_store) -> None:
    store_a = make_store("store-a")
    user_a = _driver(db_session, store_a)
    profile_a = make_driver_profile(db_session, user=user_a, store=store_a)
    order_a = make_order(db_session, store=store_a)
    assignment_a = make_order_driver_assignment(
        db_session, order=order_a, driver_profile=profile_a, store=store_a
    )

    store_b = make_store("store-b")
    user_b = _driver(db_session, store_b)
    make_driver_profile(db_session, user=user_b, store=store_b)

    with pytest.raises(HTTPException) as exc:
        ensure_driver_delivery_operational_state(
            db_session, user_b, assignment_a.id
        )
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver assignment not found"


# --------------------------------------------------------------------- #
# Driver without a profile -> 404 (via get_driver_profile_for_user)
# --------------------------------------------------------------------- #


def test_get_driver_without_profile_404(
    db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)  # no profile provisioned
    with pytest.raises(HTTPException) as exc:
        get_driver_delivery_operational_state(
            db_session, user, uuid.uuid4()
        )
    assert exc.value.status_code == 404


def test_ensure_driver_without_profile_404(
    db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    with pytest.raises(HTTPException) as exc:
        ensure_driver_delivery_operational_state(
            db_session, user, uuid.uuid4()
        )
    assert exc.value.status_code == 404
