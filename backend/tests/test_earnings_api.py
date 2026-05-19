"""Tests for the earnings surfaces.

Covers both the HTTP routes and the underlying service math:

  GET /admin/earnings              (admin-only)
  GET /stores/{store_id}/earnings  (store member, staff or above)

The commission rule (encoded in app.services.earnings):

    gross_base  = subtotal + (delivery × N) + (tip × N) + taxes
    commission  = 0.20 × gross_base
    customer    = gross_base + commission

with `DELIVERY_FEE = $10.00`, `TIP = $0.00`, and `N` = number of
*delivered* orders. Tests pin both the formula (so a future change is
visible) and the locked filter (only `status = delivered` counts).

Style mirrors test_admin_dashboard_api.py and test_products.py.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Order
from app.db.models import OrderItem
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.services.earnings import COMMISSION_RATE
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user
from app.services.earnings import DELIVERY_FEE_USD
from app.services.earnings import TIP_AMOUNT_USD


ADMIN_EARNINGS_URL = "/admin/earnings"

_NON_ADMIN_ROLES = (
    UserRole.owner,
    UserRole.manager,
    UserRole.staff,
    UserRole.driver,
)


def _store_url(store_id: uuid.UUID) -> str:
    return f"/stores/{store_id}/earnings"


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(*, name: str = "Earn-QA", is_active: bool = True) -> Store:
        store = Store(
            name=name,
            code=f"earn-{uuid.uuid4().hex[:8]}",
            is_active=is_active,
        )
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


# Thin adapter over tests.helpers.auth.make_user (F2.22.2.C2).
@pytest.fixture
def make_user(db_session: Session, make_store) -> Callable[..., User]:
    def _create(
        *,
        role: UserRole,
        store: Store | None = None,
    ) -> User:
        if role == UserRole.admin:
            sid: uuid.UUID | None = None
        else:
            sid = (store if store is not None else make_store()).id
        return central_make_user(
            db_session,
            role=role,
            store_id=sid,
            full_name=f"Earn {role.value}",
            is_active=True,
        )

    return _create


@pytest.fixture
def make_variant(db_session: Session) -> Callable[..., ProductVariant]:
    def _create(
        *,
        product_name: str | None = None,
        price: Decimal = Decimal("10.00"),
        flavor: str | None = None,
        size_label: str | None = None,
    ) -> ProductVariant:
        product = Product(
            name=product_name or f"P-{uuid.uuid4().hex[:6]}",
            category="vape",
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        variant = ProductVariant(
            product_id=product.id,
            sku=f"SKU-{uuid.uuid4().hex[:8]}",
            price=price,
            flavor=flavor,
            size_label=size_label,
            is_active=True,
        )
        db_session.add(variant)
        db_session.commit()
        db_session.refresh(variant)
        return variant

    return _create


@pytest.fixture
def make_order(
    db_session: Session,
) -> Callable[..., Order]:
    """Insert an Order plus its OrderItems (one per provided variant).

    `subtotal_amount` and `tax_amount` are taken literally from the
    arguments — the earnings service sums those columns as-is, so the
    fixture intentionally does NOT recompute them from the items.
    """

    def _create(
        *,
        store: Store,
        order_status: OrderStatus = OrderStatus.delivered,
        subtotal: Decimal = Decimal("0.00"),
        tax: Decimal = Decimal("0.00"),
        items: list[tuple[ProductVariant, int, Decimal]] | None = None,
    ) -> Order:
        from app.db.models import InventoryItem
        from app.db.models import InventoryStatus

        order = Order(
            store_id=store.id,
            idempotency_key=f"idem-{uuid.uuid4().hex[:8]}",
            status=order_status,
            subtotal_amount=subtotal,
            tax_amount=tax,
            total_amount=subtotal + tax,
        )
        db_session.add(order)
        db_session.commit()
        db_session.refresh(order)

        from sqlalchemy import select

        for variant, qty, unit_price in items or []:
            # OrderItem requires an InventoryItem FK. The schema enforces
            # one InventoryItem per (store, variant), so reuse the
            # existing row when the fixture sees the same pair twice in
            # a single test (e.g. one pending order + one delivered
            # order for the same SKU).
            inv = db_session.scalar(
                select(InventoryItem).where(
                    InventoryItem.store_id == store.id,
                    InventoryItem.variant_id == variant.id,
                )
            )
            if inv is None:
                inv = InventoryItem(
                    store_id=store.id,
                    variant_id=variant.id,
                    quantity_on_hand=qty,
                    quantity_reserved=0,
                    reorder_threshold=0,
                    status=InventoryStatus.available,
                )
                db_session.add(inv)
                db_session.commit()
                db_session.refresh(inv)

            item = OrderItem(
                order_id=order.id,
                variant_id=variant.id,
                inventory_item_id=inv.id,
                quantity=qty,
                unit_price=unit_price,
                line_total=unit_price * qty,
            )
            db_session.add(item)
        db_session.commit()
        db_session.refresh(order)
        return order

    return _create


# --------------------------------------------------------------------- #
# GET /admin/earnings — RBAC
# --------------------------------------------------------------------- #


class TestAdminEarningsRBAC:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.get(ADMIN_EARNINGS_URL)
        assert resp.status_code == 401

    @pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
    def test_non_admin_returns_403(
        self, client: TestClient, make_user, role: UserRole
    ):
        user = make_user(role=role)
        resp = client.get(ADMIN_EARNINGS_URL, headers=_auth(user))
        assert resp.status_code == 403

    def test_admin_returns_200(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        resp = client.get(ADMIN_EARNINGS_URL, headers=_auth(admin))
        assert resp.status_code == 200


# --------------------------------------------------------------------- #
# GET /admin/earnings — response shape and constants
# --------------------------------------------------------------------- #


class TestAdminEarningsShape:
    def test_envelope_keys_present(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        resp = client.get(ADMIN_EARNINGS_URL, headers=_auth(admin))
        body = resp.json()
        assert set(body.keys()) == {
            "delivered_orders",
            "subtotal_total",
            "delivery_total",
            "tip_total",
            "tax_total",
            "gross_base_total",
            "commission_total",
            "customer_paid_total",
            "commission_rate",
            "delivery_fee",
            "by_store",
        }

    def test_constants_are_echoed(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        body = client.get(ADMIN_EARNINGS_URL, headers=_auth(admin)).json()
        # The endpoint echoes the pricing constants so the UI can label
        # them without hard-coding.
        assert Decimal(body["commission_rate"]) == COMMISSION_RATE
        assert Decimal(body["delivery_fee"]) == DELIVERY_FEE_USD

    def test_empty_state_is_all_zeros(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        body = client.get(ADMIN_EARNINGS_URL, headers=_auth(admin)).json()
        assert body["delivered_orders"] == 0
        assert Decimal(body["subtotal_total"]) == Decimal("0.00")
        assert Decimal(body["commission_total"]) == Decimal("0.00")
        assert Decimal(body["customer_paid_total"]) == Decimal("0.00")
        assert body["by_store"] == []


# --------------------------------------------------------------------- #
# GET /admin/earnings — commission math
# --------------------------------------------------------------------- #


class TestAdminEarningsMath:
    def test_only_delivered_orders_count(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_order,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        make_order(
            store=store,
            order_status=OrderStatus.pending,
            subtotal=Decimal("100.00"),
        )
        make_order(
            store=store,
            order_status=OrderStatus.delivered,
            subtotal=Decimal("50.00"),
            tax=Decimal("5.00"),
        )
        body = client.get(ADMIN_EARNINGS_URL, headers=_auth(admin)).json()
        # Only the delivered order is included.
        assert body["delivered_orders"] == 1
        assert Decimal(body["subtotal_total"]) == Decimal("50.00")
        assert Decimal(body["tax_total"]) == Decimal("5.00")

    def test_commission_formula(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_order,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        # One delivered order: subtotal=100, tax=8.
        # gross_base = 100 + 10 (delivery) + 0 (tip) + 8 = 118.00
        # commission = 0.20 * 118 = 23.60
        # customer_paid = 118 + 23.60 = 141.60
        make_order(
            store=store,
            order_status=OrderStatus.delivered,
            subtotal=Decimal("100.00"),
            tax=Decimal("8.00"),
        )
        body = client.get(ADMIN_EARNINGS_URL, headers=_auth(admin)).json()
        assert body["delivered_orders"] == 1
        assert Decimal(body["delivery_total"]) == DELIVERY_FEE_USD
        assert Decimal(body["tip_total"]) == TIP_AMOUNT_USD
        assert Decimal(body["gross_base_total"]) == Decimal("118.00")
        assert Decimal(body["commission_total"]) == Decimal("23.60")
        assert Decimal(body["customer_paid_total"]) == Decimal("141.60")

    def test_by_store_breakdown_sorted_by_commission_desc(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_order,
    ):
        admin = make_user(role=UserRole.admin)
        small = make_store(name="Small")
        big = make_store(name="Big")
        # Small store: subtotal=10, tax=0 → gross=20 → commission=4.00
        make_order(
            store=small,
            order_status=OrderStatus.delivered,
            subtotal=Decimal("10.00"),
        )
        # Big store: subtotal=200, tax=0 → gross=210 → commission=42.00
        make_order(
            store=big,
            order_status=OrderStatus.delivered,
            subtotal=Decimal("200.00"),
        )
        body = client.get(ADMIN_EARNINGS_URL, headers=_auth(admin)).json()
        rows = body["by_store"]
        names = [r["store_name"] for r in rows]
        # Big store first because commission desc.
        assert names == ["Big", "Small"]
        big_row = rows[0]
        small_row = rows[1]
        assert Decimal(big_row["commission"]) == Decimal("42.00")
        assert Decimal(small_row["commission"]) == Decimal("4.00")
        assert big_row["delivered_orders"] == 1
        assert small_row["delivered_orders"] == 1


# --------------------------------------------------------------------- #
# GET /stores/{store_id}/earnings — RBAC + membership
# --------------------------------------------------------------------- #


class TestStoreEarningsRBAC:
    def test_anonymous_returns_401(
        self, client: TestClient, make_store
    ):
        store = make_store()
        resp = client.get(_store_url(store.id))
        assert resp.status_code == 401

    @pytest.mark.parametrize(
        "role", [UserRole.owner, UserRole.manager, UserRole.staff]
    )
    def test_store_member_allowed(
        self,
        client: TestClient,
        make_store,
        make_user,
        role: UserRole,
    ):
        store = make_store()
        user = make_user(role=role, store=store)
        resp = client.get(_store_url(store.id), headers=_auth(user))
        assert resp.status_code == 200

    def test_driver_blocked_by_role_gate(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        driver = make_user(role=UserRole.driver, store=store)
        resp = client.get(_store_url(store.id), headers=_auth(driver))
        assert resp.status_code == 403

    def test_other_store_member_returns_403(
        self,
        client: TestClient,
        make_store,
        make_user,
    ):
        store_a = make_store(name="A")
        store_b = make_store(name="B")
        owner_b = make_user(role=UserRole.owner, store=store_b)
        resp = client.get(_store_url(store_a.id), headers=_auth(owner_b))
        assert resp.status_code == 403

    def test_admin_can_read_any_store(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        admin = make_user(role=UserRole.admin)
        resp = client.get(_store_url(store.id), headers=_auth(admin))
        assert resp.status_code == 200

    def test_admin_unknown_store_returns_404(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            _store_url(uuid.uuid4()), headers=_auth(admin)
        )
        assert resp.status_code == 404


# --------------------------------------------------------------------- #
# GET /stores/{store_id}/earnings — shape and math
# --------------------------------------------------------------------- #


class TestStoreEarningsShape:
    def test_envelope_keys_present(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        owner = make_user(role=UserRole.owner, store=store)
        body = client.get(
            _store_url(store.id), headers=_auth(owner)
        ).json()
        assert set(body.keys()) == {
            "delivered_orders",
            "total_items_sold",
            "product_revenue",
            "top_products",
        }
        # Store surface intentionally omits commission/delivery/tip/tax
        # — those belong to the admin earnings view.
        assert "commission" not in body
        assert "delivery" not in body

    def test_empty_state_is_zero(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        owner = make_user(role=UserRole.owner, store=store)
        body = client.get(
            _store_url(store.id), headers=_auth(owner)
        ).json()
        assert body["delivered_orders"] == 0
        assert body["total_items_sold"] == 0
        assert Decimal(body["product_revenue"]) == Decimal("0.00")
        assert body["top_products"] == []


class TestStoreEarningsMath:
    def test_only_delivered_orders_contribute_to_revenue(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_variant,
        make_order,
    ):
        store = make_store()
        owner = make_user(role=UserRole.owner, store=store)
        v = make_variant(product_name="Watermelon", price=Decimal("9.99"))

        # Pending: should be ignored entirely.
        make_order(
            store=store,
            order_status=OrderStatus.pending,
            items=[(v, 3, Decimal("9.99"))],
        )
        # Delivered: should count.
        make_order(
            store=store,
            order_status=OrderStatus.delivered,
            items=[(v, 2, Decimal("9.99"))],
        )

        body = client.get(
            _store_url(store.id), headers=_auth(owner)
        ).json()
        assert body["delivered_orders"] == 1
        assert body["total_items_sold"] == 2
        # 2 * 9.99 = 19.98
        assert Decimal(body["product_revenue"]) == Decimal("19.98")

    def test_top_products_sorted_by_revenue_desc(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_variant,
        make_order,
    ):
        store = make_store()
        owner = make_user(role=UserRole.owner, store=store)
        cheap = make_variant(product_name="Cheap", price=Decimal("1.00"))
        pricey = make_variant(product_name="Pricey", price=Decimal("50.00"))

        make_order(
            store=store,
            order_status=OrderStatus.delivered,
            items=[(cheap, 5, Decimal("1.00"))],
        )
        make_order(
            store=store,
            order_status=OrderStatus.delivered,
            items=[(pricey, 2, Decimal("50.00"))],
        )

        body = client.get(
            _store_url(store.id), headers=_auth(owner)
        ).json()
        names = [p["product_name"] for p in body["top_products"]]
        assert names == ["Pricey", "Cheap"]
        assert Decimal(body["top_products"][0]["revenue"]) == Decimal(
            "100.00"
        )
        assert Decimal(body["top_products"][1]["revenue"]) == Decimal(
            "5.00"
        )
        # Aggregate matches the per-row sum.
        assert Decimal(body["product_revenue"]) == Decimal("105.00")
        assert body["total_items_sold"] == 7

    def test_variant_label_concatenates_flavor_and_size(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_variant,
        make_order,
    ):
        store = make_store()
        owner = make_user(role=UserRole.owner, store=store)
        v = make_variant(
            product_name="Disposables",
            flavor="Mango",
            size_label="5000 puffs",
            price=Decimal("12.00"),
        )
        make_order(
            store=store,
            order_status=OrderStatus.delivered,
            items=[(v, 1, Decimal("12.00"))],
        )
        body = client.get(
            _store_url(store.id), headers=_auth(owner)
        ).json()
        row = body["top_products"][0]
        assert row["variant_label"] == "Mango · 5000 puffs"

    def test_variant_label_is_null_when_no_modifiers(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_variant,
        make_order,
    ):
        store = make_store()
        owner = make_user(role=UserRole.owner, store=store)
        v = make_variant(product_name="Plain", price=Decimal("3.00"))
        make_order(
            store=store,
            order_status=OrderStatus.delivered,
            items=[(v, 1, Decimal("3.00"))],
        )
        body = client.get(
            _store_url(store.id), headers=_auth(owner)
        ).json()
        assert body["top_products"][0]["variant_label"] is None

    def test_isolation_across_stores(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_variant,
        make_order,
    ):
        store_a = make_store(name="A")
        store_b = make_store(name="B")
        owner_a = make_user(role=UserRole.owner, store=store_a)
        v = make_variant(product_name="Shared", price=Decimal("10.00"))
        # Only store B has a delivered order with this variant; A has none.
        make_order(
            store=store_b,
            order_status=OrderStatus.delivered,
            items=[(v, 4, Decimal("10.00"))],
        )
        body = client.get(
            _store_url(store_a.id), headers=_auth(owner_a)
        ).json()
        assert body["delivered_orders"] == 0
        assert body["top_products"] == []
        assert Decimal(body["product_revenue"]) == Decimal("0.00")
