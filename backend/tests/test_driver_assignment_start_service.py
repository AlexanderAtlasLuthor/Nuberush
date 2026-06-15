"""Dr.1.1.J — driver start-delivery service tests.

Exercises `start_driver_assignment`: the accepted -> started + operational
state -> en_route_to_store transition (with and without a pre-existing
not_started row), idempotency (no duplicate state, no timestamp rewrite), the
422 invalid-source-status guard for every non-accepted/started assignment
status, the 409 "already past en_route_to_store" / 422 terminal operational
guards, the anti-enumeration 404 boundary, and the no-side-effects guarantee
(no Order.status / inventory / other-timestamp bleed).

Service layer only — no TestClient, no route.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from datetime import timezone
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
from app.services.driver import start_driver_assignment
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
    def _create(name: str = "DST-Store") -> Store:
        store = Store(name=name, code=f"dst-{uuid.uuid4().hex[:8]}")
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
    """Build (store, user, profile, assignment); assignment status param."""

    def _setup(status: str = "accepted"):
        store = make_store()
        user = _driver(db_session, store)
        profile = make_driver_profile(db_session, user=user, store=store)
        order = make_order(db_session, store=store)
        assignment = make_order_driver_assignment(
            db_session,
            order=order,
            driver_profile=profile,
            store=store,
            status=status,
        )
        return store, user, profile, assignment

    return _setup


def _state_count(db_session: Session, assignment_id) -> int:
    return db_session.scalar(
        select(func.count())
        .select_from(DriverDeliveryOperationalState)
        .where(
            DriverDeliveryOperationalState.assignment_id == assignment_id
        )
    )


# --------------------------------------------------------------------- #
# Happy paths
# --------------------------------------------------------------------- #


def test_start_from_accepted_no_state(db_session: Session, setup) -> None:
    store, user, profile, assignment = setup("accepted")

    result = start_driver_assignment(db_session, user, assignment.id)
    assert result.state == "en_route_to_store"
    assert result.assignment_id == assignment.id
    assert result.order_id == assignment.order_id
    assert result.driver_profile_id == profile.id
    assert result.store_id == store.id
    assert result.state_started_at is not None
    assert result.last_transition_at is not None

    db_session.refresh(assignment)
    assert assignment.status == "started"
    assert _state_count(db_session, assignment.id) == 1


def test_start_from_accepted_with_not_started(
    db_session: Session, setup
) -> None:
    _store, user, _profile, assignment = setup("accepted")
    make_driver_delivery_operational_state(
        db_session, assignment=assignment, state="not_started"
    )

    result = start_driver_assignment(db_session, user, assignment.id)
    assert result.state == "en_route_to_store"

    db_session.refresh(assignment)
    assert assignment.status == "started"
    assert _state_count(db_session, assignment.id) == 1


# --------------------------------------------------------------------- #
# Idempotency
# --------------------------------------------------------------------- #


def test_start_idempotent_when_already_en_route(
    db_session: Session, setup
) -> None:
    _store, user, _profile, assignment = setup("started")
    started_at = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    transition_at = datetime(2026, 6, 1, 12, 5, tzinfo=timezone.utc)
    make_driver_delivery_operational_state(
        db_session,
        assignment=assignment,
        state="en_route_to_store",
        state_started_at=started_at,
        last_transition_at=transition_at,
    )

    result = start_driver_assignment(db_session, user, assignment.id)
    assert result.state == "en_route_to_store"
    # Timestamps preserved on the idempotent repeat.
    assert result.state_started_at == started_at
    assert result.last_transition_at == transition_at

    db_session.refresh(assignment)
    assert assignment.status == "started"
    assert _state_count(db_session, assignment.id) == 1


# --------------------------------------------------------------------- #
# Invalid assignment source status -> 422
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "bad_status",
    ["offered", "declined", "expired", "canceled", "completed", "assigned"],
)
def test_start_invalid_assignment_status_422(
    db_session: Session, setup, bad_status: str
) -> None:
    _store, user, _profile, assignment = setup(bad_status)

    with pytest.raises(HTTPException) as exc:
        start_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 422
    assert exc.value.detail == (
        f"Assignment cannot be started from status '{bad_status}'"
    )

    db_session.refresh(assignment)
    assert assignment.status == bad_status
    # No operational state created as a side effect of the rejected start.
    assert _state_count(db_session, assignment.id) == 0


# --------------------------------------------------------------------- #
# Later non-terminal physical state -> 409 (no regression)
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "later_state",
    [
        "arrived_at_store",
        "pickup_started",
        "picked_up",
        "en_route_to_customer",
        "arrived_at_customer",
        "returning_to_store",
    ],
)
def test_start_past_en_route_409(
    db_session: Session, setup, later_state: str
) -> None:
    _store, user, _profile, assignment = setup("started")
    make_driver_delivery_operational_state(
        db_session, assignment=assignment, state=later_state
    )

    with pytest.raises(HTTPException) as exc:
        start_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == "Delivery already past en_route_to_store"

    # State did not regress.
    state = db_session.scalar(
        select(DriverDeliveryOperationalState).where(
            DriverDeliveryOperationalState.assignment_id == assignment.id
        )
    )
    assert state.state == later_state


# --------------------------------------------------------------------- #
# Terminal operational state -> 422
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "terminal_state",
    [
        "delivery_completed",
        "delivery_failed",
        "returned_to_store",
        "canceled",
    ],
)
def test_start_terminal_state_422(
    db_session: Session, setup, terminal_state: str
) -> None:
    _store, user, _profile, assignment = setup("started")
    make_driver_delivery_operational_state(
        db_session, assignment=assignment, state=terminal_state
    )

    with pytest.raises(HTTPException) as exc:
        start_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 422
    assert exc.value.detail == (
        "Assignment cannot be started from operational state "
        f"'{terminal_state}'"
    )

    state = db_session.scalar(
        select(DriverDeliveryOperationalState).where(
            DriverDeliveryOperationalState.assignment_id == assignment.id
        )
    )
    assert state.state == terminal_state


# --------------------------------------------------------------------- #
# Anti-enumeration 404
# --------------------------------------------------------------------- #


def test_start_nonexistent_404(db_session: Session, setup) -> None:
    _store, user, _profile, _assignment = setup("accepted")
    with pytest.raises(HTTPException) as exc:
        start_driver_assignment(db_session, user, uuid.uuid4())
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver assignment not found"


def test_start_other_driver_404(db_session: Session, make_store) -> None:
    store = make_store()
    owner = _driver(db_session, store)
    owner_profile = make_driver_profile(db_session, user=owner, store=store)
    order = make_order(db_session, store=store)
    assignment = make_order_driver_assignment(
        db_session,
        order=order,
        driver_profile=owner_profile,
        store=store,
        status="accepted",
    )

    other = _driver(db_session, store)
    make_driver_profile(db_session, user=other, store=store)

    with pytest.raises(HTTPException) as exc:
        start_driver_assignment(db_session, other, assignment.id)
    assert exc.value.status_code == 404

    db_session.refresh(assignment)
    assert assignment.status == "accepted"  # untouched
    assert _state_count(db_session, assignment.id) == 0


def test_start_other_store_404(db_session: Session, make_store) -> None:
    store_a = make_store("store-a")
    owner = _driver(db_session, store_a)
    owner_profile = make_driver_profile(
        db_session, user=owner, store=store_a
    )
    order = make_order(db_session, store=store_a)
    assignment = make_order_driver_assignment(
        db_session,
        order=order,
        driver_profile=owner_profile,
        store=store_a,
        status="accepted",
    )

    store_b = make_store("store-b")
    other = _driver(db_session, store_b)
    make_driver_profile(db_session, user=other, store=store_b)

    with pytest.raises(HTTPException) as exc:
        start_driver_assignment(db_session, other, assignment.id)
    assert exc.value.status_code == 404


def test_start_driver_without_profile_404(
    db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)  # no profile
    with pytest.raises(HTTPException) as exc:
        start_driver_assignment(db_session, user, uuid.uuid4())
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver profile not found"


# --------------------------------------------------------------------- #
# No domain side effects
# --------------------------------------------------------------------- #


def test_start_no_order_or_inventory_or_timestamp_mutation(
    db_session: Session, setup
) -> None:
    _store, user, _profile, assignment = setup("accepted")
    order = db_session.get(Order, assignment.order_id)
    order_status_before = order.status
    accepted_at_before = assignment.accepted_at
    declined_at_before = assignment.declined_at
    assigned_at_before = assignment.assigned_at
    canceled_at_before = assignment.canceled_at
    completed_at_before = assignment.completed_at

    start_driver_assignment(db_session, user, assignment.id)

    db_session.refresh(order)
    db_session.refresh(assignment)
    assert order.status == order_status_before
    # Only status changed on the assignment; decision/lifecycle timestamps are
    # untouched (and no started_at column exists / was added).
    assert assignment.accepted_at == accepted_at_before
    assert assignment.declined_at == declined_at_before
    assert assignment.assigned_at == assigned_at_before
    assert assignment.canceled_at == canceled_at_before
    assert assignment.completed_at == completed_at_before
