"""Dr.1.1.I — driver assignment accept/decline service tests.

Exercises `accept_driver_assignment` and `decline_driver_assignment`: the
happy paths (offered -> accepted/declined + the right timestamp), idempotent
repeats, the 409 opposite-decision conflict, the 422 invalid-transition guard
for every non-offered status, the anti-enumeration 404 boundary, and the
no-side-effects guarantee (no Order.status / operational-state / timestamp
bleed).

Service layer only — no TestClient, no route.
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
from app.services.driver import accept_driver_assignment
from app.services.driver import decline_driver_assignment
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "DAD-Store") -> Store:
        store = Store(name=name, code=f"dad-{uuid.uuid4().hex[:8]}")
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
    """Returns a callable building (store, user, profile, assignment).

    The assignment status defaults to "offered".
    """

    def _setup(status: str = "offered"):
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


# --------------------------------------------------------------------- #
# A/B. Happy paths
# --------------------------------------------------------------------- #


def test_accept_happy_path(db_session: Session, setup) -> None:
    _store, user, _profile, assignment = setup("offered")

    result = accept_driver_assignment(db_session, user, assignment.id)
    assert result.status == "accepted"
    assert result.accepted_at is not None
    assert result.declined_at is None

    db_session.refresh(assignment)
    assert assignment.status == "accepted"
    assert assignment.accepted_at is not None
    assert assignment.declined_at is None


def test_decline_happy_path(db_session: Session, setup) -> None:
    _store, user, _profile, assignment = setup("offered")

    result = decline_driver_assignment(db_session, user, assignment.id)
    assert result.status == "declined"
    assert result.declined_at is not None
    assert result.accepted_at is None

    db_session.refresh(assignment)
    assert assignment.status == "declined"
    assert assignment.declined_at is not None
    assert assignment.accepted_at is None


# --------------------------------------------------------------------- #
# C/D. Idempotent repeats
# --------------------------------------------------------------------- #


def test_double_accept_idempotent(db_session: Session, setup) -> None:
    _store, user, _profile, assignment = setup("offered")

    first = accept_driver_assignment(db_session, user, assignment.id)
    second = accept_driver_assignment(db_session, user, assignment.id)

    assert second.status == "accepted"
    assert second.accepted_at == first.accepted_at  # not rewritten
    assert second.declined_at is None


def test_double_decline_idempotent(db_session: Session, setup) -> None:
    _store, user, _profile, assignment = setup("offered")

    first = decline_driver_assignment(db_session, user, assignment.id)
    second = decline_driver_assignment(db_session, user, assignment.id)

    assert second.status == "declined"
    assert second.declined_at == first.declined_at  # not rewritten
    assert second.accepted_at is None


# --------------------------------------------------------------------- #
# E/F. Opposite-decision conflict (409)
# --------------------------------------------------------------------- #


def test_accept_after_decline_409(db_session: Session, setup) -> None:
    _store, user, _profile, assignment = setup("offered")
    declined = decline_driver_assignment(db_session, user, assignment.id)

    with pytest.raises(HTTPException) as exc:
        accept_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == "Assignment already declined"

    db_session.refresh(assignment)
    assert assignment.status == "declined"
    assert assignment.declined_at == declined.declined_at
    assert assignment.accepted_at is None


def test_decline_after_accept_409(db_session: Session, setup) -> None:
    _store, user, _profile, assignment = setup("offered")
    accepted = accept_driver_assignment(db_session, user, assignment.id)

    with pytest.raises(HTTPException) as exc:
        decline_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 409
    assert exc.value.detail == "Assignment already accepted"

    db_session.refresh(assignment)
    assert assignment.status == "accepted"
    assert assignment.accepted_at == accepted.accepted_at
    assert assignment.declined_at is None


# --------------------------------------------------------------------- #
# G. Invalid transitions (422) from every non-offered source status
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "bad_status",
    ["expired", "canceled", "completed", "started", "assigned"],
)
def test_accept_invalid_transition_422(
    db_session: Session, setup, bad_status: str
) -> None:
    _store, user, _profile, assignment = setup(bad_status)

    with pytest.raises(HTTPException) as exc:
        accept_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 422
    assert exc.value.detail == (
        f"Assignment cannot be accepted from status '{bad_status}'"
    )

    db_session.refresh(assignment)
    assert assignment.status == bad_status
    assert assignment.accepted_at is None
    assert assignment.declined_at is None


@pytest.mark.parametrize(
    "bad_status",
    ["expired", "canceled", "completed", "started", "assigned"],
)
def test_decline_invalid_transition_422(
    db_session: Session, setup, bad_status: str
) -> None:
    _store, user, _profile, assignment = setup(bad_status)

    with pytest.raises(HTTPException) as exc:
        decline_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 422
    assert exc.value.detail == (
        f"Assignment cannot be declined from status '{bad_status}'"
    )

    db_session.refresh(assignment)
    assert assignment.status == bad_status
    assert assignment.declined_at is None
    assert assignment.accepted_at is None


# --------------------------------------------------------------------- #
# H. Anti-enumeration 404
# --------------------------------------------------------------------- #


def test_accept_nonexistent_404(db_session: Session, setup) -> None:
    _store, user, _profile, _assignment = setup("offered")
    with pytest.raises(HTTPException) as exc:
        accept_driver_assignment(db_session, user, uuid.uuid4())
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver assignment not found"


def test_accept_other_driver_404(db_session: Session, make_store) -> None:
    store = make_store()
    owner = _driver(db_session, store)
    owner_profile = make_driver_profile(db_session, user=owner, store=store)
    order = make_order(db_session, store=store)
    assignment = make_order_driver_assignment(
        db_session,
        order=order,
        driver_profile=owner_profile,
        store=store,
        status="offered",
    )

    other = _driver(db_session, store)
    make_driver_profile(db_session, user=other, store=store)

    with pytest.raises(HTTPException) as exc:
        accept_driver_assignment(db_session, other, assignment.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver assignment not found"

    db_session.refresh(assignment)
    assert assignment.status == "offered"  # untouched


def test_decline_other_store_404(db_session: Session, make_store) -> None:
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
        status="offered",
    )

    store_b = make_store("store-b")
    other = _driver(db_session, store_b)
    make_driver_profile(db_session, user=other, store=store_b)

    with pytest.raises(HTTPException) as exc:
        decline_driver_assignment(db_session, other, assignment.id)
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver assignment not found"


# --------------------------------------------------------------------- #
# I. Missing driver profile
# --------------------------------------------------------------------- #


def test_accept_driver_without_profile_404(
    db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)  # no profile provisioned
    with pytest.raises(HTTPException) as exc:
        accept_driver_assignment(db_session, user, uuid.uuid4())
    assert exc.value.status_code == 404
    assert exc.value.detail == "Driver profile not found"


# --------------------------------------------------------------------- #
# J. No domain side effects
# --------------------------------------------------------------------- #


def test_accept_no_side_effects(db_session: Session, setup) -> None:
    _store, user, _profile, assignment = setup("offered")
    order = db_session.get(Order, assignment.order_id)
    order_status_before = order.status

    accept_driver_assignment(db_session, user, assignment.id)

    db_session.refresh(order)
    assert order.status == order_status_before
    # No operational-state row materialized as a side effect.
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(DriverDeliveryOperationalState)
            .where(
                DriverDeliveryOperationalState.assignment_id
                == assignment.id
            )
        )
        == 0
    )


def test_decline_no_side_effects(db_session: Session, setup) -> None:
    _store, user, _profile, assignment = setup("offered")
    order = db_session.get(Order, assignment.order_id)
    order_status_before = order.status

    decline_driver_assignment(db_session, user, assignment.id)

    db_session.refresh(order)
    assert order.status == order_status_before
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(DriverDeliveryOperationalState)
            .where(
                DriverDeliveryOperationalState.assignment_id
                == assignment.id
            )
        )
        == 0
    )
    # assigned_at / canceled_at / completed_at remain untouched by a decline.
    db_session.refresh(assignment)
    assert assignment.canceled_at is None
    assert assignment.completed_at is None
