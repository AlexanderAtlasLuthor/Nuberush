"""Concurrency tests for the inventory service layer (S4).

These tests bypass FastAPI and call the service layer directly so the
behaviour under test is the row-level lock taken by `_lock_inventory_item`
(SELECT ... FOR UPDATE), not the HTTP plumbing.

Critical infrastructure notes
-----------------------------
- A SQLAlchemy `Session` MUST NOT be shared across threads. Each
  worker creates its OWN Session bound to its OWN connection.
- The shared `db_session` fixture from conftest is intentionally NOT
  used here: it wraps everything in a single SAVEPOINT transaction
  that would defeat the row-lock test. We use a module-scoped engine
  with `NullPool` so every Session opens a fresh connection.
- Setup data is COMMITTED to the test database before workers start
  (workers query it via independent sessions). Each test fixture
  cleans up by deleting the rows it created.
- Threads synchronize start with `threading.Barrier` so the second
  worker is guaranteed to hit the lock with the first one already
  inside the critical section.
- `Thread.join(timeout=...)` followed by `is_alive()` makes a
  hanging worker fail loudly instead of silently passing.
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

from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import InventoryMovementType
from app.db.models import InventoryStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.inventory import ReserveStockRequest
from app.schemas.inventory import SaleStockRequest
from app.services import inventory as inv


_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL_TEST",
    "postgresql+psycopg://nuberush:nuberush@localhost:5432/nuberush_test",
)

# Used to fail loudly on a hanging worker without blocking CI for too long.
_THREAD_TIMEOUT_SECONDS = 15


# --------------------------------------------------------------------- #
# Engine + setup fixtures
# --------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def concurrency_engine(migrated_test_db: str) -> Engine:
    """Module-scoped engine with NullPool so each Session opens a fresh
    connection. Required to simulate truly concurrent transactions.
    """
    engine = create_engine(migrated_test_db, poolclass=NullPool, future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def fresh_item(concurrency_engine: Engine):
    """Create store + admin + product + active variant + inventory item
    (qoh=1, qreserved=0, status=available) committed to the test DB so
    concurrent workers can see them via their own sessions.

    Yields a dict with the relevant ids. Cleans up after the test.
    """
    with Session(concurrency_engine, expire_on_commit=False) as db:
        store = Store(name="Conc", code=f"conc-{uuid.uuid4().hex[:8]}")
        admin = User(
            full_name="Conc Admin",
            email=f"conc-{uuid.uuid4().hex[:8]}@example.com",
            role=UserRole.admin,
            store_id=None,
            is_active=True,
        )
        product = Product(name=f"Conc-{uuid.uuid4().hex[:6]}", category="vape")
        db.add_all([store, admin, product])
        db.commit()
        for obj in (store, admin, product):
            db.refresh(obj)

        variant = ProductVariant(
            product_id=product.id,
            sku=f"CONC-{uuid.uuid4().hex[:8]}",
            price=Decimal("9.99"),
            is_active=True,
        )
        db.add(variant)
        db.commit()
        db.refresh(variant)

        item = InventoryItem(
            store_id=store.id,
            variant_id=variant.id,
            quantity_on_hand=1,
            quantity_reserved=0,
            status=InventoryStatus.available,
        )
        db.add(item)
        db.commit()
        db.refresh(item)

        ids = {
            "store_id": store.id,
            "admin_id": admin.id,
            "product_id": product.id,
            "variant_id": variant.id,
            "item_id": item.id,
        }

    yield ids

    # Cleanup. Use raw DELETE statements so we rely on the DB-level
    # ON DELETE CASCADE FKs declared in S1 and bypass SQLAlchemy's
    # ORM cascade behaviour, which would otherwise try to UPDATE
    # product_variants.product_id = NULL (a NOT NULL column) before
    # the SQL DELETE actually fires.
    with Session(concurrency_engine) as db:
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


# --------------------------------------------------------------------- #
# Worker helpers
# --------------------------------------------------------------------- #


def _attempt_sale(
    engine: Engine,
    item_id: uuid.UUID,
    actor_id: uuid.UUID,
    barrier: threading.Barrier,
    results: list,
    idx: int,
) -> None:
    """Worker: open own Session, sync at barrier, then sell qty=1."""
    try:
        with Session(engine, expire_on_commit=False) as db:
            barrier.wait(timeout=_THREAD_TIMEOUT_SECONDS)
            try:
                inv.sell_inventory(
                    db,
                    item_id,
                    SaleStockRequest(quantity=1),
                    actor_id,
                )
                results[idx] = ("ok", None)
            except HTTPException as e:
                results[idx] = ("fail", (e.status_code, e.detail))
    except Exception as e:  # noqa: BLE001
        results[idx] = ("error", repr(e))


def _attempt_reserve(
    engine: Engine,
    item_id: uuid.UUID,
    actor_id: uuid.UUID,
    barrier: threading.Barrier,
    results: list,
    idx: int,
) -> None:
    """Worker: open own Session, sync at barrier, then reserve qty=1."""
    try:
        with Session(engine, expire_on_commit=False) as db:
            barrier.wait(timeout=_THREAD_TIMEOUT_SECONDS)
            try:
                inv.reserve_inventory(
                    db,
                    item_id,
                    ReserveStockRequest(quantity=1),
                    actor_id,
                )
                results[idx] = ("ok", None)
            except HTTPException as e:
                results[idx] = ("fail", (e.status_code, e.detail))
    except Exception as e:  # noqa: BLE001
        results[idx] = ("error", repr(e))


def _run_workers(
    workers: list[tuple[callable, tuple]],
) -> None:
    """Start each (target, args) pair in its own thread, join with a
    timeout, and fail the test loudly on a hang."""
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


# --------------------------------------------------------------------- #
# Concurrent sales
# --------------------------------------------------------------------- #


class TestConcurrentSales:
    def test_two_concurrent_sales_for_one_unit(
        self, concurrency_engine: Engine, fresh_item: dict
    ):
        """qoh=1, two simultaneous sells of qty=1.

        The row-lock taken by `_lock_inventory_item` must serialize
        the sales: exactly one wins (qoh→0), the other reads qoh=0
        after acquiring the lock and returns 422. Logs must reflect
        exactly one successful sale.
        """
        item_id = fresh_item["item_id"]
        actor_id = fresh_item["admin_id"]
        barrier = threading.Barrier(2)
        results: list = [None, None]

        _run_workers(
            [
                (
                    _attempt_sale,
                    (concurrency_engine, item_id, actor_id, barrier, results, 0),
                ),
                (
                    _attempt_sale,
                    (concurrency_engine, item_id, actor_id, barrier, results, 1),
                ),
            ]
        )

        ok, fail, err = _split_results(results)
        assert err == [], f"Unexpected errors: {err}"
        assert len(ok) == 1, f"Expected 1 success, got {len(ok)} — results={results}"
        assert len(fail) == 1, (
            f"Expected 1 failure, got {len(fail)} — results={results}"
        )

        # Failure is the standard "insufficient stock" 422 — never a 500
        # or a constraint-violation leak.
        status_code, detail = fail[0][1]
        assert status_code == 422, f"Expected 422, got {status_code}"
        assert (
            "available" in detail.lower() or "stock" in detail.lower()
        ), f"Unexpected failure detail: {detail!r}"

        # Final DB state
        with Session(concurrency_engine) as db:
            item = db.get(InventoryItem, item_id)
            assert item.quantity_on_hand == 0, (
                f"Final qoh expected 0, got {item.quantity_on_hand}"
            )
            assert item.quantity_reserved == 0
            assert item.quantity_on_hand >= 0  # never negative

            logs = list(
                db.scalars(
                    select(InventoryLog).where(
                        InventoryLog.inventory_item_id == item_id
                    )
                ).all()
            )
            sale_logs = [
                lg for lg in logs
                if lg.movement_type == InventoryMovementType.sale
            ]
            assert len(sale_logs) == 1, (
                f"Expected exactly 1 sale log, got {len(sale_logs)}"
            )
            assert sale_logs[0].quantity_delta == -1
            assert sale_logs[0].quantity_after == 0


# --------------------------------------------------------------------- #
# Concurrent reservations
# --------------------------------------------------------------------- #


class TestConcurrentReservations:
    def test_two_concurrent_reservations_for_one_unit(
        self, concurrency_engine: Engine, fresh_item: dict
    ):
        """qoh=1, qreserved=0, two simultaneous reserves of qty=1.

        Same locking guarantee: exactly one reservation wins
        (qreserved→1), the other returns 422 because available drops
        to 0 after the first commit. qoh remains 1 (reservations do
        not move physical stock).
        """
        item_id = fresh_item["item_id"]
        actor_id = fresh_item["admin_id"]
        barrier = threading.Barrier(2)
        results: list = [None, None]

        _run_workers(
            [
                (
                    _attempt_reserve,
                    (concurrency_engine, item_id, actor_id, barrier, results, 0),
                ),
                (
                    _attempt_reserve,
                    (concurrency_engine, item_id, actor_id, barrier, results, 1),
                ),
            ]
        )

        ok, fail, err = _split_results(results)
        assert err == [], f"Unexpected errors: {err}"
        assert len(ok) == 1, (
            f"Expected 1 success, got {len(ok)} — results={results}"
        )
        assert len(fail) == 1

        status_code, detail = fail[0][1]
        assert status_code == 422
        assert (
            "available" in detail.lower() or "stock" in detail.lower()
        )

        with Session(concurrency_engine) as db:
            item = db.get(InventoryItem, item_id)
            # qoh untouched, qreserved=1, available=0
            assert item.quantity_on_hand == 1
            assert item.quantity_reserved == 1
            assert item.quantity_on_hand - item.quantity_reserved == 0

            logs = list(
                db.scalars(
                    select(InventoryLog).where(
                        InventoryLog.inventory_item_id == item_id
                    )
                ).all()
            )
            reservation_logs = [
                lg for lg in logs
                if lg.movement_type == InventoryMovementType.reservation
            ]
            assert len(reservation_logs) == 1, (
                f"Expected exactly 1 reservation log, got {len(reservation_logs)}"
            )
            assert reservation_logs[0].quantity_delta == 1
            assert reservation_logs[0].quantity_after == 1


# --------------------------------------------------------------------- #
# Sale vs reserve race
# --------------------------------------------------------------------- #


class TestConcurrentSaleVsReserve:
    def test_sale_and_reserve_race_for_one_unit(
        self, concurrency_engine: Engine, fresh_item: dict
    ):
        """qoh=1: one thread sells, the other reserves, simultaneously.

        Either operation removes the unit from the available pool, so
        whichever wins, the other must return 422. Defense in depth:
          - if the sale wins  →  qoh=0, qreserved=0, exactly 1 sale log
          - if the reserve wins → qoh=1, qreserved=1, exactly 1
            reservation log
        Either way, exactly one successful claim and no negative state.
        """
        item_id = fresh_item["item_id"]
        actor_id = fresh_item["admin_id"]
        barrier = threading.Barrier(2)
        results: list = [None, None]

        _run_workers(
            [
                (
                    _attempt_sale,
                    (concurrency_engine, item_id, actor_id, barrier, results, 0),
                ),
                (
                    _attempt_reserve,
                    (concurrency_engine, item_id, actor_id, barrier, results, 1),
                ),
            ]
        )

        ok, fail, err = _split_results(results)
        assert err == [], f"Unexpected errors: {err}"
        assert len(ok) == 1, (
            f"Expected exactly 1 successful claim, got {len(ok)} — results={results}"
        )
        assert len(fail) == 1

        status_code, _ = fail[0][1]
        assert status_code == 422

        # Determine which operation won by inspecting which result was ok
        sale_won = results[0][0] == "ok"
        reserve_won = results[1][0] == "ok"
        assert sale_won != reserve_won, "Exactly one operation must win"

        with Session(concurrency_engine) as db:
            item = db.get(InventoryItem, item_id)
            available = item.quantity_on_hand - item.quantity_reserved
            assert available >= 0, (
                f"Available stock went negative: qoh={item.quantity_on_hand}, "
                f"qreserved={item.quantity_reserved}"
            )

            logs = list(
                db.scalars(
                    select(InventoryLog).where(
                        InventoryLog.inventory_item_id == item_id
                    )
                ).all()
            )

            if sale_won:
                assert item.quantity_on_hand == 0
                assert item.quantity_reserved == 0
                sale_logs = [
                    lg for lg in logs
                    if lg.movement_type == InventoryMovementType.sale
                ]
                assert len(sale_logs) == 1
                # No reservation log since reserve failed and rolled back
                reservation_logs = [
                    lg for lg in logs
                    if lg.movement_type == InventoryMovementType.reservation
                ]
                assert reservation_logs == []
            else:
                assert item.quantity_on_hand == 1
                assert item.quantity_reserved == 1
                reservation_logs = [
                    lg for lg in logs
                    if lg.movement_type == InventoryMovementType.reservation
                ]
                assert len(reservation_logs) == 1
                # No sale log since sell failed and rolled back
                sale_logs = [
                    lg for lg in logs
                    if lg.movement_type == InventoryMovementType.sale
                ]
                assert sale_logs == []
