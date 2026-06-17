"""Dr.1.2.I.a — operational-audit wiring tests for the Dr.1.2 compliance actions.

Drives each shipped compliance service and asserts a redacted
`OperationalAuditLog` row (target_type=delivery_assignment) is written in the
SAME transaction as the business mutation, with the correct action and no
sensitive fields. Also reasserts the confirm-driver-return commercial/inventory
outcome is unchanged (OrderAuditLog still written, reservation released once,
quantity_on_hand unchanged).
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DriverDeliveryOperationalStateValue as State
from app.db.models import DriverDeliveryProof
from app.db.models import DriverDeliveryProofMethod
from app.db.models import DriverDeliveryReturn
from app.db.models import DriverDeliveryReturnState
from app.db.models import DriverDeliveryVerification
from app.db.models import DriverDeliveryVerificationMethod
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import OperationalAuditLog
from app.db.models import Order
from app.db.models import OrderAuditLog
from app.db.models import OrderItem
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import UserRole
from app.schemas.driver import DriverFailDeliveryRequest
from app.schemas.driver import DriverProofSubmitRequest
from app.schemas.driver import DriverReturnToStoreRequest
from app.schemas.driver import DriverVerifyAgeRequest
from app.schemas.orders import StoreConfirmDriverReturnRequest
from app.services.driver import complete_delivery_driver_assignment
from app.services.driver import fail_delivery_driver_assignment
from app.services.driver import return_to_store_driver_assignment
from app.services.driver import submit_proof_driver_assignment
from app.services.driver import verify_age_driver_assignment
from app.services.orders import confirm_driver_return_for_store
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_delivery_operational_state
from tests.helpers.driver import make_driver_profile
from tests.helpers.driver import make_order_driver_assignment

# Fields that must never appear in any audit before/after/metadata payload.
_SENSITIVE_KEYS = {
    "customer_email",
    "email",
    "address",
    "id_number",
    "dob",
    "license",
    "photo",
    "signature",
    "ocr",
    "barcode",
    "latitude",
    "longitude",
    "gps",
    "access_token",
    "authorization",
}


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "IAW-Store") -> Store:
        store = Store(name=name, code=f"iaw-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_setup(db_session: Session, make_store):
    """Build a reserved order + driver + assignment + operational state at a
    chosen value. Returns a dict of rows."""

    def _create(
        *,
        state: str,
        order_status: OrderStatus = OrderStatus.out_for_delivery,
        with_verification_pass: bool = False,
        with_proof: bool = False,
        with_return: str | None = None,
    ):
        store = make_store()
        driver = central_make_user(
            db_session, role=UserRole.driver, store_id=store.id
        )
        profile = make_driver_profile(db_session, user=driver, store=store)
        product = Product(name=f"V {uuid.uuid4().hex[:6]}", category="vape")
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
            idempotency_key=f"iaw-{uuid.uuid4().hex}",
            status=order_status,
            subtotal_amount=Decimal("20.00"),
            total_amount=Decimal("20.00"),
        )
        db_session.add(order)
        db_session.flush()
        db_session.add(
            OrderItem(
                order_id=order.id,
                variant_id=variant.id,
                inventory_item_id=item.id,
                quantity=2,
                unit_price=Decimal("10.00"),
                line_total=Decimal("20.00"),
            )
        )
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
        if with_verification_pass:
            db_session.add(
                DriverDeliveryVerification(
                    assignment_id=assignment.id,
                    order_id=order.id,
                    driver_profile_id=profile.id,
                    store_id=store.id,
                    outcome="pass",
                    method=DriverDeliveryVerificationMethod.manual_checklist.value,
                )
            )
        if with_proof:
            db_session.add(
                DriverDeliveryProof(
                    assignment_id=assignment.id,
                    order_id=order.id,
                    driver_profile_id=profile.id,
                    store_id=store.id,
                    method=DriverDeliveryProofMethod.manual_checklist.value,
                    recipient_present_confirmed=True,
                    handoff_confirmed=True,
                    restricted_not_left_unattended=True,
                )
            )
        if with_return is not None:
            db_session.add(
                DriverDeliveryReturn(
                    assignment_id=assignment.id,
                    order_id=order.id,
                    driver_profile_id=profile.id,
                    store_id=store.id,
                    driver_user_id=driver.id,
                    return_state=with_return,
                )
            )
        db_session.commit()
        db_session.refresh(order)
        db_session.refresh(assignment)
        return {
            "store": store,
            "driver": driver,
            "order": order,
            "item": item,
            "assignment": assignment,
        }

    return _create


def _audit_rows(db_session, assignment_id, action: str):
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(OperationalAuditLog).where(
                OperationalAuditLog.target_id == assignment_id,
                OperationalAuditLog.action == action,
            )
        )
    )


def _assert_no_sensitive(log: OperationalAuditLog) -> None:
    for blob in (log.before, log.after, log.event_metadata):
        if not blob:
            continue
        for key in blob:
            assert key not in _SENSITIVE_KEYS, key


# --------------------------------------------------------------------- #
# Driver actions
# --------------------------------------------------------------------- #


def test_verify_age_writes_audit(db_session: Session, make_setup) -> None:
    s = make_setup(state=State.arrived_at_customer.value)
    verify_age_driver_assignment(
        db_session,
        s["driver"],
        s["assignment"].id,
        DriverVerifyAgeRequest(outcome="pass", note="ok"),
    )
    rows = _audit_rows(db_session, s["assignment"].id, "delivery_verified")
    assert len(rows) == 1
    log = rows[0]
    assert log.target_type == "delivery_assignment"
    assert log.actor_user_id == s["driver"].id
    assert log.store_id == s["store"].id
    assert log.after.get("outcome") == "pass"
    _assert_no_sensitive(log)


def test_proof_writes_audit(db_session: Session, make_setup) -> None:
    s = make_setup(state=State.id_verified.value)
    submit_proof_driver_assignment(
        db_session,
        s["driver"],
        s["assignment"].id,
        DriverProofSubmitRequest(
            recipient_present_confirmed=True,
            handoff_confirmed=True,
            restricted_not_left_unattended=True,
        ),
    )
    rows = _audit_rows(
        db_session, s["assignment"].id, "delivery_proof_recorded"
    )
    assert len(rows) == 1
    _assert_no_sensitive(rows[0])


def test_complete_writes_audit(db_session: Session, make_setup) -> None:
    s = make_setup(
        state=State.id_verified.value,
        order_status=OrderStatus.out_for_delivery,
        with_verification_pass=True,
        with_proof=True,
    )
    complete_delivery_driver_assignment(
        db_session, s["driver"], s["assignment"].id
    )
    rows = _audit_rows(db_session, s["assignment"].id, "delivery_completed")
    assert len(rows) == 1
    log = rows[0]
    assert log.after.get("status") == "completed"
    _assert_no_sensitive(log)


def test_fail_writes_audit(db_session: Session, make_setup) -> None:
    s = make_setup(state=State.arrived_at_customer.value)
    fail_delivery_driver_assignment(
        db_session,
        s["driver"],
        s["assignment"].id,
        DriverFailDeliveryRequest(reason_code="customer_unavailable"),
    )
    rows = _audit_rows(db_session, s["assignment"].id, "delivery_failed")
    assert len(rows) == 1
    log = rows[0]
    assert log.after.get("reason_code") == "customer_unavailable"
    _assert_no_sensitive(log)


def test_return_start_writes_audit(db_session: Session, make_setup) -> None:
    s = make_setup(state=State.delivery_failed.value)
    return_to_store_driver_assignment(
        db_session,
        s["driver"],
        s["assignment"].id,
        DriverReturnToStoreRequest(action="start"),
    )
    rows = _audit_rows(
        db_session, s["assignment"].id, "delivery_return_started"
    )
    assert len(rows) == 1
    assert rows[0].after.get("return_state") == "returning"
    _assert_no_sensitive(rows[0])


def test_return_arrive_writes_audit(db_session: Session, make_setup) -> None:
    s = make_setup(state=State.delivery_failed.value)
    return_to_store_driver_assignment(
        db_session,
        s["driver"],
        s["assignment"].id,
        DriverReturnToStoreRequest(action="start"),
    )
    return_to_store_driver_assignment(
        db_session,
        s["driver"],
        s["assignment"].id,
        DriverReturnToStoreRequest(action="arrive"),
    )
    rows = _audit_rows(
        db_session, s["assignment"].id, "delivery_return_arrived"
    )
    assert len(rows) == 1
    assert (
        rows[0].after.get("return_state")
        == "returned_pending_confirmation"
    )
    _assert_no_sensitive(rows[0])


# --------------------------------------------------------------------- #
# Store confirm action
# --------------------------------------------------------------------- #


def test_confirm_writes_audit(db_session: Session, make_setup) -> None:
    s = make_setup(
        state=State.returned_to_store.value,
        order_status=OrderStatus.out_for_delivery,
        with_return=(
            DriverDeliveryReturnState.returned_pending_confirmation.value
        ),
    )
    actor = central_make_user(
        db_session, role=UserRole.manager, store_id=s["store"].id
    )
    confirm_driver_return_for_store(
        db_session,
        s["order"].id,
        StoreConfirmDriverReturnRequest(received_confirmed=True),
        actor,
    )
    rows = _audit_rows(
        db_session, s["assignment"].id, "delivery_return_confirmed"
    )
    assert len(rows) == 1
    log = rows[0]
    assert log.actor_user_id == actor.id
    assert log.after.get("return_state") == "confirmed"
    assert log.after.get("status") == "canceled"
    _assert_no_sensitive(log)


def test_confirm_keeps_order_audit_and_inventory_unchanged(
    db_session: Session, make_setup
) -> None:
    s = make_setup(
        state=State.returned_to_store.value,
        order_status=OrderStatus.out_for_delivery,
        with_return=(
            DriverDeliveryReturnState.returned_pending_confirmation.value
        ),
    )
    actor = central_make_user(
        db_session, role=UserRole.manager, store_id=s["store"].id
    )
    confirm_driver_return_for_store(
        db_session,
        s["order"].id,
        StoreConfirmDriverReturnRequest(received_confirmed=True),
        actor,
    )
    db_session.expire_all()
    # OrderAuditLog (canceled) still written by orders authority.
    order_audits = db_session.scalar(
        select(func.count())
        .select_from(OrderAuditLog)
        .where(
            OrderAuditLog.order_id == s["order"].id,
            OrderAuditLog.new_status == OrderStatus.canceled,
        )
    )
    assert order_audits == 1
    # Reservation released once; quantity_on_hand unchanged (no restock).
    db_session.refresh(s["item"])
    assert s["item"].quantity_reserved == 0
    assert s["item"].quantity_on_hand == 10
    # The release wrote an inventory log; none is a restock/return movement.
    logs = list(
        db_session.scalars(
            select(InventoryLog).where(
                InventoryLog.inventory_item_id == s["item"].id
            )
        )
    )
    assert logs
    for log in logs:
        assert log.quantity_delta <= 0


def test_audit_row_in_same_transaction_as_failure(
    db_session: Session, make_setup
) -> None:
    """The audit row and the business row commit together: after a fail there
    is exactly one delivery_failed audit row for the assignment."""
    s = make_setup(state=State.arrived_at_customer.value)
    fail_delivery_driver_assignment(
        db_session,
        s["driver"],
        s["assignment"].id,
        DriverFailDeliveryRequest(reason_code="store_issue"),
    )
    db_session.expire_all()
    audit = db_session.scalar(
        select(func.count())
        .select_from(OperationalAuditLog)
        .where(
            OperationalAuditLog.target_id == s["assignment"].id,
            OperationalAuditLog.action == "delivery_failed",
        )
    )
    assert audit == 1
