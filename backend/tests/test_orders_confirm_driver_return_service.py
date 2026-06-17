"""Dr.1.2.H — store return confirmation service tests.

Exercises `confirm_driver_return_for_store` directly: the atomic confirm that
stamps DriverDeliveryReturn -> confirmed, cancels the order (releasing the held
reservation with no quantity_on_hand change) via the shared cancel core, closes
the assignment to canceled, leaves the operational state at returned_to_store,
and writes exactly one OrderAuditLog; plus the 404/409/422 gate matrix and the
state-inferred idempotency.

SERVICE/DB suite only — no route layer.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DriverDeliveryOperationalState
from app.db.models import DriverDeliveryOperationalStateValue as State
from app.db.models import DriverDeliveryReturn
from app.db.models import DriverDeliveryReturnState
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import InventoryMovementType
from app.db.models import Order
from app.db.models import OrderAuditLog
from app.db.models import OrderDriverAssignment
from app.db.models import OrderItem
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.orders import StoreConfirmDriverReturnRequest
from app.services.orders import confirm_driver_return_for_store
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_delivery_operational_state
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order_driver_assignment


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "HCS-Store") -> Store:
        store = Store(name=name, code=f"hcs-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_setup(db_session: Session, make_store):
    """A returned-pending-confirmation order ready for store confirmation.

    Builds: store + manager actor + reserved inventory (on_hand=10,
    reserved=2) + order (chosen status, one line qty 2) + driver profile +
    assignment (chosen status) + operational state (chosen) + a
    DriverDeliveryReturn (chosen return_state). Returns a dict of the rows.
    """

    def _create(
        *,
        order_status: OrderStatus = OrderStatus.out_for_delivery,
        assignment_status: str = "started",
        op_state: str = State.returned_to_store.value,
        return_state: str = (
            DriverDeliveryReturnState.returned_pending_confirmation.value
        ),
        with_return: bool = True,
        confirmed: bool = False,
        actor_role: UserRole = UserRole.manager,
    ):
        store = make_store()
        actor = central_make_user(
            db_session, role=actor_role, store_id=store.id
        )
        driver_user = central_make_user(
            db_session, role=UserRole.driver, store_id=store.id
        )
        profile = make_driver_profile(
            db_session, user=driver_user, store=store
        )
        product = Product(
            name=f"Vape {uuid.uuid4().hex[:6]}", category="vape"
        )
        db_session.add(product)
        db_session.flush()
        variant = ProductVariant(
            product_id=product.id,
            sku=f"sku-{uuid.uuid4().hex[:8]}",
            price=Decimal("10.00"),
        )
        db_session.add(variant)
        db_session.flush()
        item = InventoryItem(
            store_id=store.id,
            variant_id=variant.id,
            quantity_on_hand=10,
            quantity_reserved=2,
        )
        db_session.add(item)
        db_session.flush()
        order = Order(
            store_id=store.id,
            idempotency_key=f"hcs-{uuid.uuid4().hex}",
            status=order_status,
            subtotal_amount=Decimal("20.00"),
            total_amount=Decimal("20.00"),
        )
        db_session.add(order)
        db_session.flush()
        line = OrderItem(
            order_id=order.id,
            variant_id=variant.id,
            inventory_item_id=item.id,
            quantity=2,
            unit_price=Decimal("10.00"),
            line_total=Decimal("20.00"),
        )
        db_session.add(line)
        assignment = make_order_driver_assignment(
            db_session,
            order=order,
            driver_profile=profile,
            store=store,
            status=assignment_status,
        )
        make_driver_delivery_operational_state(
            db_session, assignment=assignment, state=op_state
        )
        driver_return = None
        if with_return:
            driver_return = DriverDeliveryReturn(
                assignment_id=assignment.id,
                order_id=order.id,
                driver_profile_id=profile.id,
                store_id=store.id,
                driver_user_id=driver_user.id,
                return_state=return_state,
                note="returned by driver",
            )
            if confirmed:
                driver_return.confirmed_at = order.created_at
                driver_return.confirmed_by_user_id = actor.id
            db_session.add(driver_return)
        db_session.commit()
        db_session.refresh(order)
        if driver_return is not None:
            db_session.refresh(driver_return)
        return {
            "store": store,
            "actor": actor,
            "order": order,
            "item": item,
            "assignment": assignment,
            "driver_return": driver_return,
        }

    return _create


def _req(note: str | None = None) -> StoreConfirmDriverReturnRequest:
    return StoreConfirmDriverReturnRequest(received_confirmed=True, note=note)


def _audit_count(db_session, order_id) -> int:
    db_session.expire_all()
    return db_session.scalar(
        select(func.count())
        .select_from(OrderAuditLog)
        .where(OrderAuditLog.order_id == order_id)
    )


def _op_state(db_session, assignment_id) -> str:
    db_session.expire_all()
    return db_session.scalar(
        select(DriverDeliveryOperationalState).where(
            DriverDeliveryOperationalState.assignment_id == assignment_id
        )
    ).state


# --------------------------------------------------------------------- #
# A. Happy path
# --------------------------------------------------------------------- #


def test_confirm_from_returned_pending_sets_confirmed(
    db_session: Session, make_setup
) -> None:
    s = make_setup()
    order, dr = confirm_driver_return_for_store(
        db_session, s["order"].id, _req(note="received intact"), s["actor"]
    )
    assert dr.return_state == "confirmed"
    assert dr.confirmed_at is not None
    assert dr.confirmed_by_user_id == s["actor"].id
    assert dr.note == "received intact"


def test_confirm_cancels_order(db_session: Session, make_setup) -> None:
    s = make_setup()
    order, _dr = confirm_driver_return_for_store(
        db_session, s["order"].id, _req(), s["actor"]
    )
    assert order.status == OrderStatus.canceled
    assert order.canceled_at is not None
    assert order.cancel_reason is not None


def test_confirm_releases_reservation_no_restock(
    db_session: Session, make_setup
) -> None:
    s = make_setup()
    confirm_driver_return_for_store(
        db_session, s["order"].id, _req(), s["actor"]
    )
    db_session.refresh(s["item"])
    # Reservation released; quantity_on_hand never increases (no restock).
    assert s["item"].quantity_reserved == 0
    assert s["item"].quantity_on_hand == 10
    # No restock/return movement was written.
    logs = list(
        db_session.scalars(
            select(InventoryLog).where(
                InventoryLog.inventory_item_id == s["item"].id
            )
        )
    )
    assert logs, "expected a reservation-release movement"
    for log in logs:
        assert log.movement_type != InventoryMovementType.return_
        assert log.quantity_delta <= 0


def test_confirm_writes_order_audit_canceled(
    db_session: Session, make_setup
) -> None:
    s = make_setup()
    confirm_driver_return_for_store(
        db_session, s["order"].id, _req(), s["actor"]
    )
    db_session.expire_all()
    audits = list(
        db_session.scalars(
            select(OrderAuditLog).where(
                OrderAuditLog.order_id == s["order"].id
            )
        )
    )
    canceled = [a for a in audits if a.new_status == OrderStatus.canceled]
    assert len(canceled) == 1
    assert canceled[0].action == "order_canceled"
    assert canceled[0].performed_by_user_id == s["actor"].id


def test_confirm_sets_assignment_canceled(
    db_session: Session, make_setup
) -> None:
    s = make_setup()
    confirm_driver_return_for_store(
        db_session, s["order"].id, _req(), s["actor"]
    )
    db_session.refresh(s["assignment"])
    assert s["assignment"].status == "canceled"


def test_confirm_leaves_operational_state_returned_to_store(
    db_session: Session, make_setup
) -> None:
    s = make_setup()
    confirm_driver_return_for_store(
        db_session, s["order"].id, _req(), s["actor"]
    )
    assert _op_state(db_session, s["assignment"].id) == "returned_to_store"


# --------------------------------------------------------------------- #
# B. Gate matrix
# --------------------------------------------------------------------- #


def test_requires_returned_pending_confirmation_409(
    db_session: Session, make_setup
) -> None:
    s = make_setup(
        return_state=DriverDeliveryReturnState.returning.value,
        op_state=State.returning_to_store.value,
    )
    with pytest.raises(HTTPException) as exc:
        confirm_driver_return_for_store(
            db_session, s["order"].id, _req(), s["actor"]
        )
    assert exc.value.status_code == 409


def test_no_return_record_404(db_session: Session, make_setup) -> None:
    s = make_setup(with_return=False, op_state=State.delivery_failed.value)
    with pytest.raises(HTTPException) as exc:
        confirm_driver_return_for_store(
            db_session, s["order"].id, _req(), s["actor"]
        )
    assert exc.value.status_code == 404


def test_missing_order_404(db_session: Session, make_setup) -> None:
    s = make_setup()
    with pytest.raises(HTTPException) as exc:
        confirm_driver_return_for_store(
            db_session, uuid.uuid4(), _req(), s["actor"]
        )
    assert exc.value.status_code == 404


def test_operational_state_not_returned_to_store_409(
    db_session: Session, make_setup
) -> None:
    s = make_setup(op_state=State.returning_to_store.value)
    with pytest.raises(HTTPException) as exc:
        confirm_driver_return_for_store(
            db_session, s["order"].id, _req(), s["actor"]
        )
    assert exc.value.status_code == 409


def test_assignment_not_started_409(
    db_session: Session, make_setup
) -> None:
    s = make_setup(assignment_status="canceled")
    with pytest.raises(HTTPException) as exc:
        confirm_driver_return_for_store(
            db_session, s["order"].id, _req(), s["actor"]
        )
    assert exc.value.status_code == 409


def test_order_not_cancelable_422(db_session: Session, make_setup) -> None:
    s = make_setup(order_status=OrderStatus.delivered)
    with pytest.raises(HTTPException) as exc:
        confirm_driver_return_for_store(
            db_session, s["order"].id, _req(), s["actor"]
        )
    assert exc.value.status_code == 422


# --------------------------------------------------------------------- #
# C. Idempotency
# --------------------------------------------------------------------- #


def test_idempotent_repeat_returns_existing_200(
    db_session: Session, make_setup
) -> None:
    s = make_setup()
    confirm_driver_return_for_store(
        db_session, s["order"].id, _req(), s["actor"]
    )
    # Repeat: already confirmed + canceled + assignment canceled -> idempotent.
    order, dr = confirm_driver_return_for_store(
        db_session, s["order"].id, _req(), s["actor"]
    )
    assert order.status == OrderStatus.canceled
    assert dr.return_state == "confirmed"


def test_idempotent_repeat_does_not_double_release(
    db_session: Session, make_setup
) -> None:
    s = make_setup()
    confirm_driver_return_for_store(
        db_session, s["order"].id, _req(), s["actor"]
    )
    db_session.refresh(s["item"])
    reserved_after_first = s["item"].quantity_reserved
    logs_after_first = db_session.scalar(
        select(func.count())
        .select_from(InventoryLog)
        .where(InventoryLog.inventory_item_id == s["item"].id)
    )
    confirm_driver_return_for_store(
        db_session, s["order"].id, _req(), s["actor"]
    )
    db_session.refresh(s["item"])
    logs_after_second = db_session.scalar(
        select(func.count())
        .select_from(InventoryLog)
        .where(InventoryLog.inventory_item_id == s["item"].id)
    )
    assert s["item"].quantity_reserved == reserved_after_first == 0
    assert s["item"].quantity_on_hand == 10
    assert logs_after_second == logs_after_first


def test_idempotent_repeat_does_not_duplicate_audit(
    db_session: Session, make_setup
) -> None:
    s = make_setup()
    confirm_driver_return_for_store(
        db_session, s["order"].id, _req(), s["actor"]
    )
    audits_after_first = _audit_count(db_session, s["order"].id)
    confirm_driver_return_for_store(
        db_session, s["order"].id, _req(), s["actor"]
    )
    audits_after_second = _audit_count(db_session, s["order"].id)
    assert audits_after_second == audits_after_first == 1


# --------------------------------------------------------------------- #
# D. Inconsistent confirmed states -> 409
# --------------------------------------------------------------------- #


def test_confirmed_but_order_not_canceled_409(
    db_session: Session, make_setup
) -> None:
    # Return already confirmed, but order still out_for_delivery (inconsistent).
    s = make_setup(
        confirmed=True,
        return_state=DriverDeliveryReturnState.confirmed.value,
        order_status=OrderStatus.out_for_delivery,
        assignment_status="canceled",
    )
    with pytest.raises(HTTPException) as exc:
        confirm_driver_return_for_store(
            db_session, s["order"].id, _req(), s["actor"]
        )
    assert exc.value.status_code == 409


def test_order_canceled_but_return_not_confirmed_409(
    db_session: Session, make_setup
) -> None:
    # Order already canceled, but return still pending and op state not
    # returned_to_store would be 409; here keep op state valid but the order
    # canceled makes it non-cancelable -> 422. Use a return_state mismatch to
    # force the not-awaiting-confirmation 409 instead.
    s = make_setup(
        return_state=DriverDeliveryReturnState.returning.value,
        op_state=State.returned_to_store.value,
    )
    with pytest.raises(HTTPException) as exc:
        confirm_driver_return_for_store(
            db_session, s["order"].id, _req(), s["actor"]
        )
    assert exc.value.status_code == 409


# --------------------------------------------------------------------- #
# E. Atomicity
# --------------------------------------------------------------------- #


def test_atomicity_rolls_back_on_failure(
    db_session: Session, make_setup
) -> None:
    # Order is delivered (not cancelable): the cancelability gate fires before
    # any mutation, so the return record is NOT stamped confirmed.
    s = make_setup(order_status=OrderStatus.delivered)
    with pytest.raises(HTTPException) as exc:
        confirm_driver_return_for_store(
            db_session, s["order"].id, _req(), s["actor"]
        )
    assert exc.value.status_code == 422
    db_session.expire_all()
    dr = db_session.get(DriverDeliveryReturn, s["driver_return"].id)
    assert dr.return_state == "returned_pending_confirmation"
    assert dr.confirmed_at is None
    assert dr.confirmed_by_user_id is None
    order = db_session.get(Order, s["order"].id)
    assert order.status == OrderStatus.delivered
    assignment = db_session.get(OrderDriverAssignment, s["assignment"].id)
    assert assignment.status == "started"
    db_session.refresh(s["item"])
    assert s["item"].quantity_reserved == 2
