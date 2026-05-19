"""Service-layer tests for the admin operations alerts feed (F2.19.2).

Exercises `app.services.admin_operations.list_admin_operations_alerts`
against the real test DB via the `db_session` fixture from conftest.

Covers (per F2.19.2 requirements):

  1. Admin happy path / envelope.
  2. Non-admin forbidden (every non-admin role).
  3. low_stock category: predicate, severity buckets, deterministic id.
  4. aging_order category: open-status filter, severity thresholds,
     deterministic id including aging_minutes suffix.
  5. compliance_blocker category: allowed_for_sale + banned +
     restricted, deterministic id.
  6. inactive_store category: is_active=False, severity, id.
  7. store_no_inventory category: zero InventoryItem rows, id.
  8. category filter.
  9. severity filter.
  10. store_id filter (excludes alerts with store_id=None).
  11. aging_minutes threshold + id-suffix behavior.
  12. total before pagination.
  13. limit/offset pagination.
  14. Deterministic ordering (severity DESC, created_at DESC,
      category ASC, entity_id ASC).
  15. Read-only invariants.

Style mirrors test_admin_dashboard_service.py + test_audit_service.py.
"""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy import text
from sqlalchemy.orm import Session

from tests.helpers.auth import make_password_hash
from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import InventoryStatus
from app.db.models import Order
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.admin_operations import AdminOperationsAlertCategory
from app.schemas.admin_operations import AdminOperationsAlertEntityType
from app.schemas.admin_operations import AdminOperationsAlertSeverity
from app.services import admin_operations as svc


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(
        *, name: str | None = None, is_active: bool = True
    ) -> Store:
        store = Store(
            name=name or f"OpsSvc-{uuid.uuid4().hex[:6]}",
            code=f"os-{uuid.uuid4().hex[:8]}",
            is_active=is_active,
        )
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_user(db_session: Session) -> Callable[..., User]:
    def _create(
        *,
        role: UserRole,
        store_id: uuid.UUID | None = None,
        is_active: bool = True,
    ) -> User:
        sid = None if role == UserRole.admin else store_id
        user = User(
            full_name=f"OpsSvc {role.value}",
            email=f"{role.value}-{uuid.uuid4().hex[:10]}@example.com",
            password_hash=make_password_hash("supersecret123"),
            role=role,
            store_id=sid,
            is_active=is_active,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


@pytest.fixture
def make_admin(make_user) -> Callable[..., User]:
    def _create() -> User:
        return make_user(role=UserRole.admin)

    return _create


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create(
        *,
        compliance_status: ComplianceStatus = ComplianceStatus.allowed,
        allowed_for_sale: bool = True,
    ) -> Product:
        product = Product(
            name=f"P-{uuid.uuid4().hex[:6]}",
            category="vape",
            compliance_status=compliance_status,
            allowed_for_sale=allowed_for_sale,
            is_active=True,
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
    def _create(*, product: Product | None = None) -> ProductVariant:
        prod = product if product is not None else make_product()
        variant = ProductVariant(
            product_id=prod.id,
            sku=f"SKU-{uuid.uuid4().hex[:8]}",
            price=Decimal("9.99"),
            is_active=True,
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
        *,
        store: Store | None = None,
        variant: ProductVariant | None = None,
        quantity_on_hand: int = 10,
        quantity_reserved: int = 0,
        reorder_threshold: int = 0,
    ) -> InventoryItem:
        s = store if store is not None else make_store()
        v = variant if variant is not None else make_variant()
        item = InventoryItem(
            store_id=s.id,
            variant_id=v.id,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=quantity_reserved,
            reorder_threshold=reorder_threshold,
            status=InventoryStatus.available,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        return item

    return _create


@pytest.fixture
def make_order(db_session: Session) -> Callable[..., Order]:
    def _create(
        *,
        store: Store,
        order_status: OrderStatus = OrderStatus.pending,
        created_at: datetime | None = None,
    ) -> Order:
        order = Order(
            store_id=store.id,
            idempotency_key=f"idem-{uuid.uuid4().hex[:8]}",
            status=order_status,
            subtotal_amount=Decimal("0.00"),
            tax_amount=Decimal("0.00"),
            total_amount=Decimal("0.00"),
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)
        if created_at is not None:
            order.created_at = created_at
            db_session.commit()
            db_session.refresh(order)
        return order

    return _create


def _pin_updated_at(
    db_session: Session,
    table: str,
    trigger: str,
    rows: list,
    when: datetime,
) -> None:
    """Set `updated_at` on rows while temporarily disabling the
    `BEFORE UPDATE` trigger that would otherwise clobber the value
    with `now()`.

    Used in deterministic-ordering tests where alerts need to share
    a known `created_at` (which the service sources from `updated_at`
    for store / product / inventory-item alerts).
    """
    db_session.execute(
        text(f"ALTER TABLE {table} DISABLE TRIGGER {trigger}")
    )
    try:
        for row in rows:
            row.updated_at = when
        db_session.commit()
    finally:
        db_session.execute(
            text(f"ALTER TABLE {table} ENABLE TRIGGER {trigger}")
        )
        db_session.commit()
    for row in rows:
        db_session.refresh(row)


# --------------------------------------------------------------------- #
# A. RBAC + envelope
# --------------------------------------------------------------------- #


class TestRBAC:
    def test_admin_happy_path_empty_db(
        self, db_session: Session, make_admin
    ):
        admin = make_admin()
        response = svc.list_admin_operations_alerts(
            db_session, actor=admin
        )
        assert response.items == []
        assert response.total == 0
        assert response.limit == 50
        assert response.offset == 0

    @pytest.mark.parametrize(
        "role",
        [
            UserRole.owner,
            UserRole.manager,
            UserRole.staff,
            UserRole.driver,
        ],
    )
    def test_non_admin_forbidden(
        self,
        db_session: Session,
        make_store,
        make_user,
        role: UserRole,
    ):
        store = make_store()
        actor = make_user(role=role, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_admin_operations_alerts(db_session, actor=actor)
        assert excinfo.value.status_code == 403


# --------------------------------------------------------------------- #
# B. low_stock category
# --------------------------------------------------------------------- #


class TestLowStock:
    def test_high_when_available_zero_or_less(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_item,
    ):
        admin = make_admin()
        store = make_store()
        item = make_item(
            store=store,
            quantity_on_hand=0,
            quantity_reserved=0,
            reorder_threshold=0,
        )

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.low_stock,
        )
        assert response.total == 1
        alert = response.items[0]
        assert alert.severity == AdminOperationsAlertSeverity.high
        assert alert.id == f"low_stock:{item.id}"
        assert alert.category == AdminOperationsAlertCategory.low_stock
        assert alert.entity_type == (
            AdminOperationsAlertEntityType.inventory_item
        )
        assert alert.entity_id == item.id
        assert alert.store_id == store.id

    def test_medium_when_available_le_threshold_and_positive(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_item,
    ):
        admin = make_admin()
        store = make_store()
        # available = 2, threshold = 5 → medium (2 <= 5 AND 2 > 0)
        item = make_item(
            store=store,
            quantity_on_hand=2,
            quantity_reserved=0,
            reorder_threshold=5,
        )

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.low_stock,
        )
        assert response.total == 1
        assert response.items[0].severity == (
            AdminOperationsAlertSeverity.medium
        )
        assert response.items[0].id == f"low_stock:{item.id}"

    def test_healthy_item_does_not_generate_alert(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_item,
    ):
        admin = make_admin()
        store = make_store()
        # available = 10 > threshold = 3 → no alert.
        make_item(
            store=store,
            quantity_on_hand=10,
            quantity_reserved=0,
            reorder_threshold=3,
        )

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.low_stock,
        )
        assert response.total == 0


# --------------------------------------------------------------------- #
# C. aging_order category
# --------------------------------------------------------------------- #


class TestAgingOrder:
    def test_open_status_aged_past_threshold_qualifies_medium(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_order,
    ):
        admin = make_admin()
        store = make_store()
        # 90 mins old; threshold 60 mins → age 90 >= 60 but
        # < 2*60=120 → medium.
        ninety_min_ago = datetime.now(UTC) - timedelta(minutes=90)
        order = make_order(
            store=store,
            order_status=OrderStatus.pending,
            created_at=ninety_min_ago,
        )

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.aging_order,
            aging_minutes=60,
        )
        assert response.total == 1
        alert = response.items[0]
        assert alert.severity == AdminOperationsAlertSeverity.medium
        assert alert.id == f"aging_order:{order.id}:60"
        assert alert.entity_type == AdminOperationsAlertEntityType.order
        assert alert.store_id == store.id

    def test_high_when_age_at_least_double_threshold(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_order,
    ):
        admin = make_admin()
        store = make_store()
        # ~3 hours old; threshold 60 mins → age 180 >= 2*60=120 → high.
        three_hours_ago = datetime.now(UTC) - timedelta(hours=3)
        order = make_order(
            store=store,
            order_status=OrderStatus.preparing,
            created_at=three_hours_ago,
        )

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.aging_order,
            aging_minutes=60,
        )
        assert response.total == 1
        assert response.items[0].severity == (
            AdminOperationsAlertSeverity.high
        )
        assert response.items[0].id == f"aging_order:{order.id}:60"

    def test_younger_than_threshold_excluded(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_order,
    ):
        admin = make_admin()
        store = make_store()
        # 5 minutes old; default threshold 1440 → excluded.
        five_min_ago = datetime.now(UTC) - timedelta(minutes=5)
        make_order(
            store=store,
            order_status=OrderStatus.pending,
            created_at=five_min_ago,
        )

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.aging_order,
        )
        assert response.total == 0

    @pytest.mark.parametrize(
        "closed_status",
        [
            OrderStatus.delivered,
            OrderStatus.canceled,
            OrderStatus.returned,
        ],
    )
    def test_closed_statuses_excluded(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_order,
        closed_status: OrderStatus,
    ):
        admin = make_admin()
        store = make_store()
        twelve_hours_ago = datetime.now(UTC) - timedelta(hours=12)
        make_order(
            store=store,
            order_status=closed_status,
            created_at=twelve_hours_ago,
        )

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.aging_order,
            aging_minutes=60,
        )
        assert response.total == 0


# --------------------------------------------------------------------- #
# D. compliance_blocker category
# --------------------------------------------------------------------- #


class TestComplianceBlocker:
    def test_allowed_for_sale_false_is_high(
        self,
        db_session: Session,
        make_admin,
        make_product,
    ):
        admin = make_admin()
        product = make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=False,
        )

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.compliance_blocker,
        )
        assert response.total == 1
        alert = response.items[0]
        assert alert.severity == AdminOperationsAlertSeverity.high
        assert alert.id == f"compliance_blocker:{product.id}"
        assert alert.entity_type == (
            AdminOperationsAlertEntityType.product
        )
        # Product has no store_id column → alert.store_id is None.
        assert alert.store_id is None

    def test_banned_status_is_high(
        self,
        db_session: Session,
        make_admin,
        make_product,
    ):
        admin = make_admin()
        # CHECK constraint: banned → allowed_for_sale must be False.
        product = make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.compliance_blocker,
        )
        assert response.total == 1
        assert response.items[0].severity == (
            AdminOperationsAlertSeverity.high
        )
        assert response.items[0].id == f"compliance_blocker:{product.id}"

    def test_restricted_status_with_allowed_true_is_medium(
        self,
        db_session: Session,
        make_admin,
        make_product,
    ):
        admin = make_admin()
        product = make_product(
            compliance_status=ComplianceStatus.restricted,
            allowed_for_sale=True,
        )

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.compliance_blocker,
        )
        assert response.total == 1
        assert response.items[0].severity == (
            AdminOperationsAlertSeverity.medium
        )
        assert response.items[0].id == f"compliance_blocker:{product.id}"

    def test_allowed_product_generates_no_alert(
        self,
        db_session: Session,
        make_admin,
        make_product,
    ):
        admin = make_admin()
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.compliance_blocker,
        )
        assert response.total == 0


# --------------------------------------------------------------------- #
# E. inactive_store category
# --------------------------------------------------------------------- #


class TestInactiveStore:
    def test_inactive_store_yields_medium_alert(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_item,
    ):
        admin = make_admin()
        # Give the inactive store inventory so store_no_inventory
        # doesn't fire — keeps this test focused on inactive_store.
        store = make_store(is_active=False)
        make_item(store=store)

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.inactive_store,
        )
        assert response.total == 1
        alert = response.items[0]
        assert alert.severity == AdminOperationsAlertSeverity.medium
        assert alert.id == f"inactive_store:{store.id}"
        assert alert.entity_type == AdminOperationsAlertEntityType.store
        assert alert.store_id == store.id
        assert alert.entity_id == store.id

    def test_active_store_does_not_alert(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_item,
    ):
        admin = make_admin()
        store = make_store(is_active=True)
        make_item(store=store)

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.inactive_store,
        )
        assert response.total == 0


# --------------------------------------------------------------------- #
# F. store_no_inventory category
# --------------------------------------------------------------------- #


class TestStoreNoInventory:
    def test_store_with_zero_items_yields_medium_alert(
        self,
        db_session: Session,
        make_admin,
        make_store,
    ):
        admin = make_admin()
        store = make_store()  # no items attached.

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.store_no_inventory,
        )
        assert response.total == 1
        alert = response.items[0]
        assert alert.severity == AdminOperationsAlertSeverity.medium
        assert alert.id == f"store_no_inventory:{store.id}"
        assert alert.entity_type == AdminOperationsAlertEntityType.store
        assert alert.store_id == store.id

    def test_store_with_items_does_not_alert(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_item,
    ):
        admin = make_admin()
        store = make_store()
        make_item(store=store)

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.store_no_inventory,
        )
        assert response.total == 0


# --------------------------------------------------------------------- #
# G. Filters
# --------------------------------------------------------------------- #


class TestFilters:
    def test_category_filter_isolates_one_kind(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_product,
    ):
        admin = make_admin()
        make_store(is_active=False)  # inactive_store + store_no_inventory
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=False,
        )  # compliance_blocker

        # Without filter we should see 3 alerts.
        all_response = svc.list_admin_operations_alerts(
            db_session, actor=admin
        )
        assert all_response.total == 3

        # category=compliance_blocker should isolate that one.
        cb_response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.compliance_blocker,
        )
        assert cb_response.total == 1
        assert all(
            a.category == AdminOperationsAlertCategory.compliance_blocker
            for a in cb_response.items
        )

    def test_severity_filter(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_product,
        make_item,
    ):
        admin = make_admin()
        # High alert: out-of-stock item.
        store_h = make_store()
        make_item(
            store=store_h,
            quantity_on_hand=0,
            quantity_reserved=0,
            reorder_threshold=0,
        )
        # Medium alert: inactive store (and store_no_inventory).
        make_store(is_active=False)

        high_response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            severity=AdminOperationsAlertSeverity.high,
        )
        assert high_response.total >= 1
        assert all(
            a.severity == AdminOperationsAlertSeverity.high
            for a in high_response.items
        )

        med_response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            severity=AdminOperationsAlertSeverity.medium,
        )
        assert med_response.total >= 1
        assert all(
            a.severity == AdminOperationsAlertSeverity.medium
            for a in med_response.items
        )

    def test_store_id_filter_excludes_other_stores_and_global_alerts(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_product,
    ):
        admin = make_admin()
        store_a = make_store(is_active=False)  # alerts at store_a
        make_store(is_active=False)  # alerts at a different store
        # compliance_blocker → store_id None, should be excluded.
        make_product(allowed_for_sale=False)

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin, store_id=store_a.id
        )
        assert response.total >= 1
        for alert in response.items:
            assert alert.store_id == store_a.id


# --------------------------------------------------------------------- #
# H. aging_minutes behavior + id suffix
# --------------------------------------------------------------------- #


class TestAgingMinutesBehavior:
    def test_threshold_affects_inclusion(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_order,
    ):
        admin = make_admin()
        store = make_store()
        # 90 minutes old.
        order = make_order(
            store=store,
            order_status=OrderStatus.pending,
            created_at=datetime.now(UTC) - timedelta(minutes=90),
        )

        # aging_minutes=60 → 90 >= 60 → included.
        r60 = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.aging_order,
            aging_minutes=60,
        )
        assert r60.total == 1
        assert r60.items[0].id == f"aging_order:{order.id}:60"

        # aging_minutes=120 → 90 < 120 → excluded.
        r120 = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.aging_order,
            aging_minutes=120,
        )
        assert r120.total == 0

    def test_id_suffix_changes_with_aging_minutes(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_order,
    ):
        admin = make_admin()
        store = make_store()
        order = make_order(
            store=store,
            order_status=OrderStatus.pending,
            created_at=datetime.now(UTC) - timedelta(hours=8),
        )

        r1 = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.aging_order,
            aging_minutes=60,
        )
        r2 = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.aging_order,
            aging_minutes=30,
        )
        assert r1.items[0].id == f"aging_order:{order.id}:60"
        assert r2.items[0].id == f"aging_order:{order.id}:30"
        assert r1.items[0].id != r2.items[0].id


# --------------------------------------------------------------------- #
# I. Pagination
# --------------------------------------------------------------------- #


class TestPagination:
    def test_total_is_pre_pagination(
        self,
        db_session: Session,
        make_admin,
        make_store,
    ):
        admin = make_admin()
        # 5 stores, all inactive → 5 inactive_store + 5 store_no_inventory = 10 alerts.
        for _ in range(5):
            make_store(is_active=False)

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin, limit=2, offset=0
        )
        assert response.total == 10
        assert len(response.items) == 2

    def test_offset_paginates(
        self,
        db_session: Session,
        make_admin,
        make_store,
    ):
        admin = make_admin()
        for _ in range(5):
            make_store(is_active=False)  # 10 alerts total

        first = svc.list_admin_operations_alerts(
            db_session, actor=admin, limit=4, offset=0
        )
        second = svc.list_admin_operations_alerts(
            db_session, actor=admin, limit=4, offset=4
        )
        first_ids = {a.id for a in first.items}
        second_ids = {a.id for a in second.items}
        assert first_ids.isdisjoint(second_ids)
        assert len(first.items) == 4
        assert len(second.items) == 4

    def test_offset_beyond_total_returns_empty(
        self,
        db_session: Session,
        make_admin,
        make_store,
    ):
        admin = make_admin()
        make_store(is_active=False)

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin, limit=10, offset=999
        )
        assert response.total >= 1
        assert response.items == []


# --------------------------------------------------------------------- #
# J. Deterministic ordering
# --------------------------------------------------------------------- #


class TestDeterministicOrdering:
    def test_severity_priority_high_then_medium(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_item,
    ):
        admin = make_admin()
        # High alert: out-of-stock item.
        store_h = make_store()
        make_item(
            store=store_h,
            quantity_on_hand=0,
            quantity_reserved=0,
            reorder_threshold=0,
        )
        # Medium alerts: inactive store + store_no_inventory.
        make_store(is_active=False)

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin
        )
        # First item must be high; once we hit medium we never see
        # high again.
        seen_medium = False
        for alert in response.items:
            if alert.severity == AdminOperationsAlertSeverity.medium:
                seen_medium = True
            elif alert.severity == AdminOperationsAlertSeverity.high:
                assert not seen_medium, (
                    "High alert appeared after a medium alert — "
                    "severity DESC violated."
                )

    def test_created_at_desc_within_same_severity(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_order,
    ):
        admin = make_admin()
        store = make_store()
        # Three open orders at distinct created_at values, all in the
        # medium band (age between aging_minutes and 2*aging_minutes).
        # threshold=60 → 80m, 70m, 90m old.
        ages_minutes = [80, 70, 90]
        orders = [
            make_order(
                store=store,
                order_status=OrderStatus.pending,
                created_at=datetime.now(UTC) - timedelta(minutes=age),
            )
            for age in ages_minutes
        ]

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin,
            category=AdminOperationsAlertCategory.aging_order,
            aging_minutes=60,
        )
        # All three are medium (age < 2*60 = 120). created_at DESC →
        # newest first. Order by absolute created_at desc:
        # 70m old (newest) → 80m → 90m (oldest).
        returned_ids = [a.entity_id for a in response.items]
        expected_ids = [orders[1].id, orders[0].id, orders[2].id]
        assert returned_ids == expected_ids

    def test_category_then_entity_id_tiebreaker(
        self,
        db_session: Session,
        make_admin,
        make_store,
    ):
        """When severity AND created_at are identical, alerts must
        be sorted by category ASC, then entity_id ASC. We force
        equal `updated_at` on three inactive stores (each yielding
        `inactive_store` + `store_no_inventory` at the same time)
        and check that the secondary keys take effect.
        """
        admin = make_admin()
        stores = [make_store(is_active=False) for _ in range(3)]
        # Pin equal updated_at across all three stores.
        pinned = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        _pin_updated_at(
            db_session, "stores", "trg_stores_set_updated_at",
            stores, pinned,
        )

        response = svc.list_admin_operations_alerts(
            db_session, actor=admin
        )
        # All alerts are medium with identical created_at. The
        # ordering must collapse to (category ASC, entity_id ASC).
        # Two categories alphabetically: inactive_store before
        # store_no_inventory. Within each category, entity_id ASC.
        categories = [a.category.value for a in response.items]
        assert categories == sorted(categories)
        sorted_store_ids = sorted([s.id for s in stores], key=str)
        inactive_alerts = [
            a for a in response.items
            if a.category == (
                AdminOperationsAlertCategory.inactive_store
            )
        ]
        nostock_alerts = [
            a for a in response.items
            if a.category == (
                AdminOperationsAlertCategory.store_no_inventory
            )
        ]
        assert [a.entity_id for a in inactive_alerts] == sorted_store_ids
        assert [a.entity_id for a in nostock_alerts] == sorted_store_ids


# --------------------------------------------------------------------- #
# K. Read-only invariants
# --------------------------------------------------------------------- #


class TestReadOnly:
    def test_repeated_calls_create_no_rows(
        self,
        db_session: Session,
        make_admin,
        make_store,
        make_product,
        make_item,
        make_order,
    ):
        admin = make_admin()
        store = make_store(is_active=False)
        make_item(
            store=store,
            quantity_on_hand=0,
            reorder_threshold=0,
        )
        make_product(allowed_for_sale=False)
        make_order(
            store=store,
            order_status=OrderStatus.pending,
            created_at=datetime.now(UTC) - timedelta(hours=48),
        )

        def _snapshot() -> dict[str, int]:
            return {
                "stores": db_session.scalar(
                    select(func.count()).select_from(Store)
                ),
                "users": db_session.scalar(
                    select(func.count()).select_from(User)
                ),
                "items": db_session.scalar(
                    select(func.count()).select_from(InventoryItem)
                ),
                "orders": db_session.scalar(
                    select(func.count()).select_from(Order)
                ),
                "products": db_session.scalar(
                    select(func.count()).select_from(Product)
                ),
            }

        baseline = _snapshot()

        for _ in range(3):
            response = svc.list_admin_operations_alerts(
                db_session, actor=admin
            )
            assert response.total > 0  # sanity

        assert _snapshot() == baseline
