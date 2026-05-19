"""Service-layer tests for the orders coordinator (S5.5).

Exercises ``app.services.orders`` against the real test DB via the
``db_session`` fixture from conftest. Covers:

  A. Create order
  B. Idempotency
  C. Atomic rollback (multi-item failure)
  D. Cancel
  E. Delivered
  F. Return
  G. State machine
  H. Compliance/sellability
  I. Cross-store safety
  J. Money

API/router-level tests live in their own files. This file stays at
the service layer — it imports the service module directly and never
touches FastAPI's TestClient.

Atomicity tests that need to observe the service's own commit/rollback
boundary use a separate engine with NullPool (mirroring
``test_inventory_transactional.py``) so the service's
``db.commit()``/``db.rollback()`` actually exercise real transaction
boundaries instead of the SAVEPOINT-on-commit wrapper from the
shared ``db_session`` fixture.
"""

import os
import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from typing import Callable
from typing import Generator

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from tests.helpers.auth import make_password_hash
from app.db.models import ComplianceStatus
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
from app.schemas.orders import OrderReturnRequest
from app.schemas.orders import OrderStatusUpdate
from app.services import orders as svc


# --------------------------------------------------------------------- #
# Fixtures (transactional db_session — covers most cases)
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(code_prefix: str = "ord") -> Store:
        store = Store(name=f"Ord-{code_prefix}", code=f"{code_prefix}-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_admin(db_session: Session) -> Callable[..., User]:
    def _create() -> User:
        admin = User(
            full_name="Ord Svc Admin",
            email=f"osa-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=make_password_hash("supersecret123"),
            role=UserRole.admin,
            store_id=None,
            is_active=True,
        )
        db_session.add(admin)
        db_session.commit()
        db_session.refresh(admin)
        return admin

    return _create


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create(
        compliance_status: ComplianceStatus = ComplianceStatus.allowed,
        allowed_for_sale: bool = True,
        is_active: bool = True,
    ) -> Product:
        product = Product(
            name=f"OrdP-{uuid.uuid4().hex[:6]}",
            category="vape",
            compliance_status=compliance_status,
            allowed_for_sale=allowed_for_sale,
            is_active=is_active,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    return _create


@pytest.fixture
def make_variant(
    db_session: Session, make_product
) -> Callable[..., ProductVariant]:
    def _create(
        product: Product | None = None,
        is_active: bool = True,
        price: Decimal = Decimal("9.99"),
    ) -> ProductVariant:
        prod = product if product is not None else make_product()
        variant = ProductVariant(
            product_id=prod.id,
            sku=f"SKU-{uuid.uuid4().hex[:8]}",
            price=price,
            is_active=is_active,
        )
        db_session.add(variant)
        db_session.commit()
        db_session.refresh(variant)
        return variant

    return _create


@pytest.fixture
def make_item(
    db_session: Session, make_store, make_variant
) -> Callable[..., InventoryItem]:
    def _create(
        store: Store | None = None,
        variant: ProductVariant | None = None,
        quantity_on_hand: int = 10,
        quantity_reserved: int = 0,
        status: InventoryStatus = InventoryStatus.available,
    ) -> InventoryItem:
        s = store if store is not None else make_store()
        v = variant if variant is not None else make_variant()
        item = InventoryItem(
            store_id=s.id,
            variant_id=v.id,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            status=status,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        return item

    return _create


def _logs_for_item(db: Session, item_id: uuid.UUID) -> list[InventoryLog]:
    return list(
        db.scalars(
            select(InventoryLog).where(
                InventoryLog.inventory_item_id == item_id
            )
        ).all()
    )


def _audit_logs_for_order(db: Session, order_id: uuid.UUID) -> list[OrderAuditLog]:
    return list(
        db.scalars(
            select(OrderAuditLog)
            .where(OrderAuditLog.order_id == order_id)
            .order_by(OrderAuditLog.created_at.asc())
        ).all()
    )


def _set_order_created_at(
    db: Session, order_id: uuid.UUID, created_at: datetime
) -> None:
    order = db.get(Order, order_id)
    assert order is not None
    order.created_at = created_at
    db.add(order)
    db.commit()


def _assert_order_items_enriched(order: Order) -> None:
    assert order.items
    for item in order.items:
        assert item.variant is not None
        assert item.variant_id == item.variant.id
        assert item.variant.sku
        assert item.variant.product is not None
        assert item.variant.product.id == item.variant.product_id
        assert item.variant.product.name


# --------------------------------------------------------------------- #
# A. Create order
# --------------------------------------------------------------------- #


class TestCreateOrder:
    def test_create_order_persists_with_pending_status(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()

        order = svc.create_order(
            db_session,
            store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=2)],
            ),
            actor_user_id=admin.id,
        )

        assert order.status == OrderStatus.pending
        assert order.store_id == store.id
        assert order.id is not None

    def test_create_order_creates_order_items(
        self, db_session: Session, make_store, make_variant, make_item, make_admin
    ):
        store = make_store()
        v1 = make_variant(price=Decimal("4.99"))
        v2 = make_variant(price=Decimal("12.50"))
        i1 = make_item(store=store, variant=v1, quantity_on_hand=10)
        i2 = make_item(store=store, variant=v2, quantity_on_hand=5)
        admin = make_admin()

        order = svc.create_order(
            db_session,
            store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[
                    OrderItemCreate(variant_id=v1.id, quantity=2),
                    OrderItemCreate(variant_id=v2.id, quantity=1),
                ],
            ),
            actor_user_id=admin.id,
        )

        assert len(order.items) == 2
        items_by_variant = {oi.variant_id: oi for oi in order.items}
        assert v1.id in items_by_variant
        assert v2.id in items_by_variant
        assert items_by_variant[v1.id].quantity == 2
        assert items_by_variant[v2.id].quantity == 1

    def test_create_order_resolves_inventory_item_id(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()

        order = svc.create_order(
            db_session,
            store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )

        assert order.items[0].inventory_item_id == item.id

    def test_create_order_reserves_inventory(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10, quantity_reserved=0)
        admin = make_admin()

        svc.create_order(
            db_session,
            store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=3)],
            ),
            actor_user_id=admin.id,
        )

        db_session.refresh(item)
        # Reserve raises quantity_reserved but never touches quantity_on_hand
        assert item.quantity_reserved == 3
        assert item.quantity_on_hand == 10

    def test_create_order_snapshots_unit_price_from_db(
        self, db_session: Session, make_store, make_variant, make_item, make_admin
    ):
        store = make_store()
        variant = make_variant(price=Decimal("7.77"))
        item = make_item(store=store, variant=variant, quantity_on_hand=10)
        admin = make_admin()

        order = svc.create_order(
            db_session,
            store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=variant.id, quantity=2)],
            ),
            actor_user_id=admin.id,
        )

        oi = order.items[0]
        assert oi.unit_price == Decimal("7.77")
        assert oi.line_total == Decimal("15.54")

    def test_create_order_calculates_totals_server_side(
        self, db_session: Session, make_store, make_variant, make_item, make_admin
    ):
        store = make_store()
        v1 = make_variant(price=Decimal("3.00"))
        v2 = make_variant(price=Decimal("5.00"))
        make_item(store=store, variant=v1, quantity_on_hand=10)
        make_item(store=store, variant=v2, quantity_on_hand=10)
        admin = make_admin()

        order = svc.create_order(
            db_session,
            store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[
                    OrderItemCreate(variant_id=v1.id, quantity=2),  # 6.00
                    OrderItemCreate(variant_id=v2.id, quantity=1),  # 5.00
                ],
            ),
            actor_user_id=admin.id,
        )

        # subtotal = 6.00 + 5.00 = 11.00; tax=0; total=subtotal
        assert order.subtotal_amount == Decimal("11.00")
        assert order.tax_amount == Decimal("0.00")
        assert order.total_amount == Decimal("11.00")

    def test_create_order_writes_order_created_audit_log(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()

        order = svc.create_order(
            db_session,
            store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )

        logs = _audit_logs_for_order(db_session, order.id)
        assert len(logs) == 1
        log = logs[0]
        assert log.action == svc.ACTION_ORDER_CREATED
        assert log.previous_status is None
        assert log.new_status == OrderStatus.pending
        assert log.performed_by_user_id == admin.id
        assert log.store_id == store.id

    def test_create_order_writes_one_inventory_log_per_line(
        self, db_session: Session, make_store, make_variant, make_item, make_admin
    ):
        store = make_store()
        v1 = make_variant()
        v2 = make_variant()
        i1 = make_item(store=store, variant=v1, quantity_on_hand=10)
        i2 = make_item(store=store, variant=v2, quantity_on_hand=10)
        admin = make_admin()

        svc.create_order(
            db_session,
            store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[
                    OrderItemCreate(variant_id=v1.id, quantity=2),
                    OrderItemCreate(variant_id=v2.id, quantity=1),
                ],
            ),
            actor_user_id=admin.id,
        )

        logs1 = _logs_for_item(db_session, i1.id)
        logs2 = _logs_for_item(db_session, i2.id)
        assert len(logs1) == 1
        assert logs1[0].movement_type == InventoryMovementType.reservation
        assert logs1[0].quantity_delta == 2
        assert len(logs2) == 1
        assert logs2[0].movement_type == InventoryMovementType.reservation
        assert logs2[0].quantity_delta == 1

    def test_create_order_with_notes_persists_notes(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        admin = make_admin()

        order = svc.create_order(
            db_session,
            store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
                notes="walk-in",
            ),
            actor_user_id=admin.id,
        )

        assert order.notes == "walk-in"

    def test_create_order_with_missing_store_raises_404(
        self, db_session: Session, make_admin
    ):
        admin = make_admin()
        with pytest.raises(HTTPException) as exc:
            svc.create_order(
                db_session,
                uuid.uuid4(),
                OrderCreate(
                    idempotency_key="k-1",
                    items=[
                        OrderItemCreate(variant_id=uuid.uuid4(), quantity=1)
                    ],
                ),
                actor_user_id=admin.id,
            )
        assert exc.value.status_code == 404

    def test_create_order_with_missing_inventory_returns_422(
        self, db_session: Session, make_store, make_variant, make_admin
    ):
        store = make_store()
        # Variant exists but no inventory_item for (store, variant)
        variant = make_variant()
        admin = make_admin()

        with pytest.raises(HTTPException) as exc:
            svc.create_order(
                db_session,
                store.id,
                OrderCreate(
                    idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                    items=[OrderItemCreate(variant_id=variant.id, quantity=1)],
                ),
                actor_user_id=admin.id,
            )
        assert exc.value.status_code == 422
        assert "inventory" in exc.value.detail.lower()


# --------------------------------------------------------------------- #
# B. Idempotency
# --------------------------------------------------------------------- #


class TestIdempotency:
    def test_replay_returns_existing_order(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        key = f"k-{uuid.uuid4().hex[:8]}"

        first = svc.create_order(
            db_session,
            store.id,
            OrderCreate(
                idempotency_key=key,
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=2)],
            ),
            actor_user_id=admin.id,
        )
        replay = svc.create_order(
            db_session,
            store.id,
            OrderCreate(
                idempotency_key=key,
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=2)],
            ),
            actor_user_id=admin.id,
        )

        assert replay.id == first.id

    def test_replay_does_not_duplicate_reservations(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        key = f"k-{uuid.uuid4().hex[:8]}"

        svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=key,
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=3)],
            ),
            actor_user_id=admin.id,
        )
        svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=key,
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=3)],
            ),
            actor_user_id=admin.id,
        )

        db_session.refresh(item)
        # Quantity reserved should only reflect one reservation, not two.
        assert item.quantity_reserved == 3

    def test_replay_does_not_duplicate_order_items(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        key = f"k-{uuid.uuid4().hex[:8]}"

        first = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=key,
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )
        svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=key,
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )

        items = list(
            db_session.scalars(
                select(OrderItem).where(OrderItem.order_id == first.id)
            ).all()
        )
        assert len(items) == 1

    def test_replay_does_not_duplicate_audit_logs(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        key = f"k-{uuid.uuid4().hex[:8]}"

        first = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=key,
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )
        svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=key,
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )

        logs = _audit_logs_for_order(db_session, first.id)
        assert len(logs) == 1


# --------------------------------------------------------------------- #
# C. Atomic rollback (multi-item failure)
#
# This needs an isolated engine so the service's own commit/rollback
# boundary is observable. The shared db_session uses SAVEPOINT-on-commit
# which keeps the outer transaction alive across service-internal rollbacks.
# --------------------------------------------------------------------- #


_TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL_TEST",
    "postgresql+psycopg://nuberush:nuberush@localhost:5432/nuberush_test",
)


@pytest.fixture(scope="module")
def tx_engine(migrated_test_db: str) -> Generator[Engine, None, None]:
    engine = create_engine(migrated_test_db, poolclass=NullPool, future=True)
    yield engine
    engine.dispose()


@pytest.fixture
def tx_world(tx_engine: Engine) -> Generator[dict, None, None]:
    """Real-DB world with two variants/items: A (plenty) and B (scarce).

    Used for atomicity tests where we want the service's commit/rollback
    boundary to be the actual DB transaction boundary.
    """
    with Session(tx_engine, expire_on_commit=False) as db:
        store = Store(name="ATX", code=f"atx-{uuid.uuid4().hex[:8]}")
        admin = User(
            full_name="ATX Admin",
            email=f"atx-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=make_password_hash("p"),
            role=UserRole.admin,
            store_id=None,
            is_active=True,
        )
        product = Product(name=f"ATX-{uuid.uuid4().hex[:6]}", category="vape")
        db.add_all([store, admin, product])
        db.commit()
        for o in (store, admin, product):
            db.refresh(o)

        v_a = ProductVariant(
            product_id=product.id,
            sku=f"ATXA-{uuid.uuid4().hex[:8]}",
            price=Decimal("9.99"),
            is_active=True,
        )
        v_b = ProductVariant(
            product_id=product.id,
            sku=f"ATXB-{uuid.uuid4().hex[:8]}",
            price=Decimal("4.50"),
            is_active=True,
        )
        db.add_all([v_a, v_b])
        db.commit()
        db.refresh(v_a)
        db.refresh(v_b)

        i_a = InventoryItem(
            store_id=store.id,
            variant_id=v_a.id,
            quantity_on_hand=10,
            quantity_reserved=0,
            status=InventoryStatus.available,
        )
        i_b = InventoryItem(
            store_id=store.id,
            variant_id=v_b.id,
            quantity_on_hand=1,  # scarce on purpose
            quantity_reserved=0,
            status=InventoryStatus.available,
        )
        db.add_all([i_a, i_b])
        db.commit()
        db.refresh(i_a)
        db.refresh(i_b)

        ids = {
            "store_id": store.id,
            "admin_id": admin.id,
            "product_id": product.id,
            "v_a_id": v_a.id,
            "v_b_id": v_b.id,
            "i_a_id": i_a.id,
            "i_b_id": i_b.id,
        }

    yield ids

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


class TestAtomicRollback:
    def test_multi_item_failure_rolls_back_everything(
        self, tx_engine: Engine, tx_world: dict
    ):
        """If item B fails because of insufficient stock, the whole
        transaction must roll back: no order row, no order_items, no
        reservation on item A, no inventory_logs, no order_audit_logs.
        """
        store_id = tx_world["store_id"]
        admin_id = tx_world["admin_id"]
        v_a = tx_world["v_a_id"]
        v_b = tx_world["v_b_id"]
        i_a = tx_world["i_a_id"]
        i_b = tx_world["i_b_id"]
        key = f"k-{uuid.uuid4().hex[:8]}"

        with Session(tx_engine, expire_on_commit=False) as db:
            with pytest.raises(HTTPException) as exc:
                svc.create_order(
                    db,
                    store_id,
                    OrderCreate(
                        idempotency_key=key,
                        items=[
                            # A succeeds (qty 1 of 10 on hand)
                            OrderItemCreate(variant_id=v_a, quantity=1),
                            # B fails: only 1 on hand, request 5
                            OrderItemCreate(variant_id=v_b, quantity=5),
                        ],
                    ),
                    actor_user_id=admin_id,
                )
            assert exc.value.status_code == 422

        with Session(tx_engine) as db2:
            # No order persisted
            ord_rows = list(
                db2.scalars(
                    select(Order).where(Order.idempotency_key == key)
                ).all()
            )
            assert ord_rows == []

            # No order_items
            oi_count = db2.scalar(
                select(OrderItem).where(
                    OrderItem.variant_id.in_([v_a, v_b])
                ).limit(1)
            )
            # If oi_count is None nothing exists
            assert oi_count is None

            # No reservation on A or B
            a_after = db2.get(InventoryItem, i_a)
            b_after = db2.get(InventoryItem, i_b)
            assert a_after.quantity_reserved == 0
            assert b_after.quantity_reserved == 0
            assert a_after.quantity_on_hand == 10
            assert b_after.quantity_on_hand == 1

            # No inventory logs
            assert _logs_for_item(db2, i_a) == []
            assert _logs_for_item(db2, i_b) == []

            # No audit logs (no order existed)
            audit_rows = list(
                db2.scalars(
                    select(OrderAuditLog).where(
                        OrderAuditLog.store_id == store_id
                    )
                ).all()
            )
            assert audit_rows == []


# --------------------------------------------------------------------- #
# D. Cancel
# --------------------------------------------------------------------- #


class TestCancel:
    def _setup_pending_order(
        self, db, store, item, admin, qty=2
    ) -> Order:
        return svc.create_order(
            db, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=qty)],
            ),
            actor_user_id=admin.id,
        )

    def test_cancel_from_pending_releases_reservation(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = self._setup_pending_order(db_session, store, item, admin, qty=3)

        db_session.refresh(item)
        assert item.quantity_reserved == 3

        svc.cancel_order(
            db_session,
            order.id,
            OrderCancelRequest(reason="customer changed mind"),
            actor_user_id=admin.id,
        )

        db_session.refresh(item)
        assert item.quantity_reserved == 0
        assert item.quantity_on_hand == 10

    def test_cancel_sets_status_and_timestamps(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = self._setup_pending_order(db_session, store, item, admin, qty=1)

        canceled = svc.cancel_order(
            db_session,
            order.id,
            OrderCancelRequest(reason="out of stock"),
            actor_user_id=admin.id,
        )

        assert canceled.status == OrderStatus.canceled
        assert canceled.canceled_at is not None
        assert canceled.cancel_reason == "out of stock"

    def test_cancel_writes_audit_log(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = self._setup_pending_order(db_session, store, item, admin, qty=1)

        svc.cancel_order(
            db_session,
            order.id,
            OrderCancelRequest(reason="not paid"),
            actor_user_id=admin.id,
        )

        logs = _audit_logs_for_order(db_session, order.id)
        # one for create, one for cancel
        actions = [lg.action for lg in logs]
        assert svc.ACTION_ORDER_CREATED in actions
        assert svc.ACTION_ORDER_CANCELED in actions
        cancel_log = next(
            lg for lg in logs if lg.action == svc.ACTION_ORDER_CANCELED
        )
        assert cancel_log.previous_status == OrderStatus.pending
        assert cancel_log.new_status == OrderStatus.canceled
        assert cancel_log.reason == "not paid"

    def test_cancel_from_delivered_fails(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = self._setup_pending_order(db_session, store, item, admin, qty=1)

        # Force order into delivered state via the proper path
        svc.transition_order_status(
            db_session, order.id,
            OrderStatusUpdate(new_status=OrderStatus.accepted), admin.id,
        )
        svc.transition_order_status(
            db_session, order.id,
            OrderStatusUpdate(new_status=OrderStatus.preparing), admin.id,
        )
        svc.transition_order_status(
            db_session, order.id,
            OrderStatusUpdate(new_status=OrderStatus.ready), admin.id,
        )
        svc.transition_order_status(
            db_session, order.id,
            OrderStatusUpdate(new_status=OrderStatus.delivered), admin.id,
        )

        with pytest.raises(HTTPException) as exc:
            svc.cancel_order(
                db_session, order.id,
                OrderCancelRequest(reason="too late"), admin.id,
            )
        assert exc.value.status_code == 422

    def test_cancel_from_returned_fails(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = self._setup_pending_order(db_session, store, item, admin, qty=1)

        # Walk to delivered then return
        for s in (OrderStatus.accepted, OrderStatus.preparing,
                  OrderStatus.ready, OrderStatus.delivered):
            svc.transition_order_status(
                db_session, order.id,
                OrderStatusUpdate(new_status=s), admin.id,
            )
        svc.return_order(
            db_session, order.id,
            OrderReturnRequest(reason="defective"), admin.id,
        )

        with pytest.raises(HTTPException) as exc:
            svc.cancel_order(
                db_session, order.id,
                OrderCancelRequest(reason="too late"), admin.id,
            )
        assert exc.value.status_code == 422


# --------------------------------------------------------------------- #
# E. Delivered
# --------------------------------------------------------------------- #


class TestDelivered:
    def _create_pending(self, db, store, item, admin, qty=2):
        return svc.create_order(
            db, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=qty)],
            ),
            actor_user_id=admin.id,
        )

    def _walk_to_ready(self, db, order, admin):
        for s in (OrderStatus.accepted, OrderStatus.preparing,
                  OrderStatus.ready):
            svc.transition_order_status(
                db, order.id,
                OrderStatusUpdate(new_status=s), admin.id,
            )

    def test_ready_to_delivered_consumes_reserved_inventory(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10, quantity_reserved=0)
        admin = make_admin()
        order = self._create_pending(db_session, store, item, admin, qty=3)

        db_session.refresh(item)
        assert item.quantity_reserved == 3
        assert item.quantity_on_hand == 10

        self._walk_to_ready(db_session, order, admin)
        svc.transition_order_status(
            db_session, order.id,
            OrderStatusUpdate(new_status=OrderStatus.delivered), admin.id,
        )

        db_session.refresh(item)
        # Reservation went down by 3 AND on_hand went down by 3
        assert item.quantity_reserved == 0
        assert item.quantity_on_hand == 7

    def test_delivered_writes_sale_inventory_log(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = self._create_pending(db_session, store, item, admin, qty=2)
        self._walk_to_ready(db_session, order, admin)
        svc.transition_order_status(
            db_session, order.id,
            OrderStatusUpdate(new_status=OrderStatus.delivered), admin.id,
        )

        sale_logs = [
            lg for lg in _logs_for_item(db_session, item.id)
            if lg.movement_type == InventoryMovementType.sale
        ]
        assert len(sale_logs) == 1
        assert sale_logs[0].quantity_delta == -2
        assert sale_logs[0].reference_type == "order"
        assert sale_logs[0].reference_id == order.id

    def test_delivered_sets_delivered_at(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        admin = make_admin()
        order = self._create_pending(db_session, store, item, admin, qty=1)
        self._walk_to_ready(db_session, order, admin)
        delivered = svc.transition_order_status(
            db_session, order.id,
            OrderStatusUpdate(new_status=OrderStatus.delivered), admin.id,
        )

        assert delivered.delivered_at is not None
        assert delivered.status == OrderStatus.delivered

    def test_delivered_writes_order_delivered_audit_log(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        admin = make_admin()
        order = self._create_pending(db_session, store, item, admin, qty=1)
        self._walk_to_ready(db_session, order, admin)
        svc.transition_order_status(
            db_session, order.id,
            OrderStatusUpdate(new_status=OrderStatus.delivered), admin.id,
        )

        logs = _audit_logs_for_order(db_session, order.id)
        deliver_log = next(
            lg for lg in logs if lg.action == svc.ACTION_ORDER_DELIVERED
        )
        assert deliver_log.new_status == OrderStatus.delivered
        assert deliver_log.previous_status == OrderStatus.ready


# --------------------------------------------------------------------- #
# F. Return
# --------------------------------------------------------------------- #


class TestReturn:
    def _deliver_order(self, db, store, item, admin, qty=1):
        order = svc.create_order(
            db, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=qty)],
            ),
            actor_user_id=admin.id,
        )
        for s in (OrderStatus.accepted, OrderStatus.preparing,
                  OrderStatus.ready, OrderStatus.delivered):
            svc.transition_order_status(
                db, order.id,
                OrderStatusUpdate(new_status=s), admin.id,
            )
        return order

    def test_return_replenishes_inventory(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = self._deliver_order(db_session, store, item, admin, qty=4)

        db_session.refresh(item)
        assert item.quantity_on_hand == 6  # 10 - 4

        svc.return_order(
            db_session, order.id,
            OrderReturnRequest(reason="customer return"), admin.id,
        )

        db_session.refresh(item)
        assert item.quantity_on_hand == 10  # back up

    def test_return_sets_returned_at(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = self._deliver_order(db_session, store, item, admin, qty=2)

        returned = svc.return_order(
            db_session, order.id,
            OrderReturnRequest(reason="defective"), admin.id,
        )

        assert returned.status == OrderStatus.returned
        assert returned.returned_at is not None

    def test_return_writes_order_returned_audit_log(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = self._deliver_order(db_session, store, item, admin, qty=1)

        svc.return_order(
            db_session, order.id,
            OrderReturnRequest(reason="damaged"), admin.id,
        )

        logs = _audit_logs_for_order(db_session, order.id)
        ret_log = next(
            lg for lg in logs if lg.action == svc.ACTION_ORDER_RETURNED
        )
        assert ret_log.new_status == OrderStatus.returned
        assert ret_log.previous_status == OrderStatus.delivered
        assert ret_log.reason == "damaged"

    def test_return_from_pending_fails(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )

        with pytest.raises(HTTPException) as exc:
            svc.return_order(
                db_session, order.id,
                OrderReturnRequest(reason="early"), admin.id,
            )
        assert exc.value.status_code == 422


# --------------------------------------------------------------------- #
# G. State machine
# --------------------------------------------------------------------- #


class TestStateMachine:
    def _make_pending(self, db, store, item, admin):
        return svc.create_order(
            db, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )

    @pytest.mark.parametrize(
        "path",
        [
            (OrderStatus.accepted, OrderStatus.preparing,
             OrderStatus.ready, OrderStatus.out_for_delivery,
             OrderStatus.delivered),
            (OrderStatus.accepted, OrderStatus.preparing,
             OrderStatus.ready, OrderStatus.delivered),
        ],
    )
    def test_valid_forward_paths(
        self, db_session: Session, make_store, make_item, make_admin, path
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = self._make_pending(db_session, store, item, admin)

        for s in path:
            order = svc.transition_order_status(
                db_session, order.id,
                OrderStatusUpdate(new_status=s), admin.id,
            )
        # Last status reached
        assert order.status == path[-1]

    def test_invalid_transition_pending_to_ready_fails(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = self._make_pending(db_session, store, item, admin)

        with pytest.raises(HTTPException) as exc:
            svc.transition_order_status(
                db_session, order.id,
                OrderStatusUpdate(new_status=OrderStatus.ready), admin.id,
            )
        assert exc.value.status_code == 422

    def test_invalid_transition_pending_to_delivered_fails(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = self._make_pending(db_session, store, item, admin)

        with pytest.raises(HTTPException) as exc:
            svc.transition_order_status(
                db_session, order.id,
                OrderStatusUpdate(new_status=OrderStatus.delivered), admin.id,
            )
        assert exc.value.status_code == 422

    def test_terminal_canceled_cannot_transition(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = self._make_pending(db_session, store, item, admin)
        svc.cancel_order(
            db_session, order.id,
            OrderCancelRequest(reason="r"), admin.id,
        )

        with pytest.raises(HTTPException) as exc:
            svc.transition_order_status(
                db_session, order.id,
                OrderStatusUpdate(new_status=OrderStatus.accepted), admin.id,
            )
        assert exc.value.status_code == 422

    def test_terminal_returned_cannot_transition(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = self._make_pending(db_session, store, item, admin)
        for s in (OrderStatus.accepted, OrderStatus.preparing,
                  OrderStatus.ready, OrderStatus.delivered):
            svc.transition_order_status(
                db_session, order.id,
                OrderStatusUpdate(new_status=s), admin.id,
            )
        svc.return_order(
            db_session, order.id,
            OrderReturnRequest(reason="r"), admin.id,
        )

        with pytest.raises(HTTPException) as exc:
            svc.transition_order_status(
                db_session, order.id,
                OrderStatusUpdate(new_status=OrderStatus.delivered), admin.id,
            )
        assert exc.value.status_code == 422

    def test_canceled_cannot_be_reused_via_status_endpoint(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        """Even from pending, the generic status endpoint refuses to
        transition to canceled or returned — those need their dedicated
        cancel/return endpoints because they require reasons."""
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = self._make_pending(db_session, store, item, admin)

        with pytest.raises(HTTPException) as exc:
            svc.transition_order_status(
                db_session, order.id,
                OrderStatusUpdate(new_status=OrderStatus.canceled), admin.id,
            )
        assert exc.value.status_code == 422


# --------------------------------------------------------------------- #
# H. Compliance / sellability
# --------------------------------------------------------------------- #


class TestComplianceSellability:
    def test_banned_product_blocks_create(
        self, db_session: Session, make_store, make_product, make_variant,
        make_item, make_admin
    ):
        store = make_store()
        product = make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant, quantity_on_hand=10)
        admin = make_admin()

        with pytest.raises(HTTPException) as exc:
            svc.create_order(
                db_session, store.id,
                OrderCreate(
                    idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                    items=[OrderItemCreate(variant_id=variant.id, quantity=1)],
                ),
                actor_user_id=admin.id,
            )
        assert exc.value.status_code == 422

    def test_quarantined_item_blocks_create(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(
            store=store,
            quantity_on_hand=10,
            status=InventoryStatus.quarantined,
        )
        admin = make_admin()

        with pytest.raises(HTTPException) as exc:
            svc.create_order(
                db_session, store.id,
                OrderCreate(
                    idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                    items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
                ),
                actor_user_id=admin.id,
            )
        assert exc.value.status_code == 422

    def test_inactive_variant_blocks_create(
        self, db_session: Session, make_store, make_variant, make_item,
        make_admin
    ):
        store = make_store()
        variant = make_variant(is_active=False)
        item = make_item(store=store, variant=variant, quantity_on_hand=10)
        admin = make_admin()

        with pytest.raises(HTTPException) as exc:
            svc.create_order(
                db_session, store.id,
                OrderCreate(
                    idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                    items=[OrderItemCreate(variant_id=variant.id, quantity=1)],
                ),
                actor_user_id=admin.id,
            )
        assert exc.value.status_code == 422

    def test_item_quarantined_after_reserve_blocks_delivered(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        """A product banned/quarantined between reserve and delivered
        must not be deliverable. The DELIVERED transition's re-check
        is the line of defence (orders_rules §7).
        """
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )

        # Walk through the safe transitions
        for s in (OrderStatus.accepted, OrderStatus.preparing,
                  OrderStatus.ready):
            svc.transition_order_status(
                db_session, order.id,
                OrderStatusUpdate(new_status=s), admin.id,
            )

        # Now flip the inventory item to quarantined (simulating the
        # cascade fired by set_product_compliance(banned)).
        item.status = InventoryStatus.quarantined
        db_session.add(item)
        db_session.commit()

        with pytest.raises(HTTPException) as exc:
            svc.transition_order_status(
                db_session, order.id,
                OrderStatusUpdate(new_status=OrderStatus.delivered), admin.id,
            )
        assert exc.value.status_code == 422

    def test_cancel_after_ban_still_releases_reservation(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        """Cancel skips sellability gates by design — a banned item's
        reservation can still be freed."""
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=2)],
            ),
            actor_user_id=admin.id,
        )

        item.status = InventoryStatus.quarantined
        db_session.add(item)
        db_session.commit()

        svc.cancel_order(
            db_session, order.id,
            OrderCancelRequest(reason="banned mid-flight"), admin.id,
        )
        db_session.refresh(item)
        assert item.quantity_reserved == 0


# --------------------------------------------------------------------- #
# I. Cross-store safety
# --------------------------------------------------------------------- #


class TestCrossStoreSafety:
    def test_store_a_order_cannot_resolve_store_b_inventory(
        self, db_session: Session, make_store, make_variant, make_item,
        make_admin
    ):
        """Variant exists with inventory in store B only. An order
        for store A must fail because (store_a, variant) has no
        inventory_item row."""
        store_a = make_store(code_prefix="a")
        store_b = make_store(code_prefix="b")
        variant = make_variant()
        # Inventory only in store_b
        make_item(store=store_b, variant=variant, quantity_on_hand=10)
        admin = make_admin()

        with pytest.raises(HTTPException) as exc:
            svc.create_order(
                db_session, store_a.id,
                OrderCreate(
                    idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                    items=[OrderItemCreate(variant_id=variant.id, quantity=1)],
                ),
                actor_user_id=admin.id,
            )
        assert exc.value.status_code == 422
        assert "inventory" in exc.value.detail.lower()

    def test_variant_without_inventory_in_store_fails(
        self, db_session: Session, make_store, make_variant, make_admin
    ):
        store = make_store()
        variant = make_variant()  # no inventory item created at all
        admin = make_admin()

        with pytest.raises(HTTPException) as exc:
            svc.create_order(
                db_session, store.id,
                OrderCreate(
                    idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                    items=[OrderItemCreate(variant_id=variant.id, quantity=1)],
                ),
                actor_user_id=admin.id,
            )
        assert exc.value.status_code == 422


# --------------------------------------------------------------------- #
# J. Money
# --------------------------------------------------------------------- #


class TestMoney:
    def test_unit_price_only_comes_from_db(
        self, db_session: Session, make_store, make_variant, make_item,
        make_admin
    ):
        """The schema forbids client-supplied unit_price (validated at
        the schema layer in test_order_schemas). The service-layer
        invariant: order_item.unit_price must equal variant.price at
        creation time, regardless of any other state.
        """
        store = make_store()
        variant = make_variant(price=Decimal("19.99"))
        make_item(store=store, variant=variant, quantity_on_hand=5)
        admin = make_admin()

        order = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=variant.id, quantity=2)],
            ),
            actor_user_id=admin.id,
        )

        assert order.items[0].unit_price == Decimal("19.99")

    def test_line_total_equals_unit_price_times_quantity(
        self, db_session: Session, make_store, make_variant, make_item,
        make_admin
    ):
        store = make_store()
        variant = make_variant(price=Decimal("3.33"))
        make_item(store=store, variant=variant, quantity_on_hand=20)
        admin = make_admin()

        order = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=variant.id, quantity=4)],
            ),
            actor_user_id=admin.id,
        )

        assert order.items[0].line_total == Decimal("13.32")  # 3.33 * 4

    def test_tax_amount_is_zero_in_mvp(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()

        order = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )

        assert order.tax_amount == Decimal("0.00")

    def test_total_amount_equals_subtotal(
        self, db_session: Session, make_store, make_variant, make_item,
        make_admin
    ):
        store = make_store()
        v1 = make_variant(price=Decimal("2.50"))
        v2 = make_variant(price=Decimal("7.50"))
        make_item(store=store, variant=v1, quantity_on_hand=10)
        make_item(store=store, variant=v2, quantity_on_hand=10)
        admin = make_admin()

        order = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[
                    OrderItemCreate(variant_id=v1.id, quantity=2),  # 5.00
                    OrderItemCreate(variant_id=v2.id, quantity=1),  # 7.50
                ],
            ),
            actor_user_id=admin.id,
        )

        assert order.subtotal_amount == Decimal("12.50")
        assert order.total_amount == order.subtotal_amount


# --------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------- #


class TestReads:
    def test_get_order_returns_order(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        admin = make_admin()
        order = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )

        loaded = svc.get_order(db_session, order.id)
        assert loaded.id == order.id
        _assert_order_items_enriched(loaded)

    def test_get_order_missing_raises_404(self, db_session: Session):
        with pytest.raises(HTTPException) as exc:
            svc.get_order(db_session, uuid.uuid4())
        assert exc.value.status_code == 404

    def test_create_order_returns_items_with_variant_product(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        admin = make_admin()

        order = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )

        _assert_order_items_enriched(order)

    def test_idempotency_replay_returns_items_with_variant_product(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        admin = make_admin()
        key = f"k-{uuid.uuid4().hex[:8]}"

        svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=key,
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )
        replay = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=key,
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )

        _assert_order_items_enriched(replay)

    def test_transition_response_keeps_items_with_variant_product(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        admin = make_admin()
        order = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )

        transitioned = svc.transition_order_status(
            db_session, order.id,
            OrderStatusUpdate(new_status=OrderStatus.accepted), admin.id,
        )

        assert transitioned.status == OrderStatus.accepted
        _assert_order_items_enriched(transitioned)

    def test_cancel_response_keeps_items_with_variant_product(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        admin = make_admin()
        order = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )

        canceled = svc.cancel_order(
            db_session,
            order.id,
            OrderCancelRequest(reason="customer changed mind"),
            admin.id,
        )

        assert canceled.status == OrderStatus.canceled
        _assert_order_items_enriched(canceled)

    def test_return_response_keeps_items_with_variant_product(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        admin = make_admin()
        order = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )
        for status in (
            OrderStatus.accepted,
            OrderStatus.preparing,
            OrderStatus.ready,
            OrderStatus.delivered,
        ):
            order = svc.transition_order_status(
                db_session,
                order.id,
                OrderStatusUpdate(new_status=status),
                admin.id,
            )

        returned = svc.return_order(
            db_session,
            order.id,
            OrderReturnRequest(reason="defective unit"),
            admin.id,
        )

        assert returned.status == OrderStatus.returned
        _assert_order_items_enriched(returned)

    def test_list_orders_for_store_filters_by_store(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store_a = make_store(code_prefix="la")
        store_b = make_store(code_prefix="lb")
        item_a = make_item(store=store_a, quantity_on_hand=5)
        item_b = make_item(store=store_b, quantity_on_hand=5)
        admin = make_admin()
        oa = svc.create_order(
            db_session, store_a.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item_a.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )
        ob = svc.create_order(
            db_session, store_b.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item_b.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )

        a_only = svc.list_orders_for_store(db_session, store_a.id)
        ids = [o.id for o in a_only]
        assert oa.id in ids
        assert ob.id not in ids

    def test_list_orders_for_store_applies_limit_offset(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        for _ in range(3):
            svc.create_order(
                db_session, store.id,
                OrderCreate(
                    idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                    items=[
                        OrderItemCreate(
                            variant_id=item.variant_id, quantity=1
                        )
                    ],
                ),
                actor_user_id=admin.id,
            )

        page = svc.list_orders_for_store(
            db_session, store.id, limit=2, offset=1
        )

        assert len(page) == 2
        assert svc.count_orders_for_store(db_session, store.id) == 3

    def test_count_orders_for_store_uses_same_filters(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        old = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )
        kept = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )
        canceled = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )
        svc.cancel_order(
            db_session,
            canceled.id,
            OrderCancelRequest(reason="filter target"),
            admin.id,
        )
        base = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
        _set_order_created_at(db_session, old.id, base - timedelta(days=2))
        _set_order_created_at(db_session, kept.id, base)
        _set_order_created_at(db_session, canceled.id, base)

        listed = svc.list_orders_for_store(
            db_session,
            store.id,
            status=OrderStatus.pending,
            created_from=base - timedelta(hours=1),
        )
        total = svc.count_orders_for_store(
            db_session,
            store.id,
            status=OrderStatus.pending,
            created_from=base - timedelta(hours=1),
        )

        assert [o.id for o in listed] == [kept.id]
        assert total == 1

    def test_list_orders_for_store_orders_by_created_at_desc_then_id_desc(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        older = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )
        tied_a = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )
        tied_b = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )
        base = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
        _set_order_created_at(db_session, older.id, base - timedelta(days=1))
        _set_order_created_at(db_session, tied_a.id, base)
        _set_order_created_at(db_session, tied_b.id, base)

        ids = [
            o.id
            for o in svc.list_orders_for_store(db_session, store.id)
        ]

        assert ids[:2] == sorted([tied_a.id, tied_b.id], reverse=True)
        assert ids[2] == older.id

    def test_list_orders_for_store_includes_items(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        admin = make_admin()
        order = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )

        listed = svc.list_orders_for_store(db_session, store.id)

        assert listed[0].id == order.id
        assert len(listed[0].items) == 1
        _assert_order_items_enriched(listed[0])

    def test_list_orders_for_store_does_not_n_plus_1(
        self,
        db_session: Session,
        make_store,
        make_product,
        make_variant,
        make_item,
        make_admin,
    ):
        from sqlalchemy import event

        store = make_store()
        admin = make_admin()
        for _ in range(4):
            product = make_product()
            variant = make_variant(product=product)
            make_item(store=store, variant=variant, quantity_on_hand=5)
            svc.create_order(
                db_session,
                store.id,
                OrderCreate(
                    idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                    items=[
                        OrderItemCreate(variant_id=variant.id, quantity=1)
                    ],
                ),
                actor_user_id=admin.id,
            )

        engine = db_session.get_bind()
        captured: list[str] = []

        def _on_execute(conn, cursor, statement, parameters, context, executemany):
            sql = statement.lower()
            if "select" not in sql:
                return
            if any(
                tbl in sql
                for tbl in (
                    "orders",
                    "order_items",
                    "product_variants",
                    "products",
                )
            ):
                captured.append(statement)

        event.listen(engine, "before_cursor_execute", _on_execute)
        try:
            orders = svc.list_orders_for_store(db_session, store.id)
            for order in orders:
                _assert_order_items_enriched(order)
        finally:
            event.remove(engine, "before_cursor_execute", _on_execute)

        assert len(orders) == 4
        assert len(captured) <= 6, (
            f"list_orders_for_store fired {len(captured)} SELECTs on "
            "orders/order_items/variant/product tables for 4 orders; "
            "looks like N+1. Statements:\n" + "\n---\n".join(captured)
        )

    def test_list_order_audit_logs_returns_in_creation_order(
        self, db_session: Session, make_store, make_item, make_admin
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_admin()
        order = svc.create_order(
            db_session, store.id,
            OrderCreate(
                idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
                items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
            ),
            actor_user_id=admin.id,
        )
        svc.transition_order_status(
            db_session, order.id,
            OrderStatusUpdate(new_status=OrderStatus.accepted), admin.id,
        )

        logs = svc.list_order_audit_logs(db_session, order.id)
        assert [lg.action for lg in logs] == [
            svc.ACTION_ORDER_CREATED,
            svc.ACTION_STATUS_CHANGED,
        ]

    def test_list_order_audit_logs_missing_order_raises_404(
        self, db_session: Session
    ):
        with pytest.raises(HTTPException) as exc:
            svc.list_order_audit_logs(db_session, uuid.uuid4())
        assert exc.value.status_code == 404


# --------------------------------------------------------------------- #
# Admin global feed (F2.18.1B)
# --------------------------------------------------------------------- #


@pytest.fixture
def make_non_admin_user(
    db_session: Session, make_store
) -> Callable[..., User]:
    def _create(role: UserRole = UserRole.owner) -> User:
        store = make_store()
        user = User(
            full_name=f"Ord Svc {role.value}",
            email=f"{role.value}-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=make_password_hash("supersecret123"),
            role=role,
            store_id=store.id,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


def _make_pending_order(
    db_session: Session,
    make_store,
    make_item,
    admin: User,
    *,
    store: Store | None = None,
) -> Order:
    """Build a real pending order via the service so totals + items +
    audit log land naturally. Returns the eager-loaded Order."""
    target_store = store if store is not None else make_store()
    item = make_item(store=target_store, quantity_on_hand=10)
    return svc.create_order(
        db_session,
        target_store.id,
        OrderCreate(
            idempotency_key=f"k-{uuid.uuid4().hex[:8]}",
            items=[OrderItemCreate(variant_id=item.variant_id, quantity=1)],
        ),
        actor_user_id=admin.id,
    )


class TestServiceAdminOrdersRBAC:
    @pytest.mark.parametrize(
        "role",
        [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver],
    )
    def test_non_admin_role_forbidden(
        self, db_session: Session, make_non_admin_user, role
    ):
        actor = make_non_admin_user(role=role)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_admin_orders(db_session, actor=actor)
        assert excinfo.value.status_code == 403

    def test_admin_allowed_empty(
        self, db_session: Session, make_admin
    ):
        admin = make_admin()
        response = svc.list_admin_orders(db_session, actor=admin)
        assert response.total == 0
        assert response.items == []
        assert response.limit == 50
        assert response.offset == 0


class TestServiceAdminOrdersGlobalFeed:
    def test_returns_orders_from_multiple_stores(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store_a = make_store()
        store_b = make_store()
        order_a = _make_pending_order(
            db_session, make_store, make_item, admin, store=store_a
        )
        order_b = _make_pending_order(
            db_session, make_store, make_item, admin, store=store_b
        )

        response = svc.list_admin_orders(db_session, actor=admin)

        ids = {order.id for order in response.items}
        assert order_a.id in ids
        assert order_b.id in ids
        assert response.total >= 2

    def test_total_counts_pre_pagination(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        for _ in range(5):
            _make_pending_order(
                db_session, make_store, make_item, admin, store=store
            )

        response = svc.list_admin_orders(
            db_session, actor=admin, store_id=store.id, limit=2, offset=0
        )

        assert response.total == 5
        assert len(response.items) == 2

    def test_pagination_offset_advances(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        orders = [
            _make_pending_order(
                db_session, make_store, make_item, admin, store=store
            )
            for _ in range(4)
        ]
        # Pin distinct created_at so DESC sort is deterministic
        # (without this, all orders in a single TX share now()).
        base = datetime(2025, 6, 1, tzinfo=UTC)
        for index, order in enumerate(orders):
            _set_order_created_at(
                db_session, order.id, base + timedelta(minutes=index)
            )

        first = svc.list_admin_orders(
            db_session, actor=admin, store_id=store.id, limit=2, offset=0
        )
        second = svc.list_admin_orders(
            db_session, actor=admin, store_id=store.id, limit=2, offset=2
        )

        first_ids = {order.id for order in first.items}
        second_ids = {order.id for order in second.items}
        assert first_ids.isdisjoint(second_ids)
        assert len(first_ids) == 2
        assert len(second_ids) == 2

    def test_sort_newer_created_at_first(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        orders = [
            _make_pending_order(
                db_session, make_store, make_item, admin, store=store
            )
            for _ in range(3)
        ]
        base = datetime(2025, 6, 1, tzinfo=UTC)
        for index, order in enumerate(orders):
            _set_order_created_at(
                db_session, order.id, base + timedelta(minutes=index)
            )

        response = svc.list_admin_orders(
            db_session, actor=admin, store_id=store.id, limit=10
        )

        returned_ids = [order.id for order in response.items]
        assert returned_ids == [orders[2].id, orders[1].id, orders[0].id]

    def test_sort_id_asc_tie_breaker(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        orders = [
            _make_pending_order(
                db_session, make_store, make_item, admin, store=store
            )
            for _ in range(3)
        ]
        # Same created_at across all three → id ASC tie-breaker decides.
        same = datetime(2025, 6, 1, tzinfo=UTC)
        for order in orders:
            _set_order_created_at(db_session, order.id, same)

        response = svc.list_admin_orders(
            db_session, actor=admin, store_id=store.id, limit=10
        )

        returned_ids = [str(order.id) for order in response.items]
        assert returned_ids == sorted(str(order.id) for order in orders)


class TestServiceAdminOrdersStoreScope:
    def test_store_id_filter_returns_only_that_store(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store_a = make_store()
        store_b = make_store()
        order_a = _make_pending_order(
            db_session, make_store, make_item, admin, store=store_a
        )
        _make_pending_order(
            db_session, make_store, make_item, admin, store=store_b
        )

        response = svc.list_admin_orders(
            db_session, actor=admin, store_id=store_a.id
        )

        ids = {order.id for order in response.items}
        assert ids == {order_a.id}
        for order in response.items:
            assert order.store_id == store_a.id

    def test_unknown_store_id_raises_404(
        self, db_session: Session, make_admin
    ):
        admin = make_admin()
        with pytest.raises(HTTPException) as excinfo:
            svc.list_admin_orders(
                db_session, actor=admin, store_id=uuid.uuid4()
            )
        assert excinfo.value.status_code == 404
        assert "store" in excinfo.value.detail.lower()

    def test_inactive_store_id_returns_data(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        """Admin retains visibility into deactivated stores.

        Mirrors list_admin_audit / list_admin_inventory semantics.
        """
        admin = make_admin()
        store = make_store()
        order = _make_pending_order(
            db_session, make_store, make_item, admin, store=store
        )
        store.is_active = False
        db_session.commit()

        response = svc.list_admin_orders(
            db_session, actor=admin, store_id=store.id
        )

        ids = {row.id for row in response.items}
        assert order.id in ids


class TestServiceAdminOrdersFilters:
    def test_status_filter(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        pending = _make_pending_order(
            db_session, make_store, make_item, admin, store=store
        )
        accepted_order = _make_pending_order(
            db_session, make_store, make_item, admin, store=store
        )
        svc.transition_order_status(
            db_session,
            accepted_order.id,
            OrderStatusUpdate(new_status=OrderStatus.accepted),
            actor_user_id=admin.id,
        )

        response = svc.list_admin_orders(
            db_session,
            actor=admin,
            store_id=store.id,
            order_status=OrderStatus.accepted,
        )

        ids = {row.id for row in response.items}
        assert ids == {accepted_order.id}
        assert pending.id not in ids

    def test_date_from_inclusive_lower_bound(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        orders = [
            _make_pending_order(
                db_session, make_store, make_item, admin, store=store
            )
            for _ in range(3)
        ]
        base = datetime(2025, 6, 1, tzinfo=UTC)
        for index, order in enumerate(orders):
            _set_order_created_at(
                db_session, order.id, base + timedelta(days=index)
            )

        # date_from = the second order's timestamp; >= so it's included.
        cutoff = base + timedelta(days=1)
        response = svc.list_admin_orders(
            db_session,
            actor=admin,
            store_id=store.id,
            date_from=cutoff,
        )

        ids = {row.id for row in response.items}
        assert ids == {orders[1].id, orders[2].id}

    def test_date_to_inclusive_upper_bound(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        orders = [
            _make_pending_order(
                db_session, make_store, make_item, admin, store=store
            )
            for _ in range(3)
        ]
        base = datetime(2025, 6, 1, tzinfo=UTC)
        for index, order in enumerate(orders):
            _set_order_created_at(
                db_session, order.id, base + timedelta(days=index)
            )

        # date_to = the second order's timestamp; <= so it's included.
        cutoff = base + timedelta(days=1)
        response = svc.list_admin_orders(
            db_session,
            actor=admin,
            store_id=store.id,
            date_to=cutoff,
        )

        ids = {row.id for row in response.items}
        assert ids == {orders[0].id, orders[1].id}

    def test_date_range_filters_combined(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        orders = [
            _make_pending_order(
                db_session, make_store, make_item, admin, store=store
            )
            for _ in range(4)
        ]
        base = datetime(2025, 6, 1, tzinfo=UTC)
        for index, order in enumerate(orders):
            _set_order_created_at(
                db_session, order.id, base + timedelta(days=index)
            )

        response = svc.list_admin_orders(
            db_session,
            actor=admin,
            store_id=store.id,
            date_from=base + timedelta(days=1),
            date_to=base + timedelta(days=2),
        )

        ids = {row.id for row in response.items}
        assert ids == {orders[1].id, orders[2].id}


class TestServiceStoreScopedOrdersRegression:
    """F2.18.1B must not change the store-scoped orders service surface."""

    def test_list_orders_for_store_unchanged(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        orders = [
            _make_pending_order(
                db_session, make_store, make_item, admin, store=store
            )
            for _ in range(2)
        ]

        rows = svc.list_orders_for_store(db_session, store.id)
        assert {row.id for row in rows} == {order.id for order in orders}

    def test_count_orders_for_store_unchanged(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        for _ in range(3):
            _make_pending_order(
                db_session, make_store, make_item, admin, store=store
            )

        assert svc.count_orders_for_store(db_session, store.id) == 3
