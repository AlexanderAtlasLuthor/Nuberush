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
from datetime import UTC
from datetime import datetime
from datetime import timedelta
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
        reorder_threshold: int = 0,
        status: InventoryStatus = InventoryStatus.available,
    ) -> InventoryItem:
        s = store if store is not None else make_store()
        v = variant if variant is not None else make_variant()
        item = InventoryItem(
            store_id=s.id,
            variant_id=v.id,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            reorder_threshold=reorder_threshold,
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


def _pin_created_at(
    db_session: Session,
    items: list[InventoryItem],
    *,
    start: datetime | None = None,
    same_timestamp: bool = False,
) -> None:
    base = start or datetime(2025, 1, 1, tzinfo=UTC)
    for index, item in enumerate(items):
        item.created_at = (
            base if same_timestamp else base + timedelta(minutes=index)
        )
    db_session.commit()
    for item in items:
        db_session.refresh(item)


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
# Pagination
# --------------------------------------------------------------------- #


class TestServicePagination:
    def test_list_inventory_respects_limit_offset(
        self, db_session: Session, make_store, make_item
    ):
        store = make_store()
        items = [make_item(store=store) for _ in range(4)]
        _pin_created_at(db_session, items)

        page = svc.list_inventory_for_store(
            db_session, store.id, limit=2, offset=1
        )

        assert [item.id for item in page] == [item.id for item in items[1:3]]

    def test_count_inventory_returns_full_filtered_count(
        self, db_session: Session, make_store, make_item
    ):
        store = make_store()
        other_store = make_store()
        items = [make_item(store=store) for _ in range(5)]
        make_item(store=other_store)
        _pin_created_at(db_session, items)

        page = svc.list_inventory_for_store(
            db_session, store.id, limit=2, offset=0
        )
        total = svc.count_inventory_for_store(db_session, store.id)

        assert len(page) == 2
        assert total == 5

    def test_low_stock_count_matches_filter(
        self, db_session: Session, make_store, make_item
    ):
        store = make_store()
        other_store = make_store()
        low_a = make_item(
            store=store,
            quantity_on_hand=3,
            quantity_reserved=1,
            reorder_threshold=2,
        )
        not_low = make_item(
            store=store,
            quantity_on_hand=10,
            quantity_reserved=1,
            reorder_threshold=2,
        )
        low_b = make_item(
            store=store,
            quantity_on_hand=0,
            quantity_reserved=0,
            reorder_threshold=0,
        )
        make_item(
            store=other_store,
            quantity_on_hand=0,
            quantity_reserved=0,
            reorder_threshold=0,
        )
        _pin_created_at(db_session, [low_a, not_low, low_b])

        rows = svc.list_inventory_for_store(
            db_session, store.id, low_stock_only=True
        )
        total = svc.count_inventory_for_store(
            db_session, store.id, low_stock_only=True
        )

        assert [item.id for item in rows] == [low_a.id, low_b.id]
        assert total == 2

    def test_stable_ordering_uses_created_at_then_id(
        self, db_session: Session, make_store, make_item
    ):
        store = make_store()
        items = [make_item(store=store) for _ in range(3)]
        _pin_created_at(db_session, items, same_timestamp=True)

        rows = svc.list_inventory_for_store(
            db_session, store.id, limit=3, offset=0
        )

        assert [str(item.id) for item in rows] == sorted(
            str(item.id) for item in items
        )


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


# --------------------------------------------------------------------- #
# Admin global feed (F2.18.1)
# --------------------------------------------------------------------- #


@pytest.fixture
def make_non_admin(db_session: Session, make_store) -> Callable[..., User]:
    def _create(role: UserRole = UserRole.owner) -> User:
        store = make_store()
        user = User(
            full_name=f"Inv Svc {role.value}",
            email=f"{role.value}-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("supersecret123"),
            role=role,
            store_id=store.id,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


def _pin_updated_at(
    db_session: Session,
    items: list[InventoryItem],
    *,
    start: datetime | None = None,
    same_timestamp: bool = False,
) -> None:
    """Pin updated_at to deterministic values for sort-order assertions.

    Mirrors _pin_created_at but targets updated_at. A BEFORE UPDATE
    trigger (`trg_inventory_items_set_updated_at`) normally overwrites
    `NEW.updated_at = now()` on every UPDATE, which would clobber any
    value we tried to write. The helper disables the trigger inside the
    active test transaction so the manual values stick; the test session
    rolls back at teardown so production behavior is never affected.
    """
    from sqlalchemy import text

    db_session.execute(
        text(
            "ALTER TABLE inventory_items "
            "DISABLE TRIGGER trg_inventory_items_set_updated_at"
        )
    )
    try:
        base = start or datetime(2025, 6, 1, tzinfo=UTC)
        for index, item in enumerate(items):
            item.updated_at = (
                base if same_timestamp else base + timedelta(minutes=index)
            )
        db_session.commit()
    finally:
        db_session.execute(
            text(
                "ALTER TABLE inventory_items "
                "ENABLE TRIGGER trg_inventory_items_set_updated_at"
            )
        )
        db_session.commit()
    for item in items:
        db_session.refresh(item)


class TestServiceAdminInventoryRBAC:
    def test_non_admin_forbidden(
        self, db_session: Session, make_non_admin
    ):
        owner = make_non_admin(role=UserRole.owner)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_admin_inventory(db_session, actor=owner)
        assert excinfo.value.status_code == 403

    @pytest.mark.parametrize(
        "role",
        [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver],
    )
    def test_every_non_admin_role_forbidden(
        self, db_session: Session, make_non_admin, role
    ):
        actor = make_non_admin(role=role)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_admin_inventory(db_session, actor=actor)
        assert excinfo.value.status_code == 403

    def test_admin_allowed_empty(
        self, db_session: Session, make_admin
    ):
        admin = make_admin()
        response = svc.list_admin_inventory(db_session, actor=admin)
        assert response.total == 0
        assert response.items == []
        assert response.limit == 100
        assert response.offset == 0


class TestServiceAdminInventoryGlobalFeed:
    def test_returns_items_from_multiple_stores(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store_a = make_store()
        store_b = make_store()
        item_a = make_item(store=store_a)
        item_b = make_item(store=store_b)

        response = svc.list_admin_inventory(db_session, actor=admin)

        ids = {item.id for item in response.items}
        assert item_a.id in ids
        assert item_b.id in ids
        assert response.total >= 2

    def test_total_counts_pre_pagination(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        items = [make_item(store=store) for _ in range(5)]
        _pin_updated_at(db_session, items)

        response = svc.list_admin_inventory(
            db_session, actor=admin, store_id=store.id, limit=2, offset=0
        )

        assert response.total == 5
        assert len(response.items) == 2

    def test_pagination_offset_advances(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        items = [make_item(store=store) for _ in range(4)]
        _pin_updated_at(db_session, items)

        first_page = svc.list_admin_inventory(
            db_session, actor=admin, store_id=store.id, limit=2, offset=0
        )
        second_page = svc.list_admin_inventory(
            db_session, actor=admin, store_id=store.id, limit=2, offset=2
        )

        first_ids = [item.id for item in first_page.items]
        second_ids = [item.id for item in second_page.items]
        assert set(first_ids).isdisjoint(set(second_ids))
        assert len(first_ids) == 2
        assert len(second_ids) == 2

    def test_sort_updated_at_desc_then_id_asc(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        # Three items with the SAME updated_at to force id ASC tie-break.
        items = [make_item(store=store) for _ in range(3)]
        _pin_updated_at(db_session, items, same_timestamp=True)

        response = svc.list_admin_inventory(
            db_session, actor=admin, store_id=store.id, limit=10, offset=0
        )

        returned_ids = [str(item.id) for item in response.items]
        assert returned_ids == sorted(str(item.id) for item in items)

    def test_sort_newer_updated_at_first(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        items = [make_item(store=store) for _ in range(3)]
        # Distinct ascending timestamps → newest must come first.
        _pin_updated_at(db_session, items)

        response = svc.list_admin_inventory(
            db_session, actor=admin, store_id=store.id, limit=10, offset=0
        )

        returned_ids = [item.id for item in response.items]
        assert returned_ids == [items[2].id, items[1].id, items[0].id]


class TestServiceAdminInventoryStoreScope:
    def test_store_id_filter_returns_only_that_store(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store_a = make_store()
        store_b = make_store()
        item_a = make_item(store=store_a)
        make_item(store=store_b)

        response = svc.list_admin_inventory(
            db_session, actor=admin, store_id=store_a.id
        )

        returned_ids = {item.id for item in response.items}
        assert returned_ids == {item_a.id}
        # All returned rows belong to store_a.
        for item in response.items:
            assert item.store_id == store_a.id

    def test_unknown_store_id_raises_404(
        self, db_session: Session, make_admin
    ):
        admin = make_admin()
        with pytest.raises(HTTPException) as excinfo:
            svc.list_admin_inventory(
                db_session, actor=admin, store_id=uuid.uuid4()
            )
        assert excinfo.value.status_code == 404
        assert "store" in excinfo.value.detail.lower()

    def test_inactive_store_id_returns_data(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        """Admin retains visibility into deactivated stores.

        Mirrors F2.17.4 `list_admin_audit` semantics: inactive stores
        still serve history; only unknown ones 404.
        """
        admin = make_admin()
        store = make_store()
        item = make_item(store=store)
        # Deactivate the store directly on the row.
        store.is_active = False
        db_session.commit()

        response = svc.list_admin_inventory(
            db_session, actor=admin, store_id=store.id
        )

        ids = {row.id for row in response.items}
        assert item.id in ids


class TestServiceAdminInventoryFilters:
    def test_low_stock_filter(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        low = make_item(
            store=store,
            quantity_on_hand=2,
            quantity_reserved=1,
            reorder_threshold=2,
        )
        not_low = make_item(
            store=store,
            quantity_on_hand=20,
            quantity_reserved=0,
            reorder_threshold=2,
        )

        response = svc.list_admin_inventory(
            db_session, actor=admin, store_id=store.id, low_stock=True
        )

        ids = {item.id for item in response.items}
        assert low.id in ids
        assert not_low.id not in ids
        assert response.total == 1

    def test_status_filter(
        self, db_session: Session, make_admin, make_store, make_item
    ):
        admin = make_admin()
        store = make_store()
        flagged = make_item(store=store, status=InventoryStatus.flagged)
        make_item(store=store, status=InventoryStatus.available)

        response = svc.list_admin_inventory(
            db_session,
            actor=admin,
            store_id=store.id,
            inventory_status=InventoryStatus.flagged,
        )

        assert {item.id for item in response.items} == {flagged.id}

    def test_variant_id_filter(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_variant,
        make_item,
    ):
        admin = make_admin()
        store_a = make_store()
        store_b = make_store()
        target_variant = make_variant()
        other_variant = make_variant()
        wanted_a = make_item(store=store_a, variant=target_variant)
        wanted_b = make_item(store=store_b, variant=target_variant)
        make_item(store=store_a, variant=other_variant)

        response = svc.list_admin_inventory(
            db_session, actor=admin, variant_id=target_variant.id
        )

        ids = {item.id for item in response.items}
        assert ids == {wanted_a.id, wanted_b.id}

    def test_product_id_filter(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_product,
        make_variant,
        make_item,
    ):
        admin = make_admin()
        store = make_store()
        target_product = make_product()
        other_product = make_product()
        target_variant = make_variant(product=target_product)
        other_variant = make_variant(product=other_product)
        wanted = make_item(store=store, variant=target_variant)
        make_item(store=store, variant=other_variant)

        response = svc.list_admin_inventory(
            db_session, actor=admin, product_id=target_product.id
        )

        ids = {item.id for item in response.items}
        assert ids == {wanted.id}

    def test_q_matches_variant_sku(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_variant,
        make_item,
    ):
        admin = make_admin()
        store = make_store()
        target_variant = make_variant()
        other_variant = make_variant()
        wanted = make_item(store=store, variant=target_variant)
        make_item(store=store, variant=other_variant)

        # Take a unique substring from the target SKU.
        sku_fragment = target_variant.sku[-6:]

        response = svc.list_admin_inventory(
            db_session, actor=admin, q=sku_fragment
        )

        ids = {item.id for item in response.items}
        assert wanted.id in ids
        # Other variants happen to be different uuid-derived SKUs, so
        # they should not match this fragment.
        for item in response.items:
            assert sku_fragment.lower() in (
                item.variant.sku.lower()
                if item.variant.sku
                else ""
            ) or sku_fragment.lower() in (
                item.variant.product.name.lower()
                if item.variant.product.name
                else ""
            )

    def test_q_matches_product_name(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_product,
        make_variant,
        make_item,
    ):
        admin = make_admin()
        store = make_store()
        target_product = make_product()
        target_variant = make_variant(product=target_product)
        make_item(store=store, variant=target_variant)

        # Take a unique substring from the target product name.
        name_fragment = target_product.name[-4:]

        response = svc.list_admin_inventory(
            db_session, actor=admin, q=name_fragment
        )

        # The target item must appear.
        product_names = {
            item.variant.product.name for item in response.items
        }
        assert target_product.name in product_names

    def test_q_whitespace_only_collapses_to_no_filter(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_item,
    ):
        admin = make_admin()
        store = make_store()
        item = make_item(store=store)

        response = svc.list_admin_inventory(
            db_session, actor=admin, store_id=store.id, q="   "
        )

        ids = {row.id for row in response.items}
        assert item.id in ids


class TestServiceStoreScopedRegression:
    """F2.18.1 must not change the store-scoped service surface."""

    def test_list_inventory_for_store_unchanged(
        self, db_session: Session, make_store, make_item
    ):
        store = make_store()
        items = [make_item(store=store) for _ in range(2)]
        _pin_created_at(db_session, items)

        rows = svc.list_inventory_for_store(db_session, store.id)

        assert {row.id for row in rows} == {item.id for item in items}

    def test_count_inventory_for_store_unchanged(
        self, db_session: Session, make_store, make_item
    ):
        store = make_store()
        for _ in range(3):
            make_item(store=store)

        assert svc.count_inventory_for_store(db_session, store.id) == 3
