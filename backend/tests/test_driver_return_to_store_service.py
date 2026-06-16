"""Dr.1.2.G — return-to-store service tests.

Exercises `return_to_store_driver_assignment` directly: the operational-only
start/arrive custody flow (delivery_failed -> returning_to_store ->
returned_to_store) that creates/updates the single `DriverDeliveryReturn` row;
the per-action idempotency rule; the 422/409/404 guard matrix; and the boundary
that the driver never confirms receipt, never mutates Order.status / inventory /
OrderAuditLog, and leaves assignment.status `started`.

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
from app.db.models import DriverDeliveryReturn
from app.db.models import InventoryLog
from app.db.models import Order
from app.db.models import OrderAuditLog
from app.db.models import OrderStatus
from app.db.models import Store
from app.db.models import UserRole
from app.schemas.driver import DriverReturnToStoreRequest
from app.services.driver import return_to_store_driver_assignment
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_delivery_operational_state
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order
from tests.helpers.driver import make_order_driver_assignment


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "RTS-Store") -> Store:
        store = Store(name=name, code=f"rts-{uuid.uuid4().hex[:8]}")
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
        state: str | None = State.delivery_failed.value,
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


def _start(note: str | None = None):
    return DriverReturnToStoreRequest(action="start", note=note)


def _arrive(note: str | None = None):
    return DriverReturnToStoreRequest(action="arrive", note=note)


def _state(db_session, assignment_id) -> str:
    db_session.expire_all()
    return db_session.scalar(
        select(DriverDeliveryOperationalState).where(
            DriverDeliveryOperationalState.assignment_id == assignment_id
        )
    ).state


def _return_count(db_session, assignment_id) -> int:
    return db_session.scalar(
        select(func.count())
        .select_from(DriverDeliveryReturn)
        .where(DriverDeliveryReturn.assignment_id == assignment_id)
    )


# --------------------------------------------------------------------- #
# A. Happy paths
# --------------------------------------------------------------------- #


def test_start_from_delivery_failed_creates_return(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=State.delivery_failed.value)
    out = return_to_store_driver_assignment(
        db_session, user, assignment.id, _start(note="heading back")
    )
    assert out.assignment_id == assignment.id
    assert out.order_id == assignment.order_id
    assert out.driver_profile_id == assignment.driver_profile_id
    assert out.store_id == assignment.store_id
    assert out.driver_user_id == user.id
    assert out.return_state == "returning"
    assert out.note == "heading back"
    assert out.confirmed_at is None
    assert out.confirmed_by_user_id is None

    assert _state(db_session, assignment.id) == "returning_to_store"
    assert _return_count(db_session, assignment.id) == 1
    refreshed = db_session.get(type(assignment), assignment.id)
    assert refreshed.status == "started"


def test_arrive_from_returning_updates_return(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=State.delivery_failed.value)
    return_to_store_driver_assignment(
        db_session, user, assignment.id, _start(note="orig")
    )
    out = return_to_store_driver_assignment(
        db_session, user, assignment.id, _arrive()
    )
    assert out.return_state == "returned_pending_confirmation"
    # No note provided on arrive -> preserve existing note.
    assert out.note == "orig"
    assert out.confirmed_at is None
    assert out.confirmed_by_user_id is None

    assert _state(db_session, assignment.id) == "returned_to_store"
    # Still exactly one row (updated, not inserted).
    assert _return_count(db_session, assignment.id) == 1
    refreshed = db_session.get(type(assignment), assignment.id)
    assert refreshed.status == "started"


def test_arrive_updates_note_when_provided(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=State.delivery_failed.value)
    return_to_store_driver_assignment(
        db_session, user, assignment.id, _start(note="orig")
    )
    out = return_to_store_driver_assignment(
        db_session, user, assignment.id, _arrive(note="updated")
    )
    assert out.note == "updated"


# --------------------------------------------------------------------- #
# B. Gate matrix
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "state",
    [
        State.not_started.value,
        State.en_route_to_store.value,
        State.picked_up.value,
        State.arrived_at_customer.value,
        State.id_verified.value,
    ],
)
def test_start_requires_prior_failure_422(
    db_session: Session, make_setup, state: str
) -> None:
    assignment, user = make_setup(state=state)
    with pytest.raises(HTTPException) as exc:
        return_to_store_driver_assignment(
            db_session, user, assignment.id, _start()
        )
    assert exc.value.status_code == 422
    assert _return_count(db_session, assignment.id) == 0
    assert _state(db_session, assignment.id) == state


def test_arrive_before_start_422(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=State.delivery_failed.value)
    with pytest.raises(HTTPException) as exc:
        return_to_store_driver_assignment(
            db_session, user, assignment.id, _arrive()
        )
    assert exc.value.status_code == 422
    assert _return_count(db_session, assignment.id) == 0


def test_start_after_arrive_409(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=State.delivery_failed.value)
    return_to_store_driver_assignment(
        db_session, user, assignment.id, _start()
    )
    return_to_store_driver_assignment(
        db_session, user, assignment.id, _arrive()
    )
    with pytest.raises(HTTPException) as exc:
        return_to_store_driver_assignment(
            db_session, user, assignment.id, _start()
        )
    assert exc.value.status_code == 409


@pytest.mark.parametrize(
    "state",
    [
        State.delivery_completed.value,
        State.canceled.value,
    ],
)
def test_terminal_non_return_states_422(
    db_session: Session, make_setup, state: str
) -> None:
    assignment, user = make_setup(state=state)
    with pytest.raises(HTTPException) as exc_start:
        return_to_store_driver_assignment(
            db_session, user, assignment.id, _start()
        )
    assert exc_start.value.status_code == 422
    with pytest.raises(HTTPException) as exc_arrive:
        return_to_store_driver_assignment(
            db_session, user, assignment.id, _arrive()
        )
    assert exc_arrive.value.status_code == 422


def test_no_operational_state_row_is_422(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=None)
    with pytest.raises(HTTPException) as exc:
        return_to_store_driver_assignment(
            db_session, user, assignment.id, _start()
        )
    assert exc.value.status_code == 422


# --------------------------------------------------------------------- #
# C. Idempotency
# --------------------------------------------------------------------- #


def test_start_idempotent_returns_existing(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=State.delivery_failed.value)
    first = return_to_store_driver_assignment(
        db_session, user, assignment.id, _start()
    )
    second = return_to_store_driver_assignment(
        db_session, user, assignment.id, _start()
    )
    assert second.id == first.id
    assert _return_count(db_session, assignment.id) == 1
    assert _state(db_session, assignment.id) == "returning_to_store"


def test_arrive_idempotent_returns_existing(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=State.delivery_failed.value)
    return_to_store_driver_assignment(
        db_session, user, assignment.id, _start()
    )
    first = return_to_store_driver_assignment(
        db_session, user, assignment.id, _arrive()
    )
    second = return_to_store_driver_assignment(
        db_session, user, assignment.id, _arrive()
    )
    assert second.id == first.id
    assert second.return_state == "returned_pending_confirmation"
    assert _return_count(db_session, assignment.id) == 1
    assert _state(db_session, assignment.id) == "returned_to_store"


# --------------------------------------------------------------------- #
# D. Anti-enumeration
# --------------------------------------------------------------------- #


def test_foreign_assignment_404(
    db_session: Session, make_setup, make_store
) -> None:
    assignment, _owner = make_setup(state=State.delivery_failed.value)
    other_store = make_store(name="RTS-Other")
    other = central_make_user(
        db_session, role=UserRole.driver, store_id=other_store.id
    )
    make_driver_profile(db_session, user=other, store=other_store)
    with pytest.raises(HTTPException) as exc:
        return_to_store_driver_assignment(
            db_session, other, assignment.id, _start()
        )
    assert exc.value.status_code == 404


def test_missing_assignment_404(
    db_session: Session, make_store
) -> None:
    store = make_store()
    user = central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )
    make_driver_profile(db_session, user=user, store=store)
    with pytest.raises(HTTPException) as exc:
        return_to_store_driver_assignment(
            db_session, user, uuid.uuid4(), _start()
        )
    assert exc.value.status_code == 404


# --------------------------------------------------------------------- #
# E. Boundaries — no commercial / inventory / audit / confirm side effects
# --------------------------------------------------------------------- #


def test_assignment_status_remains_started(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=State.delivery_failed.value)
    return_to_store_driver_assignment(
        db_session, user, assignment.id, _start()
    )
    return_to_store_driver_assignment(
        db_session, user, assignment.id, _arrive()
    )
    db_session.expire_all()
    refreshed = db_session.get(type(assignment), assignment.id)
    assert refreshed.status == "started"


def test_order_status_unchanged(db_session: Session, make_setup) -> None:
    assignment, user = make_setup(
        state=State.delivery_failed.value, order_status="out_for_delivery"
    )
    return_to_store_driver_assignment(
        db_session, user, assignment.id, _start()
    )
    return_to_store_driver_assignment(
        db_session, user, assignment.id, _arrive()
    )
    db_session.expire_all()
    order = db_session.get(Order, assignment.order_id)
    assert order.status == OrderStatus.out_for_delivery
    assert order.delivered_at is None


def test_no_inventory_log_written(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=State.delivery_failed.value)
    before = db_session.scalar(
        select(func.count()).select_from(InventoryLog)
    )
    return_to_store_driver_assignment(
        db_session, user, assignment.id, _start()
    )
    return_to_store_driver_assignment(
        db_session, user, assignment.id, _arrive()
    )
    db_session.expire_all()
    after = db_session.scalar(
        select(func.count()).select_from(InventoryLog)
    )
    assert after == before


def test_no_order_audit_log_written(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=State.delivery_failed.value)
    return_to_store_driver_assignment(
        db_session, user, assignment.id, _start()
    )
    return_to_store_driver_assignment(
        db_session, user, assignment.id, _arrive()
    )
    db_session.expire_all()
    audits = db_session.scalar(
        select(func.count())
        .select_from(OrderAuditLog)
        .where(OrderAuditLog.order_id == assignment.order_id)
    )
    assert audits == 0


def test_driver_returnstate_never_confirmed(
    db_session: Session, make_setup
) -> None:
    assignment, user = make_setup(state=State.delivery_failed.value)
    return_to_store_driver_assignment(
        db_session, user, assignment.id, _start()
    )
    out = return_to_store_driver_assignment(
        db_session, user, assignment.id, _arrive()
    )
    assert out.return_state != "confirmed"
    db_session.expire_all()
    record = db_session.scalar(
        select(DriverDeliveryReturn).where(
            DriverDeliveryReturn.assignment_id == assignment.id
        )
    )
    assert record.return_state == "returned_pending_confirmation"
    assert record.confirmed_at is None
    assert record.confirmed_by_user_id is None


def test_service_does_not_call_orders_or_inventory() -> None:
    """The return-to-store service (and its two action helpers) must never reach
    into the orders or inventory authority. Strips comments/docstrings so the
    explanatory text doesn't trip the token search."""
    import inspect

    import app.services.driver as driver_mod

    funcs = [
        driver_mod.return_to_store_driver_assignment,
        driver_mod._return_to_store_start,
        driver_mod._return_to_store_arrive,
    ]
    for fn in funcs:
        raw = inspect.getsource(fn)
        code = "\n".join(line.split("#", 1)[0] for line in raw.splitlines())
        if '"""' in code:
            head, _, rest = code.partition('"""')
            _doc, _, tail = rest.partition('"""')
            code = head + tail
        assert "complete_order_via_driver(" not in code, fn.__name__
        assert "_consume_order_reservations" not in code, fn.__name__
        assert "InventoryLog(" not in code, fn.__name__
        assert "order.status" not in code.lower(), fn.__name__
        assert "assignment.status =" not in code, fn.__name__
        assert "confirmed_at" not in code, fn.__name__
        assert "confirmed_by_user_id" not in code, fn.__name__
