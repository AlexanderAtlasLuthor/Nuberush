"""Dr.1.2.F — failed-delivery service tests.

Exercises `fail_delivery_driver_assignment` directly: the operational-only
happy path that inserts a `DriverDeliveryFailure` and advances the operational
state -> delivery_failed (assignment stays started, Order.status / inventory /
OrderAuditLog all untouched); the per-reason idempotency rule; the 422/409/404
guard matrix; and the boundary that the driver layer never mutates Order.status
or inventory.

SERVICE/DB suite only — no route layer.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pydantic
import pytest
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DriverDeliveryFailure
from app.db.models import DriverDeliveryFailureReason
from app.db.models import DriverDeliveryOperationalState
from app.db.models import DriverDeliveryOperationalStateValue as State
from app.db.models import InventoryLog
from app.db.models import Order
from app.db.models import OrderAuditLog
from app.db.models import OrderStatus
from app.db.models import Store
from app.db.models import UserRole
from app.schemas.driver import DriverFailDeliveryRequest
from app.services.driver import fail_delivery_driver_assignment
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_delivery_operational_state
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


_ALLOWED_STATES = [
    State.picked_up.value,
    State.en_route_to_customer.value,
    State.arrived_at_customer.value,
    State.id_verification_pending.value,
    State.id_verified.value,
]

_ALL_REASONS = [r.value for r in DriverDeliveryFailureReason]


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "FDS-Store") -> Store:
        store = Store(name=name, code=f"fds-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_setup(db_session: Session, make_store):
    """A started assignment + operational state at a chosen value + order at a
    chosen commercial status. Returns (assignment, driver_user)."""

    def _create(
        *,
        state: str | None = State.arrived_at_customer.value,
        assignment_status: str = "started",
        order_status: str = "out_for_delivery",
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
        return assignment, user

    return _create


def _req(reason: str = "customer_unavailable", note: str | None = None):
    return DriverFailDeliveryRequest(reason_code=reason, note=note)


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


@pytest.mark.parametrize("state", _ALLOWED_STATES)
def test_happy_path_from_allowed_state(
    db_session: Session, make_setup, state: str
) -> None:
    assignment, user = make_setup(state=state)
    out = fail_delivery_driver_assignment(
        db_session, user, assignment.id, _req(note="customer not home")
    )
    assert out.assignment_id == assignment.id
    assert out.order_id == assignment.order_id
    assert out.driver_profile_id == assignment.driver_profile_id
    assert out.store_id == assignment.store_id
    assert out.reported_by_user_id == user.id
    assert out.reason_code == "customer_unavailable"
    assert out.note == "customer not home"

    # The operational state advanced; the assignment status did NOT.
    assert _state(db_session, assignment.id) == "delivery_failed"
    refreshed = db_session.get(type(assignment), assignment.id)
    assert refreshed.status == "started"

    # Exactly one failure row exists.
    count = db_session.scalar(
        select(func.count())
        .select_from(DriverDeliveryFailure)
        .where(DriverDeliveryFailure.assignment_id == assignment.id)
    )
    assert count == 1


@pytest.mark.parametrize("reason", _ALL_REASONS)
def test_all_reason_codes_accepted(
    db_session: Session, make_setup, reason: str
) -> None:
    assignment, user = make_setup()
    out = fail_delivery_driver_assignment(
        db_session, user, assignment.id, _req(reason=reason)
    )
    assert out.reason_code == reason
    assert _state(db_session, assignment.id) == "delivery_failed"


def test_note_max_length_accepted(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    out = fail_delivery_driver_assignment(
        db_session, user, assignment.id, _req(note="x" * 500)
    )
    assert out.note == "x" * 500


def test_note_too_long_rejected() -> None:
    with pytest.raises(pydantic.ValidationError):
        DriverFailDeliveryRequest(reason_code="other_manual_review", note="x" * 501)


# --------------------------------------------------------------------- #
# B. Idempotency
# --------------------------------------------------------------------- #


def test_repeated_same_reason_idempotent(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    first = fail_delivery_driver_assignment(
        db_session, user, assignment.id, _req(reason="customer_refused")
    )
    second = fail_delivery_driver_assignment(
        db_session, user, assignment.id, _req(reason="customer_refused")
    )
    assert second.id == first.id
    # No duplicate row inserted.
    count = db_session.scalar(
        select(func.count())
        .select_from(DriverDeliveryFailure)
        .where(DriverDeliveryFailure.assignment_id == assignment.id)
    )
    assert count == 1
    assert _state(db_session, assignment.id) == "delivery_failed"


def test_repeated_different_reason_is_409(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    fail_delivery_driver_assignment(
        db_session, user, assignment.id, _req(reason="customer_refused")
    )
    with pytest.raises(HTTPException) as exc:
        fail_delivery_driver_assignment(
            db_session, user, assignment.id, _req(reason="unsafe_location")
        )
    assert exc.value.status_code == 409
    # Still exactly one failure row, state unchanged.
    count = db_session.scalar(
        select(func.count())
        .select_from(DriverDeliveryFailure)
        .where(DriverDeliveryFailure.assignment_id == assignment.id)
    )
    assert count == 1


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
    ],
)
def test_too_early_state_is_422(
    db_session: Session, make_setup, state: str
) -> None:
    assignment, user = make_setup(state=state)
    with pytest.raises(HTTPException) as exc:
        fail_delivery_driver_assignment(
            db_session, user, assignment.id, _req()
        )
    assert exc.value.status_code == 422
    assert _state(db_session, assignment.id) == state


@pytest.mark.parametrize(
    "state",
    [
        State.delivery_completed.value,
        State.returned_to_store.value,
        State.canceled.value,
    ],
)
def test_terminal_state_is_422(
    db_session: Session, make_setup, state: str
) -> None:
    assignment, user = make_setup(state=state)
    with pytest.raises(HTTPException) as exc:
        fail_delivery_driver_assignment(
            db_session, user, assignment.id, _req()
        )
    assert exc.value.status_code == 422


def test_returning_to_store_is_409(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=State.returning_to_store.value)
    with pytest.raises(HTTPException) as exc:
        fail_delivery_driver_assignment(
            db_session, user, assignment.id, _req()
        )
    assert exc.value.status_code == 409


def test_no_operational_state_row_is_422(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=None)
    with pytest.raises(HTTPException) as exc:
        fail_delivery_driver_assignment(
            db_session, user, assignment.id, _req()
        )
    assert exc.value.status_code == 422


def test_assignment_not_started_is_422(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(assignment_status="accepted")
    with pytest.raises(HTTPException) as exc:
        fail_delivery_driver_assignment(
            db_session, user, assignment.id, _req()
        )
    assert exc.value.status_code == 422


# --------------------------------------------------------------------- #
# D. Anti-enumeration
# --------------------------------------------------------------------- #


def test_foreign_assignment_is_404(
    db_session: Session, make_setup, make_store
) -> None:
    assignment, _owner = make_setup()
    other_store = make_store(name="FDS-Other")
    other = central_make_user(
        db_session, role=UserRole.driver, store_id=other_store.id
    )
    make_driver_profile(db_session, user=other, store=other_store)
    with pytest.raises(HTTPException) as exc:
        fail_delivery_driver_assignment(
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
        fail_delivery_driver_assignment(
            db_session, user, uuid.uuid4(), _req()
        )
    assert exc.value.status_code == 404


# --------------------------------------------------------------------- #
# E. Boundaries — no commercial / inventory / audit side effects
# --------------------------------------------------------------------- #


def test_order_status_unchanged(db_session: Session, make_setup) -> None:
    assignment, user = make_setup(order_status="out_for_delivery")
    fail_delivery_driver_assignment(
        db_session, user, assignment.id, _req()
    )
    db_session.expire_all()
    order = db_session.get(Order, assignment.order_id)
    assert order.status == OrderStatus.out_for_delivery
    assert order.delivered_at is None


def test_no_order_audit_log_written(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    before = db_session.scalar(
        select(func.count())
        .select_from(OrderAuditLog)
        .where(OrderAuditLog.order_id == assignment.order_id)
    )
    fail_delivery_driver_assignment(
        db_session, user, assignment.id, _req()
    )
    db_session.expire_all()
    after = db_session.scalar(
        select(func.count())
        .select_from(OrderAuditLog)
        .where(OrderAuditLog.order_id == assignment.order_id)
    )
    assert after == before == 0


def test_no_inventory_log_written(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup()
    before = db_session.scalar(
        select(func.count()).select_from(InventoryLog)
    )
    fail_delivery_driver_assignment(
        db_session, user, assignment.id, _req()
    )
    db_session.expire_all()
    after = db_session.scalar(
        select(func.count()).select_from(InventoryLog)
    )
    assert after == before


def test_driver_service_does_not_call_orders_or_inventory() -> None:
    """The driver service must never reach into the orders or inventory
    authority for a fail (operational-only boundary). Strips comments so the
    explanatory docstring/comments don't trip the token search."""
    import inspect

    import app.services.driver as driver_mod

    raw = inspect.getsource(driver_mod.fail_delivery_driver_assignment)
    # Drop the docstring and inline comments — only executable code matters.
    code_lines = []
    for line in raw.splitlines():
        stripped = line.split("#", 1)[0]
        code_lines.append(stripped)
    code = "\n".join(code_lines)
    # The docstring is a single triple-quoted block; remove it.
    if '"""' in code:
        head, _, rest = code.partition('"""')
        _doc, _, tail = rest.partition('"""')
        code = head + tail

    # No commercial bridge call, no inventory call, no Order.status write,
    # and no assignment.status mutation (the fail leaves it `started`).
    assert "complete_order_via_driver(" not in code
    assert "_consume_order_reservations" not in code
    assert "InventoryLog(" not in code
    assert "order.status" not in code.lower()
    assert "assignment.status =" not in code
