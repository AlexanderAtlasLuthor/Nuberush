"""Dr.1.2.D — proof-of-delivery service tests.

Exercises `submit_proof_driver_assignment` directly: the id_verified happy path
that records a redaction-safe `DriverDeliveryProof`, the record-only guarantee
(operational state stays id_verified), the idempotency-by-existence rule, the
422/409/404 guard matrix, and the domain boundaries proving proof never mutates
Order.status, Order.age_verified_at, or inventory.

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

from app.db.models import DriverDeliveryOperationalState
from app.db.models import DriverDeliveryOperationalStateValue as State
from app.db.models import DriverDeliveryProof
from app.db.models import InventoryItem
from app.db.models import Order
from app.db.models import OrderStatus
from app.db.models import Store
from app.db.models import UserRole
from app.schemas.driver import DriverProofSubmitRequest
from app.services.driver import submit_proof_driver_assignment
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_delivery_operational_state
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "PRS-Store") -> Store:
        store = Store(name=name, code=f"prs-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_setup(db_session: Session, make_store):
    """A started assignment + operational state at a chosen state, plus the
    owning driver user. Returns (assignment, driver_user)."""

    def _create(
        state: str | None = State.id_verified.value,
        status: str = "started",
    ):
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
            status=status,
        )
        if state is not None:
            make_driver_delivery_operational_state(
                db_session, assignment=assignment, state=state
            )
        return assignment, user

    return _create


def _req(**overrides) -> DriverProofSubmitRequest:
    data = {
        "recipient_present_confirmed": True,
        "handoff_confirmed": True,
        "restricted_not_left_unattended": True,
    }
    data.update(overrides)
    return DriverProofSubmitRequest(**data)


def _count_proofs(db_session: Session, assignment_id) -> int:
    db_session.expire_all()
    return db_session.scalar(
        select(func.count())
        .select_from(DriverDeliveryProof)
        .where(DriverDeliveryProof.assignment_id == assignment_id)
    )


def _state(db_session: Session, assignment_id) -> str:
    db_session.expire_all()
    return db_session.scalar(
        select(DriverDeliveryOperationalState).where(
            DriverDeliveryOperationalState.assignment_id == assignment_id
        )
    ).state


# --------------------------------------------------------------------- #
# A. id_verified happy path
# --------------------------------------------------------------------- #


def test_proof_creates_row_with_anchors(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    out = submit_proof_driver_assignment(
        db_session, user, assignment.id, _req()
    )
    assert out.assignment_id == assignment.id
    assert out.order_id == assignment.order_id
    assert out.driver_profile_id == assignment.driver_profile_id
    assert out.store_id == assignment.store_id


def test_proof_sets_submitted_by_and_method(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    out = submit_proof_driver_assignment(
        db_session, user, assignment.id, _req(note="left with recipient")
    )
    assert out.submitted_by_user_id == user.id
    assert out.method == "manual_checklist"
    assert out.note == "left with recipient"


def test_proof_persists_all_three_confirmations(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    out = submit_proof_driver_assignment(
        db_session, user, assignment.id, _req()
    )
    assert out.recipient_present_confirmed is True
    assert out.handoff_confirmed is True
    assert out.restricted_not_left_unattended is True


def test_proof_keeps_state_id_verified(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    submit_proof_driver_assignment(db_session, user, assignment.id, _req())
    assert _state(db_session, assignment.id) == "id_verified"


# --------------------------------------------------------------------- #
# B. Idempotency by existence
# --------------------------------------------------------------------- #


def test_repeated_proof_does_not_duplicate_row(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    first = submit_proof_driver_assignment(
        db_session, user, assignment.id, _req()
    )
    assert _count_proofs(db_session, assignment.id) == 1
    second = submit_proof_driver_assignment(
        db_session, user, assignment.id, _req(note="changed note")
    )
    assert _count_proofs(db_session, assignment.id) == 1
    # Idempotent: returns the existing proof unchanged.
    assert second.id == first.id


def test_repeated_proof_does_not_rewrite_timestamps(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    first = submit_proof_driver_assignment(
        db_session, user, assignment.id, _req()
    )
    second = submit_proof_driver_assignment(
        db_session, user, assignment.id, _req()
    )
    assert second.created_at == first.created_at
    assert second.updated_at == first.updated_at


# --------------------------------------------------------------------- #
# C. Guard matrix
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
        State.arrived_at_customer.value,
        State.id_verification_pending.value,
    ],
)
def test_before_id_verified_is_422(
    db_session: Session, make_setup, state: str
) -> None:
    assignment, user = make_setup(state=state)
    with pytest.raises(HTTPException) as exc:
        submit_proof_driver_assignment(
            db_session, user, assignment.id, _req()
        )
    assert exc.value.status_code == 422
    assert _count_proofs(db_session, assignment.id) == 0


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
        submit_proof_driver_assignment(
            db_session, user, assignment.id, _req()
        )
    assert exc.value.status_code == 422


def test_returning_to_store_is_409(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=State.returning_to_store.value)
    with pytest.raises(HTTPException) as exc:
        submit_proof_driver_assignment(
            db_session, user, assignment.id, _req()
        )
    assert exc.value.status_code == 409


def test_no_operational_state_row_is_422(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=None)
    with pytest.raises(HTTPException) as exc:
        submit_proof_driver_assignment(
            db_session, user, assignment.id, _req()
        )
    assert exc.value.status_code == 422
    assert _count_proofs(db_session, assignment.id) == 0


def test_assignment_not_started_is_422(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(status="accepted")
    with pytest.raises(HTTPException) as exc:
        submit_proof_driver_assignment(
            db_session, user, assignment.id, _req()
        )
    assert exc.value.status_code == 422


def test_foreign_assignment_is_404(
    db_session: Session, make_setup, make_store
) -> None:
    assignment, _owner = make_setup()
    other_store = make_store(name="PRS-Other")
    other = central_make_user(
        db_session, role=UserRole.driver, store_id=other_store.id
    )
    make_driver_profile(db_session, user=other, store=other_store)
    with pytest.raises(HTTPException) as exc:
        submit_proof_driver_assignment(
            db_session, other, assignment.id, _req()
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
        submit_proof_driver_assignment(
            db_session, user, uuid.uuid4(), _req()
        )
    assert exc.value.status_code == 404


# --------------------------------------------------------------------- #
# D. Domain boundary guards
# --------------------------------------------------------------------- #


def test_order_status_and_age_verified_at_unchanged(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    order_before = db_session.get(Order, assignment.order_id)
    status_before = order_before.status
    age_before = order_before.age_verified_at

    submit_proof_driver_assignment(db_session, user, assignment.id, _req())

    db_session.expire_all()
    order_after = db_session.get(Order, assignment.order_id)
    assert order_after.status == status_before
    assert order_after.status == OrderStatus.pending
    assert order_after.age_verified_at == age_before
    assert order_after.age_verified_at is None


def test_inventory_untouched(db_session: Session, make_setup) -> None:
    assignment, user = make_setup()
    before = db_session.scalar(
        select(func.count()).select_from(InventoryItem)
    )
    submit_proof_driver_assignment(db_session, user, assignment.id, _req())
    db_session.expire_all()
    after = db_session.scalar(
        select(func.count()).select_from(InventoryItem)
    )
    assert after == before
