"""Dr.1.2.E — complete-delivery service tests.

Exercises `complete_delivery_driver_assignment` directly: the happy path that
advances id_verified -> delivery_completed, closes the assignment -> completed,
and promotes Order.status -> delivered via the orders authority bridge; the
idempotency rule; the compliance gate (verification pass + proof); the
422/409/404 guard matrix; and the boundary that the commercial change + audit
come from orders authority while the driver never writes Order.status.

SERVICE/DB suite only — no route layer.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DriverDeliveryOperationalState
from app.db.models import DriverDeliveryOperationalStateValue as State
from app.db.models import DriverDeliveryProof
from app.db.models import DriverDeliveryProofMethod
from app.db.models import DriverDeliveryVerification
from app.db.models import DriverDeliveryVerificationMethod
from app.db.models import DriverDeliveryVerificationOutcome
from app.db.models import Order
from app.db.models import OrderAuditLog
from app.db.models import OrderStatus
from app.db.models import Store
from app.db.models import UserRole
from app.services.driver import complete_delivery_driver_assignment
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_delivery_operational_state
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "CDS-Store") -> Store:
        store = Store(name=name, code=f"cds-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


def _add_verification(db_session, assignment, outcome="pass"):
    row = DriverDeliveryVerification(
        assignment_id=assignment.id,
        order_id=assignment.order_id,
        driver_profile_id=assignment.driver_profile_id,
        store_id=assignment.store_id,
        outcome=outcome,
        method=DriverDeliveryVerificationMethod.manual_checklist.value,
    )
    db_session.add(row)
    db_session.commit()
    return row


def _add_proof(db_session, assignment):
    row = DriverDeliveryProof(
        assignment_id=assignment.id,
        order_id=assignment.order_id,
        driver_profile_id=assignment.driver_profile_id,
        store_id=assignment.store_id,
        method=DriverDeliveryProofMethod.manual_checklist.value,
        recipient_present_confirmed=True,
        handoff_confirmed=True,
        restricted_not_left_unattended=True,
    )
    db_session.add(row)
    db_session.commit()
    return row


@pytest.fixture
def make_setup(db_session: Session, make_store):
    """A started assignment + operational state + (optional) verification/proof
    + order at a chosen commercial status. Returns (assignment, driver_user)."""

    def _create(
        *,
        state: str | None = State.id_verified.value,
        assignment_status: str = "started",
        order_status: str = "ready",
        with_verification_pass: bool = True,
        with_proof: bool = True,
    ):
        store = make_store()
        order = make_order(db_session, store=store, status=order_status)
        user = central_make_user(
            db_session, role=UserRole.driver, store_id=store.id
        )
        profile = make_driver_profile(db_session, user=user, store=store)
        assignment = make_order_driver_assignment(
            db_session,
            order=order,
            driver_profile=profile,
            store=store,
            status=assignment_status,
        )
        if state is not None:
            make_driver_delivery_operational_state(
                db_session, assignment=assignment, state=state
            )
        if with_verification_pass:
            _add_verification(db_session, assignment, outcome="pass")
        if with_proof:
            _add_proof(db_session, assignment)
        return assignment, user

    return _create


def _state(db_session, assignment_id) -> str:
    db_session.expire_all()
    return db_session.scalar(
        select(DriverDeliveryOperationalState).where(
            DriverDeliveryOperationalState.assignment_id == assignment_id
        )
    ).state


# --------------------------------------------------------------------- #
# A. Happy paths
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("order_status", ["ready", "out_for_delivery"])
def test_happy_path(
    db_session: Session, make_setup, order_status: str
) -> None:
    assignment, user = make_setup(order_status=order_status)
    out = complete_delivery_driver_assignment(
        db_session, user, assignment.id
    )
    assert out.state == "delivery_completed"

    db_session.expire_all()
    refreshed = db_session.get(
        type(assignment), assignment.id
    )
    order = db_session.get(Order, assignment.order_id)
    assert refreshed.status == "completed"
    assert refreshed.completed_at is not None
    assert order.status == OrderStatus.delivered
    assert order.delivered_at is not None


def test_audit_from_orders_authority(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    complete_delivery_driver_assignment(db_session, user, assignment.id)
    db_session.expire_all()
    audits = list(
        db_session.scalars(
            select(OrderAuditLog).where(
                OrderAuditLog.order_id == assignment.order_id
            )
        )
    )
    delivered = [a for a in audits if a.new_status == OrderStatus.delivered]
    assert len(delivered) == 1
    assert delivered[0].performed_by_user_id == user.id


# --------------------------------------------------------------------- #
# B. Idempotency
# --------------------------------------------------------------------- #


def test_repeated_complete_idempotent(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    complete_delivery_driver_assignment(db_session, user, assignment.id)

    audits_after_first = db_session.scalar(
        select(func.count())
        .select_from(OrderAuditLog)
        .where(
            OrderAuditLog.order_id == assignment.order_id,
            OrderAuditLog.new_status == OrderStatus.delivered,
        )
    )

    out = complete_delivery_driver_assignment(db_session, user, assignment.id)
    assert out.state == "delivery_completed"

    audits_after_second = db_session.scalar(
        select(func.count())
        .select_from(OrderAuditLog)
        .where(
            OrderAuditLog.order_id == assignment.order_id,
            OrderAuditLog.new_status == OrderStatus.delivered,
        )
    )
    assert audits_after_second == audits_after_first == 1
    assert _state(db_session, assignment.id) == "delivery_completed"


# --------------------------------------------------------------------- #
# C. Compliance gate
# --------------------------------------------------------------------- #


def test_id_verified_without_proof_is_422(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(with_proof=False)
    with pytest.raises(HTTPException) as exc:
        complete_delivery_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 422


def test_id_verified_without_verification_pass_is_422(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(with_verification_pass=False)
    with pytest.raises(HTTPException) as exc:
        complete_delivery_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 422


def test_arrived_at_customer_is_422(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(
        state=State.arrived_at_customer.value,
        with_verification_pass=False,
        with_proof=False,
    )
    with pytest.raises(HTTPException) as exc:
        complete_delivery_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 422


def test_returning_to_store_is_409(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(
        state=State.returning_to_store.value,
        with_verification_pass=False,
        with_proof=False,
    )
    with pytest.raises(HTTPException) as exc:
        complete_delivery_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 409


@pytest.mark.parametrize(
    "state",
    [
        State.delivery_failed.value,
        State.returned_to_store.value,
        State.canceled.value,
    ],
)
def test_terminal_state_is_422(
    db_session: Session, make_setup, state: str
) -> None:
    assignment, user = make_setup(
        state=state, with_verification_pass=False, with_proof=False
    )
    with pytest.raises(HTTPException) as exc:
        complete_delivery_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 422


def test_no_operational_state_row_is_422(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(
        state=None, with_verification_pass=False, with_proof=False
    )
    with pytest.raises(HTTPException) as exc:
        complete_delivery_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 422


def test_assignment_not_started_is_422(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(assignment_status="accepted")
    with pytest.raises(HTTPException) as exc:
        complete_delivery_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 422


# --------------------------------------------------------------------- #
# D. Order not commercially completable
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("order_status", ["pending", "accepted", "preparing"])
def test_order_not_completable_is_409(
    db_session: Session, make_setup, order_status: str
) -> None:
    assignment, user = make_setup(order_status=order_status)
    with pytest.raises(HTTPException) as exc:
        complete_delivery_driver_assignment(db_session, user, assignment.id)
    assert exc.value.status_code == 409
    # The commercial status must be untouched on rejection.
    db_session.expire_all()
    order = db_session.get(Order, assignment.order_id)
    assert order.status.value == order_status
    assert _state(db_session, assignment.id) == "id_verified"


# --------------------------------------------------------------------- #
# E. Anti-enumeration
# --------------------------------------------------------------------- #


def test_foreign_assignment_is_404(
    db_session: Session, make_setup, make_store
) -> None:
    assignment, _owner = make_setup()
    other_store = make_store(name="CDS-Other")
    other = central_make_user(
        db_session, role=UserRole.driver, store_id=other_store.id
    )
    make_driver_profile(db_session, user=other, store=other_store)
    with pytest.raises(HTTPException) as exc:
        complete_delivery_driver_assignment(db_session, other, assignment.id)
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
        complete_delivery_driver_assignment(db_session, user, uuid.uuid4())
    assert exc.value.status_code == 404
