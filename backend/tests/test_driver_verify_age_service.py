"""Dr.1.2.C — verify-age service tests.

Exercises `verify_age_driver_assignment` directly: the `pass` transition
arrived_at_customer -> id_verified with a redaction-safe verification row,
the fail / manual_review record-only behaviour (state stays
arrived_at_customer), the id_verified idempotency / 409 rules, the
422/409/404 guard matrix, and the domain boundaries proving verify-age never
mutates Order.status, Order.age_verified_at, or inventory.

This is a SERVICE/DB suite only — no route layer is exercised here.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DriverDeliveryOperationalStateValue as State
from app.db.models import DriverDeliveryVerification
from app.db.models import InventoryItem
from app.db.models import Order
from app.db.models import OrderDriverAssignment
from app.db.models import OrderStatus
from app.db.models import Store
from app.db.models import UserRole
from app.schemas.driver import DriverVerifyAgeRequest
from app.services.driver import verify_age_driver_assignment
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_delivery_operational_state
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


# --------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "VAS-Store") -> Store:
        store = Store(name=name, code=f"vas-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_setup(db_session: Session, make_store):
    """A started assignment + operational state at a chosen state, plus the
    owning driver user. Returns (assignment, driver_user)."""

    def _create(state: str = State.arrived_at_customer.value):
        store = make_store()
        order = make_order(db_session, store=store)
        user = central_make_user(
            db_session, role=UserRole.driver, store_id=store.id
        )
        profile = make_driver_profile(db_session, user=user, store=store)
        assignment = make_order_driver_assignment(
            db_session,
            order=order,
            driver_profile=profile,
            store=store,
            status="started",
        )
        make_driver_delivery_operational_state(
            db_session, assignment=assignment, state=state
        )
        return assignment, user

    return _create


def _req(outcome: str = "pass", **overrides) -> DriverVerifyAgeRequest:
    data = {"outcome": outcome}
    data.update(overrides)
    return DriverVerifyAgeRequest(**data)


def _count_verifications(db_session: Session, assignment_id) -> int:
    return db_session.scalar(
        select(func.count())
        .select_from(DriverDeliveryVerification)
        .where(DriverDeliveryVerification.assignment_id == assignment_id)
    )


def _operational_state(db_session: Session, assignment_id) -> str:
    from app.db.models import DriverDeliveryOperationalState

    db_session.expire_all()
    row = db_session.scalar(
        select(DriverDeliveryOperationalState).where(
            DriverDeliveryOperationalState.assignment_id == assignment_id
        )
    )
    return row.state


# --------------------------------------------------------------------- #
# A. pass from arrived_at_customer
# --------------------------------------------------------------------- #


def test_pass_creates_verification_with_anchors(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    out = verify_age_driver_assignment(
        db_session, user, assignment.id, _req("pass")
    )

    assert out.assignment_id == assignment.id
    assert out.order_id == assignment.order_id
    assert out.driver_profile_id == assignment.driver_profile_id
    assert out.store_id == assignment.store_id
    assert out.outcome == "pass"
    assert out.failure_reason_code is None


def test_pass_sets_performed_by_and_method(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    out = verify_age_driver_assignment(
        db_session, user, assignment.id, _req("pass")
    )
    assert out.performed_by_user_id == user.id
    assert out.method == "manual_checklist"


def test_pass_transitions_state_to_id_verified(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    verify_age_driver_assignment(
        db_session, user, assignment.id, _req("pass")
    )
    assert _operational_state(db_session, assignment.id) == "id_verified"


def test_pass_advances_state_timestamps(
    db_session: Session, make_setup
) -> None:
    from app.db.models import DriverDeliveryOperationalState

    assignment, user = make_setup()
    before = db_session.scalar(
        select(DriverDeliveryOperationalState).where(
            DriverDeliveryOperationalState.assignment_id == assignment.id
        )
    )
    original_started = before.state_started_at
    verify_age_driver_assignment(
        db_session, user, assignment.id, _req("pass")
    )
    db_session.expire_all()
    after = db_session.scalar(
        select(DriverDeliveryOperationalState).where(
            DriverDeliveryOperationalState.assignment_id == assignment.id
        )
    )
    assert after.state == "id_verified"
    assert after.state_started_at >= original_started
    assert after.last_transition_at >= original_started


# --------------------------------------------------------------------- #
# B. fail / manual_review record-only
# --------------------------------------------------------------------- #


def test_fail_records_and_keeps_state(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    out = verify_age_driver_assignment(
        db_session,
        user,
        assignment.id,
        _req("fail", failure_reason_code="customer_underage"),
    )
    assert out.outcome == "fail"
    assert out.failure_reason_code == "customer_underage"
    assert _count_verifications(db_session, assignment.id) == 1
    assert (
        _operational_state(db_session, assignment.id)
        == "arrived_at_customer"
    )


def test_manual_review_records_and_keeps_state(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    out = verify_age_driver_assignment(
        db_session, user, assignment.id, _req("manual_review")
    )
    assert out.outcome == "manual_review"
    assert (
        _operational_state(db_session, assignment.id)
        == "arrived_at_customer"
    )


def test_fail_requires_failure_reason_code() -> None:
    # The schema rejects a fail without a reason before the service runs.
    with pytest.raises(Exception):
        _req("fail")


# --------------------------------------------------------------------- #
# C. id_verified idempotency / conflict
# --------------------------------------------------------------------- #


def test_pass_idempotent_from_id_verified_no_duplicate_row(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    verify_age_driver_assignment(
        db_session, user, assignment.id, _req("pass")
    )
    assert _count_verifications(db_session, assignment.id) == 1

    # Re-issue pass; state already id_verified -> idempotent, no new row.
    out = verify_age_driver_assignment(
        db_session, user, assignment.id, _req("pass")
    )
    assert out.outcome == "pass"
    assert _count_verifications(db_session, assignment.id) == 1
    assert _operational_state(db_session, assignment.id) == "id_verified"


def test_fail_from_id_verified_conflicts(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    verify_age_driver_assignment(
        db_session, user, assignment.id, _req("pass")
    )
    with pytest.raises(HTTPException) as exc:
        verify_age_driver_assignment(
            db_session,
            user,
            assignment.id,
            _req("fail", failure_reason_code="customer_underage"),
        )
    assert exc.value.status_code == 409
    assert _count_verifications(db_session, assignment.id) == 1


def test_manual_review_from_id_verified_conflicts(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    verify_age_driver_assignment(
        db_session, user, assignment.id, _req("pass")
    )
    with pytest.raises(HTTPException) as exc:
        verify_age_driver_assignment(
            db_session, user, assignment.id, _req("manual_review")
        )
    assert exc.value.status_code == 409


# --------------------------------------------------------------------- #
# D. Guard matrix
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "state",
    [
        State.not_started.value,
        State.en_route_to_store.value,
        State.arrived_at_store.value,
        State.pickup_started.value,
        State.picked_up.value,
        State.en_route_to_customer.value,
    ],
)
def test_before_arrived_at_customer_is_422(
    db_session: Session, make_setup, state: str
) -> None:
    assignment, user = make_setup(state=state)
    with pytest.raises(HTTPException) as exc:
        verify_age_driver_assignment(
            db_session, user, assignment.id, _req("pass")
        )
    assert exc.value.status_code == 422
    assert _count_verifications(db_session, assignment.id) == 0


@pytest.mark.parametrize(
    "state",
    [
        State.delivery_completed.value,
        State.delivery_failed.value,
        State.returned_to_store.value,
        State.canceled.value,
    ],
)
def test_terminal_state_is_422(
    db_session: Session, make_setup, state: str
) -> None:
    assignment, user = make_setup(state=state)
    with pytest.raises(HTTPException) as exc:
        verify_age_driver_assignment(
            db_session, user, assignment.id, _req("pass")
        )
    assert exc.value.status_code == 422


@pytest.mark.parametrize(
    "state",
    [
        State.id_verification_pending.value,
        State.returning_to_store.value,
    ],
)
def test_later_nonterminal_state_is_409(
    db_session: Session, make_setup, state: str
) -> None:
    assignment, user = make_setup(state=state)
    with pytest.raises(HTTPException) as exc:
        verify_age_driver_assignment(
            db_session, user, assignment.id, _req("pass")
        )
    assert exc.value.status_code == 409


def test_assignment_not_started_is_422(
    db_session: Session, make_store
) -> None:
    store = make_store()
    order = make_order(db_session, store=store)
    user = central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )
    profile = make_driver_profile(db_session, user=user, store=store)
    assignment = make_order_driver_assignment(
        db_session,
        order=order,
        driver_profile=profile,
        store=store,
        status="accepted",
    )
    make_driver_delivery_operational_state(
        db_session,
        assignment=assignment,
        state=State.arrived_at_customer.value,
    )
    with pytest.raises(HTTPException) as exc:
        verify_age_driver_assignment(
            db_session, user, assignment.id, _req("pass")
        )
    assert exc.value.status_code == 422


def test_no_operational_state_row_is_422(
    db_session: Session, make_store
) -> None:
    store = make_store()
    order = make_order(db_session, store=store)
    user = central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )
    profile = make_driver_profile(db_session, user=user, store=store)
    assignment = make_order_driver_assignment(
        db_session,
        order=order,
        driver_profile=profile,
        store=store,
        status="started",
    )
    # No operational-state row materialized.
    with pytest.raises(HTTPException) as exc:
        verify_age_driver_assignment(
            db_session, user, assignment.id, _req("pass")
        )
    assert exc.value.status_code == 422
    assert _count_verifications(db_session, assignment.id) == 0


def test_foreign_assignment_is_404(
    db_session: Session, make_setup, make_store
) -> None:
    assignment, _owner = make_setup()
    # A different driver in a different store.
    other_store = make_store(name="VAS-Other")
    other_user = central_make_user(
        db_session, role=UserRole.driver, store_id=other_store.id
    )
    make_driver_profile(db_session, user=other_user, store=other_store)
    with pytest.raises(HTTPException) as exc:
        verify_age_driver_assignment(
            db_session, other_user, assignment.id, _req("pass")
        )
    assert exc.value.status_code == 404


def test_missing_assignment_is_404(
    db_session: Session, make_store
) -> None:
    store = make_store()
    user = central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )
    make_driver_profile(db_session, user=user, store=store)
    with pytest.raises(HTTPException) as exc:
        verify_age_driver_assignment(
            db_session, user, uuid.uuid4(), _req("pass")
        )
    assert exc.value.status_code == 404


# --------------------------------------------------------------------- #
# E. Domain boundary guards
# --------------------------------------------------------------------- #


def test_order_status_and_age_verified_at_unchanged(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    order_before = db_session.get(Order, assignment.order_id)
    status_before = order_before.status
    age_verified_before = order_before.age_verified_at

    verify_age_driver_assignment(
        db_session, user, assignment.id, _req("pass")
    )

    db_session.expire_all()
    order_after = db_session.get(Order, assignment.order_id)
    assert order_after.status == status_before
    assert order_after.status == OrderStatus.pending
    assert order_after.age_verified_at == age_verified_before
    assert order_after.age_verified_at is None


def test_inventory_untouched(db_session: Session, make_setup) -> None:
    assignment, user = make_setup()
    inv_count_before = db_session.scalar(
        select(func.count()).select_from(InventoryItem)
    )
    verify_age_driver_assignment(
        db_session, user, assignment.id, _req("pass")
    )
    db_session.expire_all()
    inv_count_after = db_session.scalar(
        select(func.count()).select_from(InventoryItem)
    )
    assert inv_count_after == inv_count_before
