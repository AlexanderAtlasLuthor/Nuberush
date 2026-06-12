"""Dr.1.1.G.2 — DriverDeliveryOperationalState model / DB constraint tests.

Exercises the `driver_delivery_operational_states` table directly: creation
and server-side defaults, the 1:1 anchor on an assignment, the inverse
relationships, the UNIQUE(assignment_id) and the state CHECK (all 14 valid
values accepted, an invalid value rejected), FK integrity on every anchor,
ON DELETE behaviour (assignment CASCADE, driver_profile RESTRICT), the
updated_at trigger, and domain-separation guards proving G.2 did not bleed
operational state into OrderStatus / OrderDriverAssignmentStatus / Order.

This is a MODEL/DB suite only — no service, schema, route, or transition
logic is touched.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from sqlalchemy import delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import DriverDeliveryOperationalState
from app.db.models import DriverDeliveryOperationalStateValue
from app.db.models import Order
from app.db.models import OrderDriverAssignment
from app.db.models import OrderDriverAssignmentStatus
from app.db.models import OrderStatus
from app.db.models import Store
from app.db.models import UserRole
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
    def _create(name: str = "DDOS-Store") -> Store:
        store = Store(name=name, code=f"ddos-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_assignment(
    db_session: Session, make_store
) -> Callable[..., OrderDriverAssignment]:
    """A fresh store + order + driver profile + assignment, all same-store."""

    def _create() -> OrderDriverAssignment:
        store = make_store()
        order = make_order(db_session, store=store)
        user = central_make_user(
            db_session, role=UserRole.driver, store_id=store.id
        )
        profile = make_driver_profile(db_session, user=user, store=store)
        return make_order_driver_assignment(
            db_session,
            order=order,
            driver_profile=profile,
            store=store,
        )

    return _create


# --------------------------------------------------------------------- #
# A. Basic creation + server-side defaults
# --------------------------------------------------------------------- #


def test_basic_creation(db_session: Session, make_assignment) -> None:
    assignment = make_assignment()
    state = make_driver_delivery_operational_state(
        db_session, assignment=assignment
    )

    assert state.id is not None
    assert state.assignment_id == assignment.id
    assert state.order_id == assignment.order_id
    assert state.driver_profile_id == assignment.driver_profile_id
    assert state.store_id == assignment.store_id
    assert state.state == "not_started"
    assert state.state_started_at is not None
    assert state.last_transition_at is not None
    assert state.created_at is not None
    assert state.updated_at is not None


# --------------------------------------------------------------------- #
# B. 1:1 assignment -> operational_state
# --------------------------------------------------------------------- #


def test_one_to_one_relationship(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    state = make_driver_delivery_operational_state(
        db_session, assignment=assignment
    )

    db_session.refresh(assignment)
    assert assignment.operational_state is not None
    assert assignment.operational_state.id == state.id
    # The mapped relationship is scalar (1:1), not a collection.
    assert (
        OrderDriverAssignment.operational_state.property.uselist is False
    )


# --------------------------------------------------------------------- #
# C. Inverse relationships from order / driver_profile / store
# --------------------------------------------------------------------- #


def test_inverse_relationships(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    state = make_driver_delivery_operational_state(
        db_session, assignment=assignment
    )

    order = db_session.get(Order, assignment.order_id)
    db_session.refresh(order)
    assert state.id in {s.id for s in order.delivery_operational_states}

    profile = assignment.driver_profile
    db_session.refresh(profile)
    assert state.id in {s.id for s in profile.delivery_operational_states}

    store = assignment.store
    db_session.refresh(store)
    assert state.id in {s.id for s in store.delivery_operational_states}


# --------------------------------------------------------------------- #
# D. UNIQUE(assignment_id)
# --------------------------------------------------------------------- #


def test_unique_assignment_id(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    make_driver_delivery_operational_state(
        db_session, assignment=assignment
    )

    with pytest.raises(IntegrityError):
        db_session.add(
            DriverDeliveryOperationalState(
                assignment_id=assignment.id,
                order_id=assignment.order_id,
                driver_profile_id=assignment.driver_profile_id,
                store_id=assignment.store_id,
                state="not_started",
            )
        )
        db_session.commit()
    db_session.rollback()


# --------------------------------------------------------------------- #
# E. state CHECK constraint
# --------------------------------------------------------------------- #


def test_invalid_state_rejected(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    with pytest.raises(IntegrityError):
        db_session.add(
            DriverDeliveryOperationalState(
                assignment_id=assignment.id,
                order_id=assignment.order_id,
                driver_profile_id=assignment.driver_profile_id,
                store_id=assignment.store_id,
                state="teleported_to_customer",
            )
        )
        db_session.commit()
    db_session.rollback()


# --------------------------------------------------------------------- #
# F. All 14 valid states persist
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "state_value", [v.value for v in DriverDeliveryOperationalStateValue]
)
def test_all_valid_states_persist(
    db_session: Session, make_assignment, state_value: str
) -> None:
    assignment = make_assignment()
    state = make_driver_delivery_operational_state(
        db_session, assignment=assignment, state=state_value
    )
    assert state.state == state_value


def test_enum_has_exactly_14_values() -> None:
    values = [v.value for v in DriverDeliveryOperationalStateValue]
    assert values == [
        "not_started",
        "en_route_to_store",
        "arrived_at_store",
        "pickup_started",
        "picked_up",
        "en_route_to_customer",
        "arrived_at_customer",
        "id_verification_pending",
        "id_verified",
        "delivery_completed",
        "delivery_failed",
        "returning_to_store",
        "returned_to_store",
        "canceled",
    ]


# --------------------------------------------------------------------- #
# G. FK integrity on every anchor
# --------------------------------------------------------------------- #


def test_invalid_assignment_fk_rejected(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    with pytest.raises(IntegrityError):
        db_session.add(
            DriverDeliveryOperationalState(
                assignment_id=uuid.uuid4(),
                order_id=assignment.order_id,
                driver_profile_id=assignment.driver_profile_id,
                store_id=assignment.store_id,
                state="not_started",
            )
        )
        db_session.commit()
    db_session.rollback()


def test_invalid_order_fk_rejected(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    with pytest.raises(IntegrityError):
        db_session.add(
            DriverDeliveryOperationalState(
                assignment_id=assignment.id,
                order_id=uuid.uuid4(),
                driver_profile_id=assignment.driver_profile_id,
                store_id=assignment.store_id,
                state="not_started",
            )
        )
        db_session.commit()
    db_session.rollback()


def test_invalid_driver_profile_fk_rejected(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    with pytest.raises(IntegrityError):
        db_session.add(
            DriverDeliveryOperationalState(
                assignment_id=assignment.id,
                order_id=assignment.order_id,
                driver_profile_id=uuid.uuid4(),
                store_id=assignment.store_id,
                state="not_started",
            )
        )
        db_session.commit()
    db_session.rollback()


def test_invalid_store_fk_rejected(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    with pytest.raises(IntegrityError):
        db_session.add(
            DriverDeliveryOperationalState(
                assignment_id=assignment.id,
                order_id=assignment.order_id,
                driver_profile_id=assignment.driver_profile_id,
                store_id=uuid.uuid4(),
                state="not_started",
            )
        )
        db_session.commit()
    db_session.rollback()


# --------------------------------------------------------------------- #
# H. ON DELETE behaviour
# --------------------------------------------------------------------- #


def test_assignment_delete_cascades_state(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    state = make_driver_delivery_operational_state(
        db_session, assignment=assignment
    )
    state_id = state.id

    # Delete the assignment at the SQL layer so the DB-level ON DELETE CASCADE
    # is what removes the state — not an ORM unit-of-work nullify (which would
    # try to NULL the NOT NULL assignment_id instead).
    db_session.execute(
        delete(OrderDriverAssignment).where(
            OrderDriverAssignment.id == assignment.id
        )
    )
    db_session.commit()
    db_session.expire_all()

    assert (
        db_session.get(DriverDeliveryOperationalState, state_id) is None
    )


def test_driver_profile_delete_restricted_by_state(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    make_driver_delivery_operational_state(
        db_session, assignment=assignment
    )
    profile = assignment.driver_profile

    # The driver_profile FK is ON DELETE RESTRICT: a profile that still has
    # operational-state rows cannot be hard-deleted. (The assignment's own
    # RESTRICT FK to the profile also guards this, which is fine — both
    # express "preserve driver history".)
    with pytest.raises(IntegrityError):
        db_session.delete(profile)
        db_session.commit()
    db_session.rollback()


# --------------------------------------------------------------------- #
# I. updated_at trigger; last_transition_at does NOT auto-advance
# --------------------------------------------------------------------- #


def test_updated_at_trigger_and_last_transition_static(
    db_session: Session, make_assignment
) -> None:
    assignment = make_assignment()
    state = make_driver_delivery_operational_state(
        db_session, assignment=assignment
    )

    original_updated_at = state.updated_at
    original_last_transition_at = state.last_transition_at

    # A bare state change must NOT itself advance last_transition_at — there
    # is no transition service in G.2; only the shared updated_at trigger
    # fires.
    state.state = DriverDeliveryOperationalStateValue.en_route_to_store.value
    db_session.commit()
    db_session.refresh(state)

    assert state.state == "en_route_to_store"
    assert state.updated_at >= original_updated_at
    assert state.last_transition_at == original_last_transition_at


# --------------------------------------------------------------------- #
# J. Domain separation guards
# --------------------------------------------------------------------- #


def test_order_status_vocabulary_unchanged() -> None:
    assert [s.value for s in OrderStatus] == [
        "pending",
        "accepted",
        "preparing",
        "ready",
        "out_for_delivery",
        "delivered",
        "canceled",
        "returned",
    ]


def test_assignment_status_vocabulary_unchanged() -> None:
    assert [s.value for s in OrderDriverAssignmentStatus] == [
        "offered",
        "accepted",
        "declined",
        "expired",
        "assigned",
        "started",
        "completed",
        "canceled",
    ]


def test_order_has_no_driver_operational_columns() -> None:
    columns = set(Order.__table__.columns.keys())
    for forbidden in (
        "assigned_driver_id",
        "driver_id",
        "delivery_state",
        "driver_operational_state",
        "pickup_started_at",
        "picked_up_at",
        "driver_arrived_at",
    ):
        assert forbidden not in columns
