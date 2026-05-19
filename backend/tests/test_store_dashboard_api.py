"""API-level tests for the store-scoped dashboard endpoints.

Exercises the seven `GET /stores/{store_id}/...` routes the dashboard
home page consumes:

  /dashboard, /dashboard/kpis, /orders/summary, /inventory/summary,
  /products/summary, /activity, /alerts

Covered surfaces:

  - auth gate (anon → 401) on every endpoint.
  - RBAC matrix (admin/owner/manager/staff allowed; driver → 403;
    anon → 401).
  - tenancy collapse for non-admins (cross-store / unknown → 403).
  - admin against unknown store → 404; admin against inactive → 400.
  - response shape: KPI / summary aggregates match seeded state.
  - activity feed paginates and orders by `created_at DESC`.
  - alerts: low_stock + aging_order + no_inventory categories;
    severity filter; deterministic ids.
"""

from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import InventoryMovementType
from app.db.models import InventoryStatus
from app.db.models import Order
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(
        *, name: str = "SDash-API", is_active: bool = True
    ) -> Store:
        store = Store(
            name=name,
            code=f"sd-{uuid.uuid4().hex[:8]}",
            is_active=is_active,
        )
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


# Thin adapter over tests.helpers.auth.make_user (F2.22.2.C2).
@pytest.fixture
def make_user(
    db_session: Session, make_store
) -> Callable[..., User]:
    def _create(
        role: UserRole, store_id: uuid.UUID | None = None
    ) -> User:
        if role == UserRole.admin:
            sid = None
        else:
            sid = store_id if store_id is not None else make_store().id
        return central_make_user(
            db_session,
            role=role,
            store_id=sid,
            full_name=f"SDash {role.value}",
            is_active=True,
            password="supersecret123",
        )

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


@pytest.fixture
def make_log(db_session: Session) -> Callable[..., InventoryLog]:
    def _create(
        *,
        item: InventoryItem,
        created_at: datetime | None = None,
        delta: int = 5,
        after: int = 15,
    ) -> InventoryLog:
        log = InventoryLog(
            inventory_item_id=item.id,
            store_id=item.store_id,
            variant_id=item.variant_id,
            movement_type=InventoryMovementType.receipt,
            quantity_delta=delta,
            quantity_after=after,
        )
        db_session.add(log)
        db_session.commit()
        db_session.refresh(log)
        if created_at is not None:
            log.created_at = created_at
            db_session.commit()
            db_session.refresh(log)
        return log

    return _create


# All seven endpoints, parameterized for the cross-cutting auth/RBAC
# matrix. Path templates use `{store_id}` so each test fills in the
# concrete id under test.
ALL_PATHS = [
    "/stores/{store_id}/dashboard",
    "/stores/{store_id}/dashboard/kpis",
    "/stores/{store_id}/orders/summary",
    "/stores/{store_id}/inventory/summary",
    "/stores/{store_id}/products/summary",
    "/stores/{store_id}/activity",
    "/stores/{store_id}/alerts",
]


# --------------------------------------------------------------------- #
# Cross-cutting auth / RBAC / tenancy
# --------------------------------------------------------------------- #


class TestAuthRBAC:
    @pytest.mark.parametrize("path_tmpl", ALL_PATHS)
    def test_anonymous_returns_401(
        self, client: TestClient, make_store, path_tmpl: str
    ) -> None:
        store = make_store()
        resp = client.get(path_tmpl.format(store_id=store.id))
        assert resp.status_code == 401, resp.text

    @pytest.mark.parametrize("path_tmpl", ALL_PATHS)
    def test_driver_forbidden(
        self,
        client: TestClient,
        make_store,
        make_user,
        path_tmpl: str,
    ) -> None:
        store = make_store()
        driver = make_user(UserRole.driver, store_id=store.id)
        resp = client.get(
            path_tmpl.format(store_id=store.id), headers=_auth(driver)
        )
        assert resp.status_code == 403, resp.text

    @pytest.mark.parametrize("path_tmpl", ALL_PATHS)
    def test_cross_store_user_forbidden(
        self,
        client: TestClient,
        make_store,
        make_user,
        path_tmpl: str,
    ) -> None:
        store_a = make_store()
        store_b = make_store()
        intruder = make_user(UserRole.owner, store_id=store_a.id)
        resp = client.get(
            path_tmpl.format(store_id=store_b.id),
            headers=_auth(intruder),
        )
        # require_store_member collapses cross-store and unknown into
        # 403 for non-admins.
        assert resp.status_code == 403, resp.text

    @pytest.mark.parametrize("path_tmpl", ALL_PATHS)
    def test_admin_unknown_store_returns_404(
        self,
        client: TestClient,
        make_user,
        path_tmpl: str,
    ) -> None:
        admin = make_user(UserRole.admin)
        resp = client.get(
            path_tmpl.format(store_id=uuid.uuid4()),
            headers=_auth(admin),
        )
        assert resp.status_code == 404, resp.text

    @pytest.mark.parametrize("path_tmpl", ALL_PATHS)
    def test_admin_inactive_store_returns_400(
        self,
        client: TestClient,
        make_store,
        make_user,
        path_tmpl: str,
    ) -> None:
        store = make_store(is_active=False)
        admin = make_user(UserRole.admin)
        resp = client.get(
            path_tmpl.format(store_id=store.id), headers=_auth(admin)
        )
        assert resp.status_code == 400, resp.text

    @pytest.mark.parametrize(
        "role",
        [UserRole.owner, UserRole.manager, UserRole.staff],
    )
    @pytest.mark.parametrize("path_tmpl", ALL_PATHS)
    def test_in_store_roles_allowed(
        self,
        client: TestClient,
        make_store,
        make_user,
        role: UserRole,
        path_tmpl: str,
    ) -> None:
        store = make_store()
        user = make_user(role, store_id=store.id)
        resp = client.get(
            path_tmpl.format(store_id=store.id), headers=_auth(user)
        )
        assert resp.status_code == 200, resp.text


# --------------------------------------------------------------------- #
# /stores/{store_id}/dashboard
# --------------------------------------------------------------------- #


class TestDashboard:
    def test_envelope_keys(
        self, client: TestClient, make_store, make_user
    ) -> None:
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)
        resp = client.get(
            f"/stores/{store.id}/dashboard", headers=_auth(owner)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == {
            "store_id",
            "kpis",
            "orders",
            "inventory",
            "products",
            "recent_activity",
        }
        assert body["store_id"] == str(store.id)
        assert set(body["kpis"].keys()) == {
            "orders_open",
            "orders_by_status",
            "inventory_total_items",
            "inventory_low_stock",
            "products_in_store",
            "products_blocked",
        }
        # by_status is dense across every OrderStatus member.
        assert set(body["kpis"]["orders_by_status"].keys()) == {
            s.value for s in OrderStatus
        }

    def test_aggregates_reflect_seeded_state(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        make_order,
        make_log,
        make_variant,
        make_product,
    ) -> None:
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)

        # 2 inventory items, one low-stock, one healthy.
        low_variant = make_variant()
        low = make_item(
            store=store,
            variant=low_variant,
            quantity_on_hand=1,
            reorder_threshold=10,
        )
        healthy = make_item(
            store=store, quantity_on_hand=50, reorder_threshold=5
        )
        # Inventory log on the low-stock item so recent_activity is
        # non-empty.
        make_log(item=low)

        # Orders: 3 pending, 1 delivered.
        make_order(store=store, order_status=OrderStatus.pending)
        make_order(store=store, order_status=OrderStatus.pending)
        make_order(store=store, order_status=OrderStatus.pending)
        make_order(store=store, order_status=OrderStatus.delivered)

        # Cross-store noise that must NOT leak in.
        other_store = make_store()
        make_order(
            store=other_store, order_status=OrderStatus.pending
        )

        # Blocked product wired into this store via inventory.
        blocked_product = make_product(
            compliance_status=ComplianceStatus.restricted
        )
        blocked_variant = make_variant(product=blocked_product)
        make_item(store=store, variant=blocked_variant)

        resp = client.get(
            f"/stores/{store.id}/dashboard", headers=_auth(owner)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()

        kpis = body["kpis"]
        assert kpis["orders_open"] == 3
        assert kpis["orders_by_status"][OrderStatus.pending.value] == 3
        assert kpis["orders_by_status"][OrderStatus.delivered.value] == 1
        assert kpis["inventory_total_items"] == 3  # low + healthy + blocked
        assert kpis["inventory_low_stock"] >= 1
        assert kpis["products_in_store"] >= 1
        assert kpis["products_blocked"] >= 1

        # Inventory totals come from this store only.
        inv = body["inventory"]
        assert inv["total_items"] == 3
        assert inv["total_on_hand"] >= 51  # 1 + 50 + healthy's default

        # Recent activity is bounded at 5 and only contains this store's
        # inventory logs.
        assert isinstance(body["recent_activity"], list)
        assert len(body["recent_activity"]) <= 5
        for evt in body["recent_activity"]:
            assert evt["store_id"] == str(store.id)


# --------------------------------------------------------------------- #
# /stores/{store_id}/dashboard/kpis
# --------------------------------------------------------------------- #


class TestKpis:
    def test_kpis_match_dashboard(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        make_order,
    ) -> None:
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)
        make_item(
            store=store, quantity_on_hand=0, reorder_threshold=5
        )
        make_order(store=store, order_status=OrderStatus.pending)

        full = client.get(
            f"/stores/{store.id}/dashboard", headers=_auth(owner)
        ).json()
        kpis = client.get(
            f"/stores/{store.id}/dashboard/kpis", headers=_auth(owner)
        ).json()

        # The dashboard derives KPIs from the same section
        # computations, so the two surfaces are guaranteed to agree.
        assert kpis == full["kpis"]


# --------------------------------------------------------------------- #
# /stores/{store_id}/orders/summary
# --------------------------------------------------------------------- #


class TestOrdersSummary:
    def test_histogram_is_dense_and_open_count_matches(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_order,
    ) -> None:
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)
        make_order(store=store, order_status=OrderStatus.pending)
        make_order(store=store, order_status=OrderStatus.accepted)
        make_order(store=store, order_status=OrderStatus.delivered)

        resp = client.get(
            f"/stores/{store.id}/orders/summary",
            headers=_auth(owner),
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == {"open_count", "by_status", "recent"}
        # Dense histogram.
        assert set(body["by_status"].keys()) == {
            s.value for s in OrderStatus
        }
        assert body["by_status"][OrderStatus.pending.value] == 1
        assert body["by_status"][OrderStatus.accepted.value] == 1
        assert body["by_status"][OrderStatus.delivered.value] == 1
        # open_count covers pending + accepted, not delivered.
        assert body["open_count"] == 2
        assert len(body["recent"]) == 3

    def test_recent_bounded_to_five(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_order,
    ) -> None:
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)
        for _ in range(7):
            make_order(store=store)
        body = client.get(
            f"/stores/{store.id}/orders/summary",
            headers=_auth(owner),
        ).json()
        assert len(body["recent"]) == 5


# --------------------------------------------------------------------- #
# /stores/{store_id}/inventory/summary
# --------------------------------------------------------------------- #


class TestInventorySummary:
    def test_low_stock_predicate(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ) -> None:
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)
        # Low-stock: effective (on_hand - reserved) <= threshold.
        make_item(
            store=store,
            quantity_on_hand=2,
            quantity_reserved=0,
            reorder_threshold=5,
        )
        make_item(
            store=store,
            quantity_on_hand=20,
            quantity_reserved=0,
            reorder_threshold=5,
        )

        body = client.get(
            f"/stores/{store.id}/inventory/summary",
            headers=_auth(owner),
        ).json()
        assert body["total_items"] == 2
        assert body["low_stock_count"] == 1
        assert body["total_on_hand"] == 22
        assert body["total_reserved"] == 0

    def test_cross_store_isolation(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ) -> None:
        store_a = make_store()
        store_b = make_store()
        owner = make_user(UserRole.owner, store_id=store_a.id)

        make_item(store=store_a, quantity_on_hand=10)
        make_item(store=store_b, quantity_on_hand=100)

        body = client.get(
            f"/stores/{store_a.id}/inventory/summary",
            headers=_auth(owner),
        ).json()
        assert body["total_items"] == 1
        assert body["total_on_hand"] == 10


# --------------------------------------------------------------------- #
# /stores/{store_id}/products/summary
# --------------------------------------------------------------------- #


class TestProductsSummary:
    def test_counts_products_via_inventory_join(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
    ) -> None:
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)

        # Product allowed and stocked in this store.
        allowed_product = make_product(
            compliance_status=ComplianceStatus.allowed
        )
        allowed_variant = make_variant(product=allowed_product)
        make_item(store=store, variant=allowed_variant)

        # Restricted product stocked in this store.
        restricted_product = make_product(
            compliance_status=ComplianceStatus.restricted
        )
        restricted_variant = make_variant(product=restricted_product)
        make_item(store=store, variant=restricted_variant)

        # Banned product NOT stocked in this store -> must not count.
        banned_product = make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        make_variant(product=banned_product)

        body = client.get(
            f"/stores/{store.id}/products/summary",
            headers=_auth(owner),
        ).json()
        assert body["in_store_count"] == 2
        assert body["blocked_count"] == 1


# --------------------------------------------------------------------- #
# /stores/{store_id}/activity
# --------------------------------------------------------------------- #


class TestActivity:
    def test_paginates_and_orders_desc(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        make_log,
    ) -> None:
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)
        item = make_item(store=store)

        base = datetime(2025, 1, 1, tzinfo=UTC)
        for i in range(7):
            make_log(item=item, created_at=base + timedelta(minutes=i))

        body = client.get(
            f"/stores/{store.id}/activity?limit=3&offset=0",
            headers=_auth(owner),
        ).json()
        assert body["total"] == 7
        assert body["limit"] == 3
        assert body["offset"] == 0
        assert len(body["items"]) == 3
        # Descending by created_at.
        timestamps = [evt["created_at"] for evt in body["items"]]
        assert timestamps == sorted(timestamps, reverse=True)

    def test_filters_to_this_store_only(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        make_log,
    ) -> None:
        store_a = make_store()
        store_b = make_store()
        owner = make_user(UserRole.owner, store_id=store_a.id)
        item_a = make_item(store=store_a)
        item_b = make_item(store=store_b)
        make_log(item=item_a)
        make_log(item=item_b)

        body = client.get(
            f"/stores/{store_a.id}/activity",
            headers=_auth(owner),
        ).json()
        assert body["total"] == 1
        assert body["items"][0]["store_id"] == str(store_a.id)


# --------------------------------------------------------------------- #
# /stores/{store_id}/alerts
# --------------------------------------------------------------------- #


class TestAlerts:
    def test_no_inventory_alert_when_store_empty(
        self, client: TestClient, make_store, make_user
    ) -> None:
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)
        body = client.get(
            f"/stores/{store.id}/alerts", headers=_auth(owner)
        ).json()
        cats = [a["category"] for a in body["items"]]
        assert "no_inventory" in cats

    def test_low_stock_alert(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ) -> None:
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)
        item = make_item(
            store=store,
            quantity_on_hand=0,
            reorder_threshold=5,
        )
        body = client.get(
            f"/stores/{store.id}/alerts?category=low_stock",
            headers=_auth(owner),
        ).json()
        assert body["total"] >= 1
        ids = {a["id"] for a in body["items"]}
        assert f"low_stock:{item.id}" in ids
        # Fully depleted -> severity high.
        depleted = next(
            a for a in body["items"] if a["entity_id"] == str(item.id)
        )
        assert depleted["severity"] == "high"

    def test_aging_order_alert_with_threshold(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_order,
    ) -> None:
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)

        old = datetime.now(UTC) - timedelta(minutes=120)
        make_order(
            store=store,
            order_status=OrderStatus.pending,
            created_at=old,
        )
        # Recent order should NOT count.
        make_order(store=store, order_status=OrderStatus.pending)

        body = client.get(
            f"/stores/{store.id}/alerts?"
            f"category=aging_order&aging_minutes=60",
            headers=_auth(owner),
        ).json()
        assert body["total"] == 1
        alert = body["items"][0]
        assert alert["category"] == "aging_order"
        assert alert["id"].endswith(":60")

    def test_severity_filter(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ) -> None:
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)
        # Healthy stock -> no low-stock alert. Only the no_inventory
        # alert is suppressed because we have one item.
        make_item(
            store=store,
            quantity_on_hand=0,
            reorder_threshold=5,
        )

        body = client.get(
            f"/stores/{store.id}/alerts?severity=high",
            headers=_auth(owner),
        ).json()
        for alert in body["items"]:
            assert alert["severity"] == "high"

    def test_pagination_bounds_enforced(
        self, client: TestClient, make_store, make_user
    ) -> None:
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)
        resp = client.get(
            f"/stores/{store.id}/alerts?limit=0",
            headers=_auth(owner),
        )
        assert resp.status_code == 422
