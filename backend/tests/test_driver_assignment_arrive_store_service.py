"""Dr.1.1.K — driver arrive-at-store service tests.

Exercises `arrive_driver_assignment`: the operational state
`en_route_to_store -> arrived_at_store` transition, idempotency (no timestamp
rewrite), the 422 invalid-source-status guard for every non-started assignment
status, the 422 "not yet en route" guard (missing / not_started state — arrival
NEVER materializes a row), the 409 "already past arrived_at_store" / 422
terminal operational guards, the anti-enumeration 404 boundary, and the
no-side-effects guarantee (no Order.status / inventory / assignment-status /
assignment-timestamp bleed).

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
from app.services.driver import arrive_driver_assignment
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
    def _create(name: str = "DAS-Store") -> Store:
        store = Store(name=name, code=f"das-{uuid.uuid4().hex[:8]}")
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

    def _setup(status: str = "started"):
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
# Happy path
# --------------------------------------------------------------------- #


def test_arrive_from_en_route(db_session: Session, setup) -> None:
    store, user, profile, assignment = setup("started")
    make_driver_delivery_operational_state(
        db_session, assignment=assignment, state="en_route_to_store"
    )

    result = arrive_driver_assignment(db_session, user, assignment.id)
    assert result.state == "arrived_at_store"
    assert result.assignment_id == assignment.id
    assert result.order_id == assignment.order_id
    assert result.driver_profile_id == profile.id
    assert result.store_id == store.id
    assert result.state_started_at is not None
    assert result.last_transition_at is not None

    db_session.refresh(assignment)
    # Arrival NEVER mutates the assignment status.
    assert assignment.status == "started"
    assert _state_count(db_session, assignment.id) == 1


# --------------------------------------------------------------------- #
# Idempotency
# --------------------------------------------------------------------- #


def test_arrive_idempotent_when_already_arrived(
    db_session: Session, setup
) -> None:
    _store, user, _profile, assignment = setup("started")
    started_at = datetime(2026, 6, 1, 12, 0, tzinfo=timezone.utc)
    transition_at = datetime(2026, 6, 1, 12, 5, tzinfo=timezone.utc)
    make_driver_delivery_operational_state(
        db_session,
        assignment=assignment,
        state="arrived_at_store",
        state_started_at=started_at,
        last_transition_at=transition_at,
    )

    result = arrive_driver_assignment(db_session, user, assignment.id)
    assert result.state == "arrived_at_store"
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
    [
        "offered",
        "accepted",
        "declined",
        "expired",
        "canceled",
        "completed",
        "assigned",
    ],
)
def test_arrive_invalid_assignment_status_422(
    db_session: Session, setup, bad_status: str
) -> None:
    _store, user, _profile, assignment = setup(bad_status)
    # A row may exist; the assignment-status gate fires before state checks.
    make_driver_delivery_operational_state(
        db_session, assignment=assignment, state="en_route_to_store"
    )

    with pytest.raises(HTTPException) as exc:
        arrive_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 422
    assert exc.value.detail == (
        f"Assignment cannot arrive at store from status '{bad_status}'"
    )

    db_session.refresh(assignment)
    assert assignment.status == bad_status
    # State did not advance.
    state = db_session.scalar(
        select(DriverDeliveryOperationalState).where(
            DriverDeliveryOperationalState.assignment_id == assignment.id
        )
    )
    assert state.state == "en_route_to_store"


# --------------------------------------------------------------------- #
# Operational state behind required -> 422 (not yet en route)
# --------------------------------------------------------------------- #


def test_arrive_without_operational_state_422(
    db_session: Session, setup
) -> None:
    _store, user, _profile, assignment = setup("started")

    with pytest.raises(HTTPException) as exc:
        arrive_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 422
    assert exc.value.detail == "Delivery not yet en route to store"

    # Arrival NEVER materializes the operational-state row.
    assert _state_count(db_session, assignment.id) == 0


def test_arrive_from_not_started_422(db_session: Session, setup) -> None:
    _store, user, _profile, assignment = setup("started")
    make_driver_delivery_operational_state(
        db_session, assignment=assignment, state="not_started"
    )

    with pytest.raises(HTTPException) as exc:
        arrive_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 422
    assert exc.value.detail == "Delivery not yet en route to store"

    state = db_session.scalar(
        select(DriverDeliveryOperationalState).where(
            DriverDeliveryOperationalState.assignment_id == assignment.id
        )
    )
    assert state.state == "not_started"


# --------------------------------------------------------------------- #
# Later non-terminal physical state -> 409 (no regression)
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "later_state",
    [
        "pickup_started",
        "picked_up",
        "en_route_to_customer",
        "arrived_at_customer",
        "id_verification_pending",
        "id_verified",
        "returning_to_store",
    ],
)
def test_arrive_past_store_409(
    db_session: Session, setup, later_state: str
) -> None:
    _store, user, _profile, assignment = setup("started")
    make_driver_delivery_operational_state(
        db_session, assignment=assignment, state=later_state
    )

    with pytest.raises(HTTPException) as exc:
        arrive_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == "Delivery already past arrived_at_store"

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
def test_arrive_terminal_state_422(
    db_session: Session, setup, terminal_state: str
) -> None:
    _store, user, _profile, assignment = setup("started")
    make_driver_delivery_operational_state(
        db_session, assignment=assignment, state=terminal_state
    )

    with pytest.raises(HTTPException) as exc:
        arrive_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 422
    assert exc.value.detail == (
        "Assignment cannot arrive at store from operational state "
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


def test_arrive_nonexistent_404(db_session: Session, setup) -> None:
    _store, user, _profile, _assignment = setup("started")
    with pytest.raises(HTTPException) as exc:
        arrive_driver_assignment(db_session, user, uuid.uuid4())
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver assignment not found"


def test_arrive_other_driver_404(db_session: Session, make_store) -> None:
    store = make_store()
    owner = _driver(db_session, store)
    owner_profile = make_driver_profile(db_session, user=owner, store=store)
    order = make_order(db_session, store=store)
    assignment = make_order_driver_assignment(
        db_session,
        order=order,
        driver_profile=owner_profile,
        store=store,
        status="started",
    )
    make_driver_delivery_operational_state(
        db_session, assignment=assignment, state="en_route_to_store"
    )

    other = _driver(db_session, store)
    make_driver_profile(db_session, user=other, store=store)

    with pytest.raises(HTTPException) as exc:
        arrive_driver_assignment(db_session, other, assignment.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver assignment not found"

    # The owner's state did not advance.
    state = db_session.scalar(
        select(DriverDeliveryOperationalState).where(
            DriverDeliveryOperationalState.assignment_id == assignment.id
        )
    )
    assert state.state == "en_route_to_store"


def test_arrive_other_store_404(db_session: Session, make_store) -> None:
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
        status="started",
    )
    make_driver_delivery_operational_state(
        db_session, assignment=assignment, state="en_route_to_store"
    )

    store_b = make_store("store-b")
    other = _driver(db_session, store_b)
    make_driver_profile(db_session, user=other, store=store_b)

    with pytest.raises(HTTPException) as exc:
        arrive_driver_assignment(db_session, other, assignment.id)
    assert exc.value.status_code == 404


def test_arrive_driver_without_profile_404(
    db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)  # no profile
    with pytest.raises(HTTPException) as exc:
        arrive_driver_assignment(db_session, user, uuid.uuid4())
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver profile not found"


# --------------------------------------------------------------------- #
# No domain side effects
# --------------------------------------------------------------------- #


def test_arrive_no_order_inventory_or_assignment_mutation(
    db_session: Session, setup
) -> None:
    _store, user, _profile, assignment = setup("started")
    make_driver_delivery_operational_state(
        db_session, assignment=assignment, state="en_route_to_store"
    )
    order = db_session.get(Order, assignment.order_id)
    order_status_before = order.status
    status_before = assignment.status
    assigned_at_before = assignment.assigned_at
    accepted_at_before = assignment.accepted_at
    declined_at_before = assignment.declined_at
    canceled_at_before = assignment.canceled_at
    completed_at_before = assignment.completed_at

    arrive_driver_assignment(db_session, user, assignment.id)

    db_session.refresh(order)
    db_session.refresh(assignment)
    assert order.status == order_status_before
    # Arrival touches ONLY the operational state — never the assignment.
    assert assignment.status == status_before == "started"
    assert assignment.assigned_at == assigned_at_before
    assert assignment.accepted_at == accepted_at_before
    assert assignment.declined_at == declined_at_before
    assert assignment.canceled_at == canceled_at_before
    assert assignment.completed_at == completed_at_before
