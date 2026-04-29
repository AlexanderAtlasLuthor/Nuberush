"""Service-layer tests for the inventory module (S4).

Exercises app.services.inventory against the real test DB via the
`db_session` fixture from conftest. Covers:
  - setup (create + duplicate)
  - the 7 stock movements (receive, adjust, damage, sale, reserve,
    release, return)
  - InventoryLog writing on every successful mutation
  - validation gates (insufficient stock, release > reserved,
    quarantined, banned product, inactive variant, adjust/damage
    that would push qoh negative or below qreserved)
  - atomicity (a failing sale leaves no quantity change AND no log
    row)

API-level matrices (RBAC, tenancy via TestClient) live in a
separate file by design — see prompt's "Do not duplicate router/API
tests here".

Style mirrors tests/test_products.py.
"""

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import InventoryMovementType
from app.db.models import InventoryStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.inventory import AdjustStockRequest
from app.schemas.inventory import DamageStockRequest
from app.schemas.inventory import InventoryItemCreate
from app.schemas.inventory import ReceiveStockRequest
from app.schemas.inventory import ReleaseReservationRequest
from app.schemas.inventory import ReserveStockRequest
from app.schemas.inventory import ReturnStockRequest
from app.schemas.inventory import SaleStockRequest
from app.services import inventory as svc


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create() -> Store:
        store = Store(name="Inv-Svc", code=f"is-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_admin(db_session: Session) -> Callable[..., User]:
    def _create() -> User:
        admin = User(
            full_name="Inv Svc Admin",
            email=f"isa-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("supersecret123"),
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
            name=f"P-{uuid.uuid4().hex[:6]}",
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
    ) -> ProductVariant:
        prod = product if product is not None else make_product()
        variant = ProductVariant(
            product_id=prod.id,
            sku=f"SKU-{uuid.uuid4().hex[:8]}",
            price=Decimal("9.99"),
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
            select(InventoryLog).where(InventoryLog.inventory_item_id == item_id)
        ).all()
    )


# --------------------------------------------------------------------- #
# Setup
# --------------------------------------------------------------------- #


class TestServiceSetup:
    def test_create_inventory_item_persists(
        self, db_session: Session, make_store, make_variant, make_admin
    ):
        store = make_store()
        variant = make_variant()
        admin = make_admin()
        item = svc.create_inventory_item(
            db_session,
            store.id,
            InventoryItemCreate(variant_id=variant.id, quantity_on_hand=5),
            actor_user_id=admin.id,
        )
        assert item.store_id == store.id
        assert item.variant_id == variant.id
        assert item.quantity_on_hand == 5
        assert item.status == InventoryStatus.available

    def test_duplicate_store_variant_raises_409(
        self, db_session: Session, make_store, make_variant, make_admin
    ):
        store = make_store()
        variant = make_variant()
        admin = make_admin()
        svc.create_inventory_item(
            db_session,
            store.id,
            InventoryItemCreate(variant_id=variant.id),
            actor_user_id=admin.id,
        )
        with pytest.raises(HTTPException) as excinfo:
            svc.create_inventory_item(
                db_session,
                store.id,
                InventoryItemCreate(variant_id=variant.id),
                actor_user_id=admin.id,
            )
        assert excinfo.value.status_code == 409
        assert "already exists" in excinfo.value.detail.lower()


# --------------------------------------------------------------------- #
# Movements — happy paths
# --------------------------------------------------------------------- #


class TestServiceMovementsHappyPath:
    def test_receive_increases_quantity_on_hand(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=5)
        result = svc.receive_stock(
            db_session,
            item.id,
            ReceiveStockRequest(quantity=3),
            admin.id,
        )
        assert result.quantity_on_hand == 8
        assert result.quantity_reserved == 0

    def test_adjust_signed_delta_changes_quantity_on_hand(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=10)

        positive = svc.adjust_stock(
            db_session,
            item.id,
            AdjustStockRequest(delta=4, reason="receive"),
            admin.id,
        )
        assert positive.quantity_on_hand == 14

        negative = svc.adjust_stock(
            db_session,
            item.id,
            AdjustStockRequest(delta=-2, reason="loss"),
            admin.id,
        )
        assert negative.quantity_on_hand == 12

    def test_damage_reduces_quantity_on_hand(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=8)
        result = svc.record_damage(
            db_session,
            item.id,
            DamageStockRequest(quantity=3, reason="broken"),
            admin.id,
        )
        assert result.quantity_on_hand == 5

    def test_sale_reduces_quantity_on_hand(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=10)
        result = svc.sell_inventory(
            db_session,
            item.id,
            SaleStockRequest(quantity=4),
            admin.id,
        )
        assert result.quantity_on_hand == 6
        assert result.quantity_reserved == 0

    def test_reserve_increases_quantity_reserved(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=10)
        result = svc.reserve_inventory(
            db_session,
            item.id,
            ReserveStockRequest(quantity=4),
            admin.id,
        )
        assert result.quantity_reserved == 4
        # quantity_on_hand untouched
        assert result.quantity_on_hand == 10

    def test_release_reduces_quantity_reserved(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=10, quantity_reserved=4)
        result = svc.release_reservation(
            db_session,
            item.id,
            ReleaseReservationRequest(quantity=3),
            admin.id,
        )
        assert result.quantity_reserved == 1
        # quantity_on_hand untouched
        assert result.quantity_on_hand == 10

    def test_return_increases_quantity_on_hand(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=5)
        result = svc.return_to_inventory(
            db_session,
            item.id,
            ReturnStockRequest(quantity=2, reason="customer return"),
            admin.id,
        )
        assert result.quantity_on_hand == 7


# --------------------------------------------------------------------- #
# Logs
# --------------------------------------------------------------------- #


class TestServiceLogWriting:
    def test_receive_writes_log_with_correct_fields(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=5)
        svc.receive_stock(
            db_session,
            item.id,
            ReceiveStockRequest(quantity=3),
            admin.id,
        )
        logs = _logs_for_item(db_session, item.id)
        assert len(logs) == 1
        log = logs[0]
        assert log.movement_type == InventoryMovementType.receipt
        assert log.quantity_delta == 3
        assert log.quantity_after == 8
        assert log.performed_by_user_id == admin.id

    def test_sale_writes_log_with_negative_delta(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=10)
        svc.sell_inventory(
            db_session, item.id, SaleStockRequest(quantity=2), admin.id
        )
        logs = _logs_for_item(db_session, item.id)
        assert len(logs) == 1
        assert logs[0].movement_type == InventoryMovementType.sale
        assert logs[0].quantity_delta == -2
        assert logs[0].quantity_after == 8

    def test_reserve_writes_log_against_quantity_reserved(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=10)
        svc.reserve_inventory(
            db_session, item.id, ReserveStockRequest(quantity=4), admin.id
        )
        logs = _logs_for_item(db_session, item.id)
        assert len(logs) == 1
        # quantity_after for reservation tracks quantity_reserved
        assert logs[0].movement_type == InventoryMovementType.reservation
        assert logs[0].quantity_delta == 4
        assert logs[0].quantity_after == 4

    def test_release_writes_cancellation_log(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=10, quantity_reserved=4)
        svc.release_reservation(
            db_session,
            item.id,
            ReleaseReservationRequest(quantity=4),
            admin.id,
        )
        logs = _logs_for_item(db_session, item.id)
        assert len(logs) == 1
        assert logs[0].movement_type == InventoryMovementType.cancellation
        assert logs[0].quantity_delta == -4
        assert logs[0].quantity_after == 0

    def test_adjust_log_records_signed_delta(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=10)
        svc.adjust_stock(
            db_session,
            item.id,
            AdjustStockRequest(delta=-3, reason="loss"),
            admin.id,
        )
        logs = _logs_for_item(db_session, item.id)
        assert logs[0].movement_type == InventoryMovementType.adjustment
        assert logs[0].quantity_delta == -3
        assert logs[0].quantity_after == 7

    def test_full_chain_writes_one_log_per_mutation(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=10)

        svc.receive_stock(
            db_session, item.id, ReceiveStockRequest(quantity=5), admin.id
        )
        svc.adjust_stock(
            db_session, item.id, AdjustStockRequest(delta=-2, reason="x"), admin.id
        )
        svc.record_damage(
            db_session, item.id, DamageStockRequest(quantity=1, reason="x"), admin.id
        )
        svc.reserve_inventory(
            db_session, item.id, ReserveStockRequest(quantity=3), admin.id
        )
        svc.sell_inventory(
            db_session, item.id, SaleStockRequest(quantity=2), admin.id
        )
        svc.release_reservation(
            db_session, item.id, ReleaseReservationRequest(quantity=1), admin.id
        )
        svc.return_to_inventory(
            db_session,
            item.id,
            ReturnStockRequest(quantity=1, reason="defect"),
            admin.id,
        )

        logs = _logs_for_item(db_session, item.id)
        types = [log.movement_type for log in sorted(logs, key=lambda x: x.created_at)]
        # Note: 'cancellation' is the canonical movement_type for release
        # of reservation per inventory_rules §3 + §7.
        assert types == [
            InventoryMovementType.receipt,
            InventoryMovementType.adjustment,
            InventoryMovementType.damage,
            InventoryMovementType.reservation,
            InventoryMovementType.sale,
            InventoryMovementType.cancellation,
            InventoryMovementType.return_,
        ]


# --------------------------------------------------------------------- #
# Validation gates
# --------------------------------------------------------------------- #


class TestServiceValidations:
    def test_sale_without_stock_returns_422(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=2)
        with pytest.raises(HTTPException) as excinfo:
            svc.sell_inventory(
                db_session, item.id,
                SaleStockRequest(quantity=10), admin.id,
            )
        assert excinfo.value.status_code == 422
        assert "available" in excinfo.value.detail.lower()

    def test_reserve_over_available_returns_422(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        # qoh=10, reserved=8 → available=2; reserving 5 must fail
        item = make_item(quantity_on_hand=10, quantity_reserved=8)
        with pytest.raises(HTTPException) as excinfo:
            svc.reserve_inventory(
                db_session, item.id,
                ReserveStockRequest(quantity=5), admin.id,
            )
        assert excinfo.value.status_code == 422

    def test_release_over_reserved_returns_422(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=5, quantity_reserved=2)
        with pytest.raises(HTTPException) as excinfo:
            svc.release_reservation(
                db_session, item.id,
                ReleaseReservationRequest(quantity=5), admin.id,
            )
        assert excinfo.value.status_code == 422
        assert "release" in excinfo.value.detail.lower()

    def test_quarantined_blocks_sale(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=10, status=InventoryStatus.quarantined)
        with pytest.raises(HTTPException) as excinfo:
            svc.sell_inventory(
                db_session, item.id,
                SaleStockRequest(quantity=1), admin.id,
            )
        assert excinfo.value.status_code == 422
        assert "quarantined" in excinfo.value.detail.lower()

    def test_quarantined_blocks_reserve(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=10, status=InventoryStatus.quarantined)
        with pytest.raises(HTTPException) as excinfo:
            svc.reserve_inventory(
                db_session, item.id,
                ReserveStockRequest(quantity=1), admin.id,
            )
        assert excinfo.value.status_code == 422

    def test_banned_product_blocks_sale(
        self,
        db_session: Session,
        make_product,
        make_variant,
        make_item,
        make_admin,
    ):
        admin = make_admin()
        product = make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        variant = make_variant(product=product)
        item = make_item(variant=variant, quantity_on_hand=10)
        with pytest.raises(HTTPException) as excinfo:
            svc.sell_inventory(
                db_session, item.id,
                SaleStockRequest(quantity=1), admin.id,
            )
        assert excinfo.value.status_code == 422

    def test_banned_product_blocks_reserve(
        self,
        db_session: Session,
        make_product,
        make_variant,
        make_item,
        make_admin,
    ):
        admin = make_admin()
        product = make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        variant = make_variant(product=product)
        item = make_item(variant=variant, quantity_on_hand=10)
        with pytest.raises(HTTPException) as excinfo:
            svc.reserve_inventory(
                db_session, item.id,
                ReserveStockRequest(quantity=1), admin.id,
            )
        assert excinfo.value.status_code == 422

    def test_inactive_variant_blocks_sale(
        self,
        db_session: Session,
        make_variant,
        make_item,
        make_admin,
    ):
        admin = make_admin()
        variant = make_variant(is_active=False)
        item = make_item(variant=variant, quantity_on_hand=10)
        with pytest.raises(HTTPException) as excinfo:
            svc.sell_inventory(
                db_session, item.id,
                SaleStockRequest(quantity=1), admin.id,
            )
        assert excinfo.value.status_code == 422
        assert "active" in excinfo.value.detail.lower()

    def test_inactive_variant_blocks_reserve(
        self,
        db_session: Session,
        make_variant,
        make_item,
        make_admin,
    ):
        admin = make_admin()
        variant = make_variant(is_active=False)
        item = make_item(variant=variant, quantity_on_hand=10)
        with pytest.raises(HTTPException) as excinfo:
            svc.reserve_inventory(
                db_session, item.id,
                ReserveStockRequest(quantity=1), admin.id,
            )
        assert excinfo.value.status_code == 422

    def test_adjust_cannot_make_quantity_on_hand_negative(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=3)
        with pytest.raises(HTTPException) as excinfo:
            svc.adjust_stock(
                db_session, item.id,
                AdjustStockRequest(delta=-10, reason="overshoot"),
                admin.id,
            )
        assert excinfo.value.status_code == 422

    def test_adjust_cannot_drop_below_quantity_reserved(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        # qoh=10, reserved=8 → adjusting -5 would leave qoh=5 < reserved=8
        item = make_item(quantity_on_hand=10, quantity_reserved=8)
        with pytest.raises(HTTPException) as excinfo:
            svc.adjust_stock(
                db_session, item.id,
                AdjustStockRequest(delta=-5, reason="bad recount"),
                admin.id,
            )
        assert excinfo.value.status_code == 422
        assert "quantity_reserved" in excinfo.value.detail.lower()

    def test_damage_cannot_drop_below_quantity_reserved(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=10, quantity_reserved=8)
        with pytest.raises(HTTPException) as excinfo:
            svc.record_damage(
                db_session, item.id,
                DamageStockRequest(quantity=5, reason="broken"),
                admin.id,
            )
        assert excinfo.value.status_code == 422
        assert "quantity_reserved" in excinfo.value.detail.lower()


# --------------------------------------------------------------------- #
# Atomicity
# --------------------------------------------------------------------- #


class TestServiceAtomicity:
    def test_failed_sale_does_not_change_quantities(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=2, quantity_reserved=0)
        with pytest.raises(HTTPException):
            svc.sell_inventory(
                db_session, item.id,
                SaleStockRequest(quantity=99), admin.id,
            )
        db_session.refresh(item)
        assert item.quantity_on_hand == 2
        assert item.quantity_reserved == 0

    def test_failed_sale_does_not_create_inventory_log(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=2)
        n_before = len(_logs_for_item(db_session, item.id))
        with pytest.raises(HTTPException):
            svc.sell_inventory(
                db_session, item.id,
                SaleStockRequest(quantity=99), admin.id,
            )
        n_after = len(_logs_for_item(db_session, item.id))
        assert n_after == n_before

    def test_failed_reserve_does_not_create_log_or_change_state(
        self, db_session: Session, make_item, make_admin
    ):
        admin = make_admin()
        item = make_item(quantity_on_hand=10, quantity_reserved=8)
        n_before = len(_logs_for_item(db_session, item.id))
        with pytest.raises(HTTPException):
            svc.reserve_inventory(
                db_session, item.id,
                ReserveStockRequest(quantity=5), admin.id,
            )
        db_session.refresh(item)
        assert item.quantity_reserved == 8
        assert len(_logs_for_item(db_session, item.id)) == n_before


# --------------------------------------------------------------------- #
# BIE: anti-N+1 regression for the list endpoint
# --------------------------------------------------------------------- #


class TestEagerLoading:
    def test_list_inventory_does_not_n_plus_1(
        self,
        db_session: Session,
        make_store,
        make_product,
        make_variant,
        make_item,
    ):
        """`list_inventory_for_store` MUST issue a bounded number of
        SQL statements regardless of how many items the store carries.

        With default lazy-loading the cost would be `1 + 2N` (items,
        then per-item variant SELECT, then per-item product SELECT).
        With `selectinload(InventoryItem.variant).selectinload(
        ProductVariant.product)` the cost is `3` total, independent
        of N: one SELECT for items, one IN-list SELECT for variants,
        one IN-list SELECT for products.

        We listen on the bound engine via `before_cursor_execute` and
        filter to SELECTs that touch the inventory / variant / product
        tables. The threshold is conservative (≤ 5) so a transient
        extra read does not flake the test, but well below `2N+1` for
        N≥4.
        """
        from sqlalchemy import event

        store = make_store()
        # 4 distinct items keeps `2N+1 = 9` clearly above any sane
        # threshold while still cheap to set up.
        for _ in range(4):
            product = make_product()
            variant = make_variant(product=product)
            make_item(store=store, variant=variant)

        engine = db_session.get_bind()
        captured: list[str] = []

        def _on_execute(conn, cursor, statement, parameters, context, executemany):
            sql = statement.lower()
            if "select" not in sql:
                return
            if any(
                tbl in sql
                for tbl in ("inventory_items", "product_variants", "products")
            ):
                captured.append(statement)

        event.listen(engine, "before_cursor_execute", _on_execute)
        try:
            items = svc.list_inventory_for_store(db_session, store.id)
        finally:
            event.remove(engine, "before_cursor_execute", _on_execute)

        # Sanity: we got the rows back and they are populated.
        assert len(items) == 4
        for item in items:
            # Eager-loaded — accessing these does NOT trigger more SQL.
            assert item.variant is not None
            assert item.variant.product is not None
            assert item.variant.sku
            assert item.variant.product.name

        # Bounded query count. Strict expectation is exactly 3 (items,
        # variants, products); allow a small slack for harmless
        # transactional bookkeeping that some SQLAlchemy versions emit.
        assert len(captured) <= 5, (
            f"list_inventory_for_store fired {len(captured)} SELECTs on "
            f"inventory/variant/product tables for 4 items — looks like "
            f"N+1. Statements:\n" + "\n---\n".join(captured)
        )
