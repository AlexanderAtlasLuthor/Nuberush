"""Dr.1.2.E — orders authority driver-completion bridge tests.

Exercises `complete_order_via_driver` directly: the ready/out_for_delivery ->
delivered promotion, the inventory consume via the existing orders path, the
OrderAuditLog written by the orders authority with the driver as actor, the
rejection of non-completable statuses, and the already-delivered idempotency.

This is a SERVICE/DB suite — the bridge does NOT commit, so each test commits
explicitly to mirror the driver service's coordinated transaction.
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

from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import Order
from app.db.models import OrderAuditLog
from app.db.models import OrderItem
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.services.orders import complete_order_via_driver
from tests.helpers.auth import make_user as central_make_user


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "OCB-Store") -> Store:
        store = Store(name=name, code=f"ocb-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_ready_order(db_session: Session, make_store):
    """A store-scoped order with one reserved line item, at a chosen status.

    Builds product/variant/inventory_item with stock reserved (on_hand=10,
    reserved=2) and an order line for qty 2, mirroring the post-reservation
    state an order is in when a driver completes it.
    """

    def _create(status: OrderStatus = OrderStatus.ready):
        store = make_store()
        product = Product(name=f"Vape {uuid.uuid4().hex[:6]}", category="vape")
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
            idempotency_key=f"ocb-{uuid.uuid4().hex}",
            status=status,
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
        db_session.commit()
        db_session.refresh(order)
        return store, order, item

    return _create


def _driver(db_session: Session, store: Store) -> User:
    return central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )


def _audit_rows(db_session: Session, order_id) -> list[OrderAuditLog]:
    db_session.expire_all()
    return list(
        db_session.scalars(
            select(OrderAuditLog).where(OrderAuditLog.order_id == order_id)
        )
    )


# --------------------------------------------------------------------- #
# Happy paths
# --------------------------------------------------------------------- #


def test_ready_to_delivered(db_session: Session, make_ready_order) -> None:
    store, order, _item = make_ready_order(OrderStatus.ready)
    driver = _driver(db_session, store)
    out = complete_order_via_driver(db_session, order.id, driver.id)
    db_session.commit()
    assert out.status == OrderStatus.delivered
    db_session.refresh(order)
    assert order.status == OrderStatus.delivered
    assert order.delivered_at is not None


def test_out_for_delivery_to_delivered(
    db_session: Session, make_ready_order
) -> None:
    store, order, _item = make_ready_order(OrderStatus.out_for_delivery)
    driver = _driver(db_session, store)
    complete_order_via_driver(db_session, order.id, driver.id)
    db_session.commit()
    db_session.refresh(order)
    assert order.status == OrderStatus.delivered


# --------------------------------------------------------------------- #
# Rejected origin statuses
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "bad_status",
    [OrderStatus.pending, OrderStatus.accepted, OrderStatus.preparing],
)
def test_non_completable_status_rejected(
    db_session: Session, make_ready_order, bad_status: OrderStatus
) -> None:
    store, order, _item = make_ready_order(bad_status)
    driver = _driver(db_session, store)
    with pytest.raises(HTTPException) as exc:
        complete_order_via_driver(db_session, order.id, driver.id)
    assert exc.value.status_code == 409
    db_session.rollback()
    db_session.refresh(order)
    assert order.status == bad_status


def test_missing_order_is_404(db_session: Session, make_store) -> None:
    store = make_store()
    driver = _driver(db_session, store)
    with pytest.raises(HTTPException) as exc:
        complete_order_via_driver(db_session, uuid.uuid4(), driver.id)
    assert exc.value.status_code == 404


# --------------------------------------------------------------------- #
# Idempotency
# --------------------------------------------------------------------- #


def test_already_delivered_is_idempotent_no_reconsume(
    db_session: Session, make_ready_order
) -> None:
    store, order, item = make_ready_order(OrderStatus.ready)
    driver = _driver(db_session, store)
    complete_order_via_driver(db_session, order.id, driver.id)
    db_session.commit()

    inv_logs_after_first = db_session.scalar(
        select(func.count())
        .select_from(InventoryLog)
        .where(InventoryLog.inventory_item_id == item.id)
    )
    audits_after_first = len(_audit_rows(db_session, order.id))

    # Second call: already delivered → idempotent, no re-consume, no audit.
    out = complete_order_via_driver(db_session, order.id, driver.id)
    db_session.commit()
    assert out.status == OrderStatus.delivered

    inv_logs_after_second = db_session.scalar(
        select(func.count())
        .select_from(InventoryLog)
        .where(InventoryLog.inventory_item_id == item.id)
    )
    audits_after_second = len(_audit_rows(db_session, order.id))
    assert inv_logs_after_second == inv_logs_after_first
    assert audits_after_second == audits_after_first


# --------------------------------------------------------------------- #
# Inventory consume + audit via orders authority
# --------------------------------------------------------------------- #


def test_consume_reduces_on_hand_and_clears_reserved(
    db_session: Session, make_ready_order
) -> None:
    store, order, item = make_ready_order(OrderStatus.ready)
    driver = _driver(db_session, store)
    complete_order_via_driver(db_session, order.id, driver.id)
    db_session.commit()
    db_session.refresh(item)
    # Consume reduces on_hand by the line qty and releases the reservation.
    assert item.quantity_on_hand == 8
    assert item.quantity_reserved == 0


def test_consume_writes_inventory_log_not_restock(
    db_session: Session, make_ready_order
) -> None:
    store, order, item = make_ready_order(OrderStatus.ready)
    driver = _driver(db_session, store)
    complete_order_via_driver(db_session, order.id, driver.id)
    db_session.commit()
    logs = list(
        db_session.scalars(
            select(InventoryLog).where(
                InventoryLog.inventory_item_id == item.id
            )
        )
    )
    assert logs, "expected an inventory movement from the consume"
    # The consume is a negative (sale) movement, never a restock/replenish.
    for log in logs:
        assert log.quantity_delta < 0


def test_audit_written_by_orders_authority_with_driver_actor(
    db_session: Session, make_ready_order
) -> None:
    store, order, _item = make_ready_order(OrderStatus.ready)
    driver = _driver(db_session, store)
    complete_order_via_driver(db_session, order.id, driver.id)
    db_session.commit()
    audits = _audit_rows(db_session, order.id)
    delivered = [a for a in audits if a.new_status == OrderStatus.delivered]
    assert len(delivered) == 1
    assert delivered[0].action == "order_delivered"
    assert delivered[0].performed_by_user_id == driver.id
