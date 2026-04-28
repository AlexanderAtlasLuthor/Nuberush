"""Transactional refactor tests for inventory service (S5.3).

Validates the no-commit `_locked` helpers introduced for the orders
coordinator. Specifically proves:

  B. Helper-driven mutations roll back when the outer transaction
     rolls back. Logs roll back together.
  C. Multi-item failure rollbacks atomically (one item commits
     nothing if a later item fails).
  D. _consume_reserved_inventory_locked drops both qreserved and
     qoh, writes a sale log, and is reversible by outer rollback.
  E. Guardrails: invalid args, insufficient reservation, missing
     store match, wrong sellability state — all raise without
     committing.

Backward-compatibility for the public functions (A) is already
covered by the existing tests in test_inventory_services.py and
test_inventory_api.py.

Tests use a separate engine with NullPool (same pattern as
test_inventory_concurrency.py) so each session opens its own
connection and outer rollback semantics are observable.
"""

import os
import uuid
from decimal import Decimal
from typing import Generator

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
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.inventory import ReceiveStockRequest
from app.schemas.inventory import ReserveStockRequest
from app.schemas.inventory import SaleStockRequest
from app.services import inventory as inv


_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL_TEST",
    "postgresql+psycopg://nuberush:nuberush@localhost:5432/nuberush_test",
)


# --------------------------------------------------------------------- #
# Engine + setup fixtures
# --------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def tx_engine() -> Engine:
    engine = create_engine(_TEST_DATABASE_URL, poolclass=NullPool, future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def fresh_two_items(tx_engine: Engine) -> Generator[dict, None, None]:
    """Create one store + admin + product + two variants + two
    inventory items committed to the test DB. Yields ids and cleans
    up after the test."""
    with Session(tx_engine, expire_on_commit=False) as db:
        store = Store(name="TX", code=f"tx-{uuid.uuid4().hex[:8]}")
        admin = User(
            full_name="TX Admin",
            email=f"tx-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("p"),
            role=UserRole.admin,
            store_id=None,
            is_active=True,
        )
        product = Product(name=f"TX-{uuid.uuid4().hex[:6]}", category="vape")
        db.add_all([store, admin, product])
        db.commit()
        for o in (store, admin, product):
            db.refresh(o)

        v_a = ProductVariant(
            product_id=product.id,
            sku=f"TXA-{uuid.uuid4().hex[:8]}",
            price=Decimal("9.99"),
            is_active=True,
        )
        v_b = ProductVariant(
            product_id=product.id,
            sku=f"TXB-{uuid.uuid4().hex[:8]}",
            price=Decimal("9.99"),
            is_active=True,
        )
        db.add_all([v_a, v_b])
        db.commit()
        db.refresh(v_a)
        db.refresh(v_b)

        item_a = InventoryItem(
            store_id=store.id,
            variant_id=v_a.id,
            quantity_on_hand=10,
            quantity_reserved=0,
            status=InventoryStatus.available,
        )
        item_b = InventoryItem(
            store_id=store.id,
            variant_id=v_b.id,
            quantity_on_hand=1,  # intentionally scarce for the multi-item test
            quantity_reserved=0,
            status=InventoryStatus.available,
        )
        db.add_all([item_a, item_b])
        db.commit()
        db.refresh(item_a)
        db.refresh(item_b)

        ids = {
            "store_id": store.id,
            "admin_id": admin.id,
            "product_id": product.id,
            "item_a_id": item_a.id,
            "item_b_id": item_b.id,
        }

    yield ids

    # Cleanup via raw DELETE (rely on DB-level CASCADE chain).
    with Session(tx_engine) as db:
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


def _logs_for_item(db: Session, item_id: uuid.UUID) -> list[InventoryLog]:
    return list(
        db.scalars(
            select(InventoryLog).where(
                InventoryLog.inventory_item_id == item_id
            )
        ).all()
    )


# --------------------------------------------------------------------- #
# B. Helper internals do not commit — outer rollback reverts state
# --------------------------------------------------------------------- #


class TestLockedHelpersRollback:
    def test_reserve_locked_visible_inside_tx_then_rolled_back(
        self, tx_engine: Engine, fresh_two_items: dict
    ):
        item_id = fresh_two_items["item_a_id"]
        actor_id = fresh_two_items["admin_id"]

        # Open a session, call the helper, observe the in-tx mutation,
        # then rollback. The mutation must not persist; neither must
        # the inventory_log row.
        with Session(tx_engine, expire_on_commit=False) as db:
            inv._reserve_inventory_locked(
                db,
                item_id,
                ReserveStockRequest(quantity=4),
                actor_id,
            )
            db.flush()

            # Visible inside the open transaction
            item_in_tx = db.get(InventoryItem, item_id)
            assert item_in_tx.quantity_reserved == 4

            in_tx_logs = _logs_for_item(db, item_id)
            assert len(in_tx_logs) == 1
            assert in_tx_logs[0].movement_type == InventoryMovementType.reservation

            db.rollback()

        # New session — confirms the rollback erased everything
        with Session(tx_engine) as db2:
            after = db2.get(InventoryItem, item_id)
            assert after.quantity_reserved == 0
            assert after.quantity_on_hand == 10
            assert _logs_for_item(db2, item_id) == []

    def test_sell_locked_rolled_back_does_not_persist(
        self, tx_engine: Engine, fresh_two_items: dict
    ):
        item_id = fresh_two_items["item_a_id"]
        actor_id = fresh_two_items["admin_id"]

        with Session(tx_engine, expire_on_commit=False) as db:
            inv._sell_inventory_locked(
                db,
                item_id,
                SaleStockRequest(quantity=3),
                actor_id,
            )
            db.flush()
            assert db.get(InventoryItem, item_id).quantity_on_hand == 7
            db.rollback()

        with Session(tx_engine) as db2:
            assert db2.get(InventoryItem, item_id).quantity_on_hand == 10
            assert _logs_for_item(db2, item_id) == []


# --------------------------------------------------------------------- #
# C. Multi-item rollback: orders-style coordinator simulation
# --------------------------------------------------------------------- #


class TestMultiItemRollback:
    def test_partial_failure_rolls_back_both_items(
        self, tx_engine: Engine, fresh_two_items: dict
    ):
        """Simulate what the orders coordinator will do: reserve A
        (succeeds) and reserve B (fails because B has only 1 unit and
        we ask for 5). The whole transaction must roll back."""
        a_id = fresh_two_items["item_a_id"]
        b_id = fresh_two_items["item_b_id"]
        actor_id = fresh_two_items["admin_id"]

        with Session(tx_engine, expire_on_commit=False) as db:
            try:
                inv._reserve_inventory_locked(
                    db, a_id, ReserveStockRequest(quantity=2), actor_id
                )
                inv._reserve_inventory_locked(
                    db, b_id, ReserveStockRequest(quantity=5), actor_id
                )
                db.commit()
            except HTTPException as e:
                db.rollback()
                assert e.status_code == 422
            else:
                pytest.fail("Expected HTTPException for insufficient stock on B")

        # Verify NEITHER item was mutated and NO logs persist.
        with Session(tx_engine) as db2:
            a_after = db2.get(InventoryItem, a_id)
            b_after = db2.get(InventoryItem, b_id)
            assert a_after.quantity_reserved == 0, (
                "Item A reservation persisted despite item B failing"
            )
            assert b_after.quantity_reserved == 0
            assert _logs_for_item(db2, a_id) == []
            assert _logs_for_item(db2, b_id) == []

    def test_full_success_persists_both_items_atomically(
        self, tx_engine: Engine, fresh_two_items: dict
    ):
        """Mirror of the failure test: both reservations fit, single
        commit at the end persists both atomically with both logs."""
        a_id = fresh_two_items["item_a_id"]
        b_id = fresh_two_items["item_b_id"]
        actor_id = fresh_two_items["admin_id"]

        with Session(tx_engine, expire_on_commit=False) as db:
            inv._reserve_inventory_locked(
                db, a_id, ReserveStockRequest(quantity=3), actor_id
            )
            inv._reserve_inventory_locked(
                db, b_id, ReserveStockRequest(quantity=1), actor_id
            )
            db.commit()

        with Session(tx_engine) as db2:
            assert db2.get(InventoryItem, a_id).quantity_reserved == 3
            assert db2.get(InventoryItem, b_id).quantity_reserved == 1
            a_logs = _logs_for_item(db2, a_id)
            b_logs = _logs_for_item(db2, b_id)
            assert len(a_logs) == 1 and len(b_logs) == 1

            # Cleanup the persisted reservations so other tests in
            # this fixture lifetime see clean state.
            db2.execute(
                text(
                    "DELETE FROM inventory_logs "
                    "WHERE inventory_item_id IN (:a, :b)"
                ),
                {"a": a_id, "b": b_id},
            )
            db2.execute(
                text(
                    "UPDATE inventory_items SET quantity_reserved = 0 "
                    "WHERE id IN (:a, :b)"
                ),
                {"a": a_id, "b": b_id},
            )
            db2.commit()


# --------------------------------------------------------------------- #
# D. _consume_reserved_inventory_locked
# --------------------------------------------------------------------- #


class TestConsumeReservedInventoryLocked:
    def test_consume_after_reserve_drops_both_quantities(
        self, tx_engine: Engine, fresh_two_items: dict
    ):
        item_id = fresh_two_items["item_a_id"]
        store_id = fresh_two_items["store_id"]
        actor_id = fresh_two_items["admin_id"]
        order_id = uuid.uuid4()

        with Session(tx_engine, expire_on_commit=False) as db:
            # Reserve 4 units first (committed to set up the scenario)
            inv._reserve_inventory_locked(
                db, item_id, ReserveStockRequest(quantity=4), actor_id
            )
            db.commit()

        with Session(tx_engine, expire_on_commit=False) as db:
            # Consume 3 of the 4 reserved units, in this same tx.
            inv._consume_reserved_inventory_locked(
                db,
                item_id,
                3,
                actor_user_id=actor_id,
                order_id=order_id,
                expected_store_id=store_id,
                reason="qa consume",
            )
            db.commit()

        with Session(tx_engine) as db2:
            after = db2.get(InventoryItem, item_id)
            # qoh: 10 -> 10 (reserve does not touch on_hand) -> 7 (consume 3)
            assert after.quantity_on_hand == 7
            # qreserved: 0 -> 4 (reserve) -> 1 (consume 3)
            assert after.quantity_reserved == 1

            # The log produced by consume is movement_type=sale,
            # delta=-3, after=7, reference_type=order, reference_id=order_id
            sale_logs = [
                lg for lg in _logs_for_item(db2, item_id)
                if lg.movement_type == InventoryMovementType.sale
            ]
            assert len(sale_logs) == 1
            log = sale_logs[0]
            assert log.quantity_delta == -3
            assert log.quantity_after == 7
            assert log.reference_type == "order"
            assert log.reference_id == order_id

            # Cleanup so subsequent fixture state is consistent
            db2.execute(
                text(
                    "DELETE FROM inventory_logs WHERE inventory_item_id = :iid"
                ),
                {"iid": item_id},
            )
            db2.execute(
                text(
                    "UPDATE inventory_items SET quantity_on_hand = 10, "
                    "quantity_reserved = 0 WHERE id = :iid"
                ),
                {"iid": item_id},
            )
            db2.commit()

    def test_consume_locked_rolled_back_does_not_persist(
        self, tx_engine: Engine, fresh_two_items: dict
    ):
        item_id = fresh_two_items["item_a_id"]
        actor_id = fresh_two_items["admin_id"]
        order_id = uuid.uuid4()

        # Reserve via committed tx
        with Session(tx_engine, expire_on_commit=False) as db:
            inv._reserve_inventory_locked(
                db, item_id, ReserveStockRequest(quantity=2), actor_id
            )
            db.commit()

        # Consume in an open tx then rollback — should leave qreserved=2,
        # qoh=10 unchanged.
        with Session(tx_engine, expire_on_commit=False) as db:
            inv._consume_reserved_inventory_locked(
                db,
                item_id,
                2,
                actor_user_id=actor_id,
                order_id=order_id,
            )
            db.flush()
            mid = db.get(InventoryItem, item_id)
            assert mid.quantity_on_hand == 8
            assert mid.quantity_reserved == 0
            db.rollback()

        with Session(tx_engine) as db2:
            after = db2.get(InventoryItem, item_id)
            assert after.quantity_on_hand == 10
            assert after.quantity_reserved == 2

            sale_logs = [
                lg for lg in _logs_for_item(db2, item_id)
                if lg.movement_type == InventoryMovementType.sale
            ]
            assert sale_logs == []

            # Cleanup
            db2.execute(
                text(
                    "DELETE FROM inventory_logs WHERE inventory_item_id = :iid"
                ),
                {"iid": item_id},
            )
            db2.execute(
                text(
                    "UPDATE inventory_items SET quantity_on_hand = 10, "
                    "quantity_reserved = 0 WHERE id = :iid"
                ),
                {"iid": item_id},
            )
            db2.commit()


# --------------------------------------------------------------------- #
# E. Guardrails on _consume_reserved_inventory_locked
# --------------------------------------------------------------------- #


class TestConsumeReservedGuardrails:
    def test_quantity_zero_rejected(
        self, tx_engine: Engine, fresh_two_items: dict
    ):
        item_id = fresh_two_items["item_a_id"]
        order_id = uuid.uuid4()
        with Session(tx_engine) as db:
            with pytest.raises(HTTPException) as exc:
                inv._consume_reserved_inventory_locked(
                    db, item_id, 0,
                    actor_user_id=None,
                    order_id=order_id,
                )
            assert exc.value.status_code == 422

    def test_quantity_negative_rejected(
        self, tx_engine: Engine, fresh_two_items: dict
    ):
        item_id = fresh_two_items["item_a_id"]
        order_id = uuid.uuid4()
        with Session(tx_engine) as db:
            with pytest.raises(HTTPException) as exc:
                inv._consume_reserved_inventory_locked(
                    db, item_id, -1,
                    actor_user_id=None,
                    order_id=order_id,
                )
            assert exc.value.status_code == 422

    def test_consume_more_than_reserved_rejected(
        self, tx_engine: Engine, fresh_two_items: dict
    ):
        item_id = fresh_two_items["item_a_id"]
        actor_id = fresh_two_items["admin_id"]
        order_id = uuid.uuid4()
        with Session(tx_engine, expire_on_commit=False) as db:
            inv._reserve_inventory_locked(
                db, item_id, ReserveStockRequest(quantity=2), actor_id
            )
            db.commit()
        with Session(tx_engine) as db:
            with pytest.raises(HTTPException) as exc:
                inv._consume_reserved_inventory_locked(
                    db, item_id, 5,
                    actor_user_id=actor_id,
                    order_id=order_id,
                )
            assert exc.value.status_code == 422
            assert "reserved" in exc.value.detail.lower()
        # cleanup the reservation we made
        with Session(tx_engine) as db2:
            db2.execute(
                text(
                    "DELETE FROM inventory_logs WHERE inventory_item_id = :iid"
                ),
                {"iid": item_id},
            )
            db2.execute(
                text(
                    "UPDATE inventory_items SET quantity_reserved = 0 "
                    "WHERE id = :iid"
                ),
                {"iid": item_id},
            )
            db2.commit()

    def test_wrong_expected_store_rejected(
        self, tx_engine: Engine, fresh_two_items: dict
    ):
        item_id = fresh_two_items["item_a_id"]
        order_id = uuid.uuid4()
        wrong_store = uuid.uuid4()
        with Session(tx_engine) as db:
            with pytest.raises(HTTPException) as exc:
                inv._consume_reserved_inventory_locked(
                    db, item_id, 1,
                    actor_user_id=None,
                    order_id=order_id,
                    expected_store_id=wrong_store,
                )
            assert exc.value.status_code == 422
            assert "store" in exc.value.detail.lower()

    def test_consume_blocked_when_item_quarantined(
        self, tx_engine: Engine, fresh_two_items: dict
    ):
        """If a product gets banned between reserve and delivered,
        the inventory cascade flips status to quarantined, which makes
        `_assert_item_operable` reject the consume — defense-in-depth
        per orders_rules §7."""
        item_id = fresh_two_items["item_a_id"]
        actor_id = fresh_two_items["admin_id"]
        order_id = uuid.uuid4()

        # Reserve OK (status=available at reserve time)
        with Session(tx_engine, expire_on_commit=False) as db:
            inv._reserve_inventory_locked(
                db, item_id, ReserveStockRequest(quantity=2), actor_id
            )
            db.commit()

        # Flip status to quarantined (simulates the cascade fired by
        # set_product_compliance(banned)).
        with Session(tx_engine) as db:
            db.execute(
                text(
                    "UPDATE inventory_items SET status = 'quarantined' "
                    "WHERE id = :iid"
                ),
                {"iid": item_id},
            )
            db.commit()

        # Consume must now fail
        with Session(tx_engine) as db:
            with pytest.raises(HTTPException) as exc:
                inv._consume_reserved_inventory_locked(
                    db, item_id, 1,
                    actor_user_id=actor_id,
                    order_id=order_id,
                )
            assert exc.value.status_code == 422
            assert "quarantined" in exc.value.detail.lower()

        # Cleanup
        with Session(tx_engine) as db2:
            db2.execute(
                text(
                    "DELETE FROM inventory_logs WHERE inventory_item_id = :iid"
                ),
                {"iid": item_id},
            )
            db2.execute(
                text(
                    "UPDATE inventory_items SET quantity_reserved = 0, "
                    "status = 'available' WHERE id = :iid"
                ),
                {"iid": item_id},
            )
            db2.commit()
