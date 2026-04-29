"""Concurrency tests for the orders coordinator (S5.10).

These tests bypass FastAPI and call the service layer directly so the
behaviour under test is the row-level lock taken inside
``_lock_inventory_item`` (SELECT ... FOR UPDATE) plus the unique
``(store_id, idempotency_key)`` constraint, not HTTP plumbing.

Critical infrastructure notes
-----------------------------
- A SQLAlchemy ``Session`` MUST NOT be shared across threads. Each
  worker creates its OWN ``Session`` bound to its OWN connection.
- The shared ``db_session`` fixture from conftest is intentionally NOT
  used here: it wraps everything in a single SAVEPOINT transaction
  that would defeat the row-lock test. We use a module-scoped engine
  with ``NullPool`` so every Session opens a fresh connection.
- Setup data is COMMITTED to the test database before workers start
  (workers query it via independent sessions). Each test fixture
  cleans up by deleting the rows it created.
- Threads synchronize start with ``threading.Barrier`` so the second
  worker is guaranteed to hit the lock with the first one already
  inside the critical section.
- Cleanup deletes ``orders`` BEFORE ``products``/``stores`` because
  ``order_items.inventory_item_id`` and ``order_items.variant_id``
  use ``ON DELETE RESTRICT``; cascading from products/stores to
  inventory_items would otherwise be blocked by the order_items rows.

Race window flexibility
-----------------------
Several of these scenarios have two valid losing paths depending on
whether the loser's snapshot of the order was taken before or after
the winner committed (Postgres MVCC / READ COMMITTED). Assertions
accept either path as long as the final DB state is consistent and
the failure is a clean 422.
"""

import os
import threading
import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from app.core.security import hash_password
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import InventoryMovementType
from app.db.models import InventoryStatus
from app.db.models import Order
from app.db.models import OrderAuditLog
from app.db.models import OrderItem
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.orders import OrderCancelRequest
from app.schemas.orders import OrderCreate
from app.schemas.orders import OrderItemCreate
from app.schemas.orders import OrderStatusUpdate
from app.services import orders as svc


_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL_TEST",
    "postgresql+psycopg://nuberush:nuberush@localhost:5432/nuberush_test",
)

# Used to fail loudly on a hanging worker without blocking CI for too long.
_THREAD_TIMEOUT_SECONDS = 20


# --------------------------------------------------------------------- #
# Engine + setup helpers
# --------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def concurrency_engine() -> Engine:
    engine = create_engine(_TEST_DATABASE_URL, poolclass=NullPool, future=True)
    yield engine
    engine.dispose()


def _cleanup_world(engine: Engine, ids: dict) -> None:
    """Tear down a committed test world.

    Order matters because:
      - ``order_items.inventory_item_id`` and ``order_items.variant_id`` use
        ``ON DELETE RESTRICT`` so we must delete orders first (cascades to
        order_items and order_audit_logs).
      - Then deleting the product cascades to variants, inventory_items,
        inventory_logs.
      - Finally store + user.
    """
    with Session(engine) as db:
        db.execute(
            text("DELETE FROM orders WHERE store_id = :sid"),
            {"sid": ids["store_id"]},
        )
        if "product_id" in ids:
            db.execute(
                text("DELETE FROM products WHERE id = :pid"),
                {"pid": ids["product_id"]},
            )
        db.execute(
            text("DELETE FROM stores WHERE id = :sid"),
            {"sid": ids["store_id"]},
        )
        db.execute(
            text("DELETE FROM users WHERE id = :uid"),
            {"uid": ids["admin_id"]},
        )
        db.commit()


def _build_world(
    engine: Engine,
    *,
    quantity_on_hand: int,
    second_item: bool = False,
    second_qoh: int = 0,
) -> dict:
    """Create store + admin + product + variant + inventory item, all committed.

    Returns a dict of ids. When ``second_item=True`` it adds a second
    variant + inventory item (used by the multi-item rollback test).
    """
    with Session(engine, expire_on_commit=False) as db:
        store = Store(
            name="OrdConc", code=f"oc-{uuid.uuid4().hex[:8]}"
        )
        admin = User(
            full_name="Ord Conc Admin",
            email=f"oc-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("p"),
            role=UserRole.admin,
            store_id=None,
            is_active=True,
        )
        product = Product(
            name=f"OcP-{uuid.uuid4().hex[:6]}", category="vape"
        )
        db.add_all([store, admin, product])
        db.commit()
        for obj in (store, admin, product):
            db.refresh(obj)

        variant_a = ProductVariant(
            product_id=product.id,
            sku=f"OCA-{uuid.uuid4().hex[:8]}",
            price=Decimal("9.99"),
            is_active=True,
        )
        db.add(variant_a)
        db.commit()
        db.refresh(variant_a)

        item_a = InventoryItem(
            store_id=store.id,
            variant_id=variant_a.id,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=0,
            status=InventoryStatus.available,
        )
        db.add(item_a)
        db.commit()
        db.refresh(item_a)

        ids = {
            "store_id": store.id,
            "admin_id": admin.id,
            "product_id": product.id,
            "variant_a_id": variant_a.id,
            "item_a_id": item_a.id,
        }

        if second_item:
            variant_b = ProductVariant(
                product_id=product.id,
                sku=f"OCB-{uuid.uuid4().hex[:8]}",
                price=Decimal("4.50"),
                is_active=True,
            )
            db.add(variant_b)
            db.commit()
            db.refresh(variant_b)

            item_b = InventoryItem(
                store_id=store.id,
                variant_id=variant_b.id,
                quantity_on_hand=second_qoh,
                quantity_reserved=0,
                status=InventoryStatus.available,
            )
            db.add(item_b)
            db.commit()
            db.refresh(item_b)

            ids["variant_b_id"] = variant_b.id
            ids["item_b_id"] = item_b.id

        return ids


@pytest.fixture
def world_qoh1(concurrency_engine: Engine):
    """Single-variant world with qoh=1 (used by tests A and B-base)."""
    ids = _build_world(concurrency_engine, quantity_on_hand=1)
    yield ids
    _cleanup_world(concurrency_engine, ids)


@pytest.fixture
def world_qoh10(concurrency_engine: Engine):
    """Single-variant world with qoh=10 (used by tests B, C, D)."""
    ids = _build_world(concurrency_engine, quantity_on_hand=10)
    yield ids
    _cleanup_world(concurrency_engine, ids)


@pytest.fixture
def world_two_items(concurrency_engine: Engine):
    """Two-variant world: A qoh=10 (plenty), B qoh=1 (scarce)."""
    ids = _build_world(
        concurrency_engine,
        quantity_on_hand=10,
        second_item=True,
        second_qoh=1,
    )
    yield ids
    _cleanup_world(concurrency_engine, ids)


# --------------------------------------------------------------------- #
# Worker helpers
# --------------------------------------------------------------------- #


def _attempt_create_order(
    engine: Engine,
    store_id: uuid.UUID,
    payload: OrderCreate,
    actor_id: uuid.UUID,
    barrier: threading.Barrier,
    results: list,
    idx: int,
) -> None:
    """Worker: open own Session, sync at barrier, then create_order."""
    try:
        with Session(engine, expire_on_commit=False) as db:
            barrier.wait(timeout=_THREAD_TIMEOUT_SECONDS)
            try:
                order = svc.create_order(
                    db,
                    store_id,
                    payload,
                    actor_user_id=actor_id,
                )
                results[idx] = ("ok", order.id)
            except HTTPException as e:
                results[idx] = ("fail", (e.status_code, e.detail))
    except Exception as e:  # noqa: BLE001
        results[idx] = ("error", repr(e))


def _attempt_transition(
    engine: Engine,
    order_id: uuid.UUID,
    target: OrderStatus,
    actor_id: uuid.UUID,
    barrier: threading.Barrier,
    results: list,
    idx: int,
) -> None:
    try:
        with Session(engine, expire_on_commit=False) as db:
            barrier.wait(timeout=_THREAD_TIMEOUT_SECONDS)
            try:
                svc.transition_order_status(
                    db,
                    order_id,
                    OrderStatusUpdate(new_status=target),
                    actor_id,
                )
                results[idx] = ("ok", None)
            except HTTPException as e:
                results[idx] = ("fail", (e.status_code, e.detail))
    except Exception as e:  # noqa: BLE001
        results[idx] = ("error", repr(e))


def _attempt_cancel(
    engine: Engine,
    order_id: uuid.UUID,
    actor_id: uuid.UUID,
    barrier: threading.Barrier,
    results: list,
    idx: int,
) -> None:
    try:
        with Session(engine, expire_on_commit=False) as db:
            barrier.wait(timeout=_THREAD_TIMEOUT_SECONDS)
            try:
                svc.cancel_order(
                    db,
                    order_id,
                    OrderCancelRequest(reason=f"race-{idx}"),
                    actor_id,
                )
                results[idx] = ("ok", None)
            except HTTPException as e:
                results[idx] = ("fail", (e.status_code, e.detail))
    except Exception as e:  # noqa: BLE001
        results[idx] = ("error", repr(e))


def _run_workers(workers: list[tuple]) -> None:
    threads = [
        threading.Thread(target=fn, args=args, daemon=True)
        for fn, args in workers
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=_THREAD_TIMEOUT_SECONDS)
        if t.is_alive():
            pytest.fail(
                f"Worker thread did not complete within "
                f"{_THREAD_TIMEOUT_SECONDS}s — likely deadlock or hung lock."
            )


def _split_results(results: list) -> tuple[list, list, list]:
    ok = [r for r in results if r[0] == "ok"]
    fail = [r for r in results if r[0] == "fail"]
    err = [r for r in results if r[0] == "error"]
    return ok, fail, err


def _logs_for_item(db: Session, item_id: uuid.UUID) -> list[InventoryLog]:
    return list(
        db.scalars(
            select(InventoryLog).where(
                InventoryLog.inventory_item_id == item_id
            )
        ).all()
    )


def _orders_for_store(db: Session, store_id: uuid.UUID) -> list[Order]:
    return list(
        db.scalars(select(Order).where(Order.store_id == store_id)).all()
    )


def _audit_logs_for_order(
    db: Session, order_id: uuid.UUID
) -> list[OrderAuditLog]:
    return list(
        db.scalars(
            select(OrderAuditLog).where(
                OrderAuditLog.order_id == order_id
            )
        ).all()
    )


# --------------------------------------------------------------------- #
# A. Two orders compete for the only unit of stock
# --------------------------------------------------------------------- #


class TestConcurrentOrderCreate:
    def test_two_orders_compete_for_one_unit(
        self, concurrency_engine: Engine, world_qoh1: dict
    ):
        """qoh=1, two simultaneous create_order(qty=1, distinct keys).

        The row-lock taken by ``_reserve_inventory_locked`` must
        serialize the reservations: exactly one wins, the other returns
        422 with "insufficient stock" and rolls back its Order, its
        OrderItem, its inventory log and its audit log.
        """
        store_id = world_qoh1["store_id"]
        item_id = world_qoh1["item_a_id"]
        variant_id = world_qoh1["variant_a_id"]
        actor_id = world_qoh1["admin_id"]

        payload_a = OrderCreate(
            idempotency_key=f"a-{uuid.uuid4().hex[:8]}",
            items=[OrderItemCreate(variant_id=variant_id, quantity=1)],
        )
        payload_b = OrderCreate(
            idempotency_key=f"b-{uuid.uuid4().hex[:8]}",
            items=[OrderItemCreate(variant_id=variant_id, quantity=1)],
        )

        barrier = threading.Barrier(2)
        results: list = [None, None]

        _run_workers(
            [
                (
                    _attempt_create_order,
                    (concurrency_engine, store_id, payload_a, actor_id,
                     barrier, results, 0),
                ),
                (
                    _attempt_create_order,
                    (concurrency_engine, store_id, payload_b, actor_id,
                     barrier, results, 1),
                ),
            ]
        )

        ok, fail, err = _split_results(results)
        assert err == [], f"Unexpected errors: {err}"
        assert len(ok) == 1, (
            f"Expected exactly 1 success, got {len(ok)}: {results}"
        )
        assert len(fail) == 1

        status_code, detail = fail[0][1]
        assert status_code == 422
        detail_l = detail.lower()
        assert (
            "available" in detail_l or "stock" in detail_l
        ), f"Unexpected fail detail: {detail!r}"

        # Final DB state
        with Session(concurrency_engine) as db:
            item = db.get(InventoryItem, item_id)
            assert item.quantity_reserved == 1, (
                f"Expected qreserved=1, got {item.quantity_reserved}"
            )
            assert item.quantity_on_hand == 1, (
                f"Expected qoh=1 (untouched), got {item.quantity_on_hand}"
            )
            assert item.quantity_reserved >= 0
            assert item.quantity_on_hand >= 0

            orders = _orders_for_store(db, store_id)
            assert len(orders) == 1, f"Expected 1 order, got {len(orders)}"
            assert orders[0].status == OrderStatus.pending

            order_items = list(
                db.scalars(
                    select(OrderItem).where(
                        OrderItem.order_id == orders[0].id
                    )
                ).all()
            )
            assert len(order_items) == 1

            reservation_logs = [
                lg for lg in _logs_for_item(db, item_id)
                if lg.movement_type == InventoryMovementType.reservation
            ]
            assert len(reservation_logs) == 1, (
                f"Expected 1 reservation log, got {len(reservation_logs)}"
            )

            audit_created = [
                lg for lg in _audit_logs_for_order(db, orders[0].id)
                if lg.action == svc.ACTION_ORDER_CREATED
            ]
            assert len(audit_created) == 1


# --------------------------------------------------------------------- #
# B. Same idempotency_key concurrent → exactly one order, replay-safe
# --------------------------------------------------------------------- #


class TestConcurrentIdempotency:
    def test_same_key_concurrent_returns_one_order(
        self, concurrency_engine: Engine, world_qoh10: dict
    ):
        """Two simultaneous create_order calls with identical
        ``(store_id, idempotency_key, payload)``.

        The unique constraint ``uq_orders_store_idempotency_key`` makes
        the second insert fail; the service catches the IntegrityError,
        rolls back, re-fetches the existing order and returns it. Both
        callers therefore observe a successful create with the same
        ``order.id``. Inventory must reserve exactly once.
        """
        store_id = world_qoh10["store_id"]
        item_id = world_qoh10["item_a_id"]
        variant_id = world_qoh10["variant_a_id"]
        actor_id = world_qoh10["admin_id"]
        key = f"shared-{uuid.uuid4().hex[:8]}"

        payload = OrderCreate(
            idempotency_key=key,
            items=[OrderItemCreate(variant_id=variant_id, quantity=2)],
        )

        barrier = threading.Barrier(2)
        results: list = [None, None]

        _run_workers(
            [
                (
                    _attempt_create_order,
                    (concurrency_engine, store_id, payload, actor_id,
                     barrier, results, 0),
                ),
                (
                    _attempt_create_order,
                    (concurrency_engine, store_id, payload, actor_id,
                     barrier, results, 1),
                ),
            ]
        )

        ok, fail, err = _split_results(results)
        assert err == [], f"Unexpected errors: {err}"
        # Both must succeed (one created, one replayed). A 409 from the
        # service would be a regression: idempotency must be safe.
        assert len(ok) == 2, (
            f"Expected both threads to succeed (replay-safe), "
            f"got ok={len(ok)} fail={fail}"
        )
        # And both must have returned the SAME order id.
        assert ok[0][1] == ok[1][1], (
            f"Replay returned a different order: {ok}"
        )

        with Session(concurrency_engine) as db:
            orders = _orders_for_store(db, store_id)
            assert len(orders) == 1, (
                f"Expected exactly 1 order, got {len(orders)}"
            )
            order = orders[0]
            assert order.status == OrderStatus.pending

            order_items = list(
                db.scalars(
                    select(OrderItem).where(
                        OrderItem.order_id == order.id
                    )
                ).all()
            )
            assert len(order_items) == 1
            assert order_items[0].quantity == 2

            item = db.get(InventoryItem, item_id)
            # Reserved exactly once (2 units), not twice.
            assert item.quantity_reserved == 2, (
                f"Reservation duplicated: qreserved={item.quantity_reserved}"
            )
            assert item.quantity_on_hand == 10  # untouched

            reservation_logs = [
                lg for lg in _logs_for_item(db, item_id)
                if lg.movement_type == InventoryMovementType.reservation
            ]
            assert len(reservation_logs) == 1, (
                f"Expected 1 reservation log, got {len(reservation_logs)}"
            )

            audit_created = [
                lg for lg in _audit_logs_for_order(db, order.id)
                if lg.action == svc.ACTION_ORDER_CREATED
            ]
            assert len(audit_created) == 1


# --------------------------------------------------------------------- #
# C. Concurrent delivered transitions on the same order
# --------------------------------------------------------------------- #


def _make_ready_order(
    engine: Engine, world: dict, quantity: int = 2
) -> uuid.UUID:
    """Helper: create a pending order and walk it to status=ready,
    committed. Returns the order id.
    """
    with Session(engine, expire_on_commit=False) as db:
        order = svc.create_order(
            db,
            world["store_id"],
            OrderCreate(
                idempotency_key=f"setup-{uuid.uuid4().hex[:8]}",
                items=[
                    OrderItemCreate(
                        variant_id=world["variant_a_id"],
                        quantity=quantity,
                    )
                ],
            ),
            actor_user_id=world["admin_id"],
        )
        order_id = order.id

    actor = world["admin_id"]
    for s in (OrderStatus.accepted, OrderStatus.preparing, OrderStatus.ready):
        with Session(engine, expire_on_commit=False) as db:
            svc.transition_order_status(
                db, order_id,
                OrderStatusUpdate(new_status=s),
                actor,
            )
    return order_id


class TestConcurrentDelivered:
    def test_two_delivered_transitions_for_same_order(
        self, concurrency_engine: Engine, world_qoh10: dict
    ):
        """ready → delivered called twice concurrently.

        Exactly one consume must succeed; the other returns 422 either
        because:
          - it lost the inventory row-lock race and finds quantity_reserved
            already at 0 ("Cannot consume X units: only 0 are reserved.")
          - or because its READ COMMITTED snapshot of the order was taken
            after the winner committed, so it sees status=delivered and
            ``_assert_valid_transition(delivered, delivered)`` raises with
            "Invalid transition delivered -> delivered."
        Either path is valid; final state is identical.
        """
        order_id = _make_ready_order(
            concurrency_engine, world_qoh10, quantity=3
        )
        item_id = world_qoh10["item_a_id"]
        actor_id = world_qoh10["admin_id"]

        barrier = threading.Barrier(2)
        results: list = [None, None]

        _run_workers(
            [
                (
                    _attempt_transition,
                    (concurrency_engine, order_id, OrderStatus.delivered,
                     actor_id, barrier, results, 0),
                ),
                (
                    _attempt_transition,
                    (concurrency_engine, order_id, OrderStatus.delivered,
                     actor_id, barrier, results, 1),
                ),
            ]
        )

        ok, fail, err = _split_results(results)
        assert err == [], f"Unexpected errors: {err}"
        assert len(ok) == 1, f"Expected 1 success, got {len(ok)}: {results}"
        assert len(fail) == 1

        status_code, detail = fail[0][1]
        assert status_code == 422
        detail_l = detail.lower()
        assert (
            "reserved" in detail_l        # consume race lost
            or "transition" in detail_l   # status race lost
        ), f"Unexpected fail detail: {detail!r}"

        with Session(concurrency_engine) as db:
            item = db.get(InventoryItem, item_id)
            assert item.quantity_reserved == 0, (
                f"Expected qreserved=0, got {item.quantity_reserved}"
            )
            assert item.quantity_on_hand == 7, (
                f"qoh dropped twice: expected 10-3=7, got {item.quantity_on_hand}"
            )
            assert item.quantity_on_hand >= 0
            assert item.quantity_reserved >= 0

            sale_logs = [
                lg for lg in _logs_for_item(db, item_id)
                if lg.movement_type == InventoryMovementType.sale
            ]
            assert len(sale_logs) == 1, (
                f"Expected 1 sale log, got {len(sale_logs)}"
            )

            order = db.get(Order, order_id)
            assert order.status == OrderStatus.delivered

            audit_delivered = [
                lg for lg in _audit_logs_for_order(db, order_id)
                if lg.action == svc.ACTION_ORDER_DELIVERED
            ]
            assert len(audit_delivered) == 1, (
                f"Expected 1 order_delivered audit, got {len(audit_delivered)}"
            )


# --------------------------------------------------------------------- #
# D. Concurrent cancel on the same order
# --------------------------------------------------------------------- #


class TestConcurrentCancel:
    def test_two_cancels_for_same_pending_order(
        self, concurrency_engine: Engine, world_qoh10: dict
    ):
        """Two simultaneous cancel_order calls on a pending order.

        Exactly one cancel wins (releases reservation, sets canceled,
        writes audit). The loser returns 422 either because:
          - it lost the inventory row-lock race and finds quantity_reserved
            already at 0 ("Cannot release X units: only 0 are reserved.")
          - or because its order snapshot was taken after the winner's
            commit, so it sees status=canceled and the cancelable check
            raises with "Cannot cancel an order in status 'canceled'."
        """
        actor_id = world_qoh10["admin_id"]
        store_id = world_qoh10["store_id"]
        variant_id = world_qoh10["variant_a_id"]
        item_id = world_qoh10["item_a_id"]

        # Setup: create a pending order with reservation=2 and commit it.
        with Session(concurrency_engine, expire_on_commit=False) as db:
            order = svc.create_order(
                db,
                store_id,
                OrderCreate(
                    idempotency_key=f"cancelrace-{uuid.uuid4().hex[:8]}",
                    items=[
                        OrderItemCreate(variant_id=variant_id, quantity=2)
                    ],
                ),
                actor_user_id=actor_id,
            )
            order_id = order.id

        barrier = threading.Barrier(2)
        results: list = [None, None]

        _run_workers(
            [
                (
                    _attempt_cancel,
                    (concurrency_engine, order_id, actor_id,
                     barrier, results, 0),
                ),
                (
                    _attempt_cancel,
                    (concurrency_engine, order_id, actor_id,
                     barrier, results, 1),
                ),
            ]
        )

        ok, fail, err = _split_results(results)
        assert err == [], f"Unexpected errors: {err}"
        assert len(ok) == 1, f"Expected 1 success, got {len(ok)}: {results}"
        assert len(fail) == 1

        status_code, detail = fail[0][1]
        assert status_code == 422
        detail_l = detail.lower()
        assert (
            "release" in detail_l       # release race lost
            or "cancel" in detail_l     # status race lost
            or "transition" in detail_l
        ), f"Unexpected fail detail: {detail!r}"

        with Session(concurrency_engine) as db:
            item = db.get(InventoryItem, item_id)
            assert item.quantity_reserved == 0, (
                f"qreserved should be 0 after one release; "
                f"got {item.quantity_reserved} (double release?)"
            )
            assert item.quantity_on_hand == 10  # cancel does not touch qoh
            assert item.quantity_reserved >= 0
            assert item.quantity_on_hand >= 0

            cancellation_logs = [
                lg for lg in _logs_for_item(db, item_id)
                if lg.movement_type == InventoryMovementType.cancellation
            ]
            assert len(cancellation_logs) == 1, (
                f"Expected 1 cancellation log, got {len(cancellation_logs)}"
            )

            order = db.get(Order, order_id)
            assert order.status == OrderStatus.canceled
            assert order.canceled_at is not None

            audit_canceled = [
                lg for lg in _audit_logs_for_order(db, order_id)
                if lg.action == svc.ACTION_ORDER_CANCELED
            ]
            assert len(audit_canceled) == 1


# --------------------------------------------------------------------- #
# E. Multi-item concurrent create with partial failure
# --------------------------------------------------------------------- #


class TestConcurrentMultiItemPartialFailure:
    def test_two_multi_item_orders_atomic_under_contention(
        self, concurrency_engine: Engine, world_two_items: dict
    ):
        """Two simultaneous orders for ``[A=1, B=1]``, where B has only
        1 unit available. Exactly one order can secure both items.

        The losing thread serializes on item A's row lock first, may
        even succeed there (qoh=10 has plenty), then fails on item B
        because the winner already reserved B's only unit. The
        coordinator's rollback must discard the loser's A reservation
        too — atomicity.
        """
        store_id = world_two_items["store_id"]
        actor_id = world_two_items["admin_id"]
        v_a = world_two_items["variant_a_id"]
        v_b = world_two_items["variant_b_id"]
        i_a = world_two_items["item_a_id"]
        i_b = world_two_items["item_b_id"]

        payload_one = OrderCreate(
            idempotency_key=f"multi-1-{uuid.uuid4().hex[:8]}",
            items=[
                OrderItemCreate(variant_id=v_a, quantity=1),
                OrderItemCreate(variant_id=v_b, quantity=1),
            ],
        )
        payload_two = OrderCreate(
            idempotency_key=f"multi-2-{uuid.uuid4().hex[:8]}",
            items=[
                OrderItemCreate(variant_id=v_a, quantity=1),
                OrderItemCreate(variant_id=v_b, quantity=1),
            ],
        )

        barrier = threading.Barrier(2)
        results: list = [None, None]

        _run_workers(
            [
                (
                    _attempt_create_order,
                    (concurrency_engine, store_id, payload_one, actor_id,
                     barrier, results, 0),
                ),
                (
                    _attempt_create_order,
                    (concurrency_engine, store_id, payload_two, actor_id,
                     barrier, results, 1),
                ),
            ]
        )

        ok, fail, err = _split_results(results)
        assert err == [], f"Unexpected errors: {err}"
        assert len(ok) == 1, (
            f"Expected exactly 1 successful multi-item order, got {len(ok)}: "
            f"{results}"
        )
        assert len(fail) == 1

        status_code, detail = fail[0][1]
        assert status_code == 422
        detail_l = detail.lower()
        assert (
            "available" in detail_l or "stock" in detail_l
        ), f"Unexpected fail detail: {detail!r}"

        with Session(concurrency_engine) as db:
            item_a = db.get(InventoryItem, i_a)
            item_b = db.get(InventoryItem, i_b)

            # Atomicity: loser's reservation on A was rolled back along
            # with B. A is reserved exactly once (winner only).
            assert item_a.quantity_reserved == 1, (
                f"Item A reservation leaked from rolled-back order: "
                f"qreserved={item_a.quantity_reserved}"
            )
            assert item_b.quantity_reserved == 1
            assert item_a.quantity_on_hand == 10
            assert item_b.quantity_on_hand == 1
            assert item_a.quantity_on_hand >= 0
            assert item_a.quantity_reserved >= 0
            assert item_b.quantity_on_hand >= 0
            assert item_b.quantity_reserved >= 0

            orders = _orders_for_store(db, store_id)
            assert len(orders) == 1, (
                f"Loser's order leaked: expected 1 order, got {len(orders)}"
            )
            winner_order_id = orders[0].id

            order_items = list(
                db.scalars(
                    select(OrderItem).where(
                        OrderItem.order_id == winner_order_id
                    )
                ).all()
            )
            assert len(order_items) == 2

            # No orphan order_items from loser
            all_order_items = list(
                db.scalars(
                    select(OrderItem).where(
                        OrderItem.inventory_item_id.in_([i_a, i_b])
                    )
                ).all()
            )
            assert len(all_order_items) == 2

            # Reservation logs: exactly one per item (winner's two)
            res_logs_a = [
                lg for lg in _logs_for_item(db, i_a)
                if lg.movement_type == InventoryMovementType.reservation
            ]
            res_logs_b = [
                lg for lg in _logs_for_item(db, i_b)
                if lg.movement_type == InventoryMovementType.reservation
            ]
            assert len(res_logs_a) == 1, (
                f"Item A has {len(res_logs_a)} reservation logs; loser leaked"
            )
            assert len(res_logs_b) == 1

            # Audit log: exactly one order_created (winner's)
            audit_logs = list(
                db.scalars(
                    select(OrderAuditLog).where(
                        OrderAuditLog.store_id == store_id
                    )
                ).all()
            )
            audit_created = [
                lg for lg in audit_logs
                if lg.action == svc.ACTION_ORDER_CREATED
            ]
            assert len(audit_created) == 1, (
                f"Expected 1 order_created audit, got {len(audit_created)}"
            )
