"""API-level tests for the admin dashboard endpoint (F2.19.1).

Exercises `GET /admin/dashboard` via the FastAPI TestClient. Service-
level behavior (counts, predicates, sort, bounds) lives in
test_admin_dashboard_service.py and is not duplicated here. This suite
focuses on:

  - auth gate: anonymous → 401.
  - RBAC matrix: admin → 200, every non-admin role → 403.
  - Response envelope: every top-level section present and typed.
  - Backend-computed values: counts move with seeded DB state.
  - Bounded tails: `orders.recent` and `recent_audit` capped at 5.
  - No pagination/query-param requirement on the endpoint itself.

Style mirrors test_audit_api.py and test_orders_api.py.
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

from app.core.security import create_access_token
from app.core.security import hash_password
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


ADMIN_DASHBOARD_URL = "/admin/dashboard"

_TOP_LEVEL_KEYS = {
    "stores",
    "users",
    "inventory",
    "orders",
    "compliance",
    "recent_audit",
}

_STORES_KEYS = {"total", "active", "inactive"}
_USERS_KEYS = {"total", "active"}
_INVENTORY_KEYS = {"low_stock_count"}
_ORDERS_KEYS = {"open_count", "by_status", "recent"}
_COMPLIANCE_KEYS = {"blocked_count"}

_NON_ADMIN_ROLES = (
    UserRole.owner,
    UserRole.manager,
    UserRole.staff,
    UserRole.driver,
)


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(
        *, name: str = "Dash-API", is_active: bool = True
    ) -> Store:
        store = Store(
            name=name,
            code=f"da-{uuid.uuid4().hex[:8]}",
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
            full_name=f"DashAPI {role.value}",
            email=f"{role.value}-{uuid.uuid4().hex[:10]}@example.com",
            password_hash=hash_password("supersecret123"),
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
def make_inventory_log(
    db_session: Session,
) -> Callable[..., InventoryLog]:
    def _create(
        *,
        item: InventoryItem,
        actor: User | None = None,
        created_at: datetime | None = None,
    ) -> InventoryLog:
        log = InventoryLog(
            inventory_item_id=item.id,
            store_id=item.store_id,
            variant_id=item.variant_id,
            performed_by_user_id=actor.id if actor is not None else None,
            movement_type=InventoryMovementType.receipt,
            quantity_delta=5,
            quantity_after=15,
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


# --------------------------------------------------------------------- #
# A. Auth gate / RBAC
# --------------------------------------------------------------------- #


class TestAuthRBAC:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.get(ADMIN_DASHBOARD_URL)
        assert resp.status_code == 401, resp.text

    def test_invalid_token_returns_401(self, client: TestClient):
        resp = client.get(
            ADMIN_DASHBOARD_URL,
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401, resp.text

    def test_admin_returns_200(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_DASHBOARD_URL, headers=_auth(admin)
        )
        assert resp.status_code == 200, resp.text

    @pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
    def test_non_admin_forbidden(
        self,
        client: TestClient,
        make_store,
        make_user,
        role: UserRole,
    ):
        store = make_store()
        actor = make_user(role=role, store_id=store.id)
        resp = client.get(
            ADMIN_DASHBOARD_URL, headers=_auth(actor)
        )
        assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------- #
# B. Response envelope
# --------------------------------------------------------------------- #


class TestResponseEnvelope:
    def test_envelope_top_level_keys(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_DASHBOARD_URL, headers=_auth(admin)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == _TOP_LEVEL_KEYS

    def test_section_keys(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_DASHBOARD_URL, headers=_auth(admin)
        )
        body = resp.json()
        assert set(body["stores"].keys()) == _STORES_KEYS
        assert set(body["users"].keys()) == _USERS_KEYS
        assert set(body["inventory"].keys()) == _INVENTORY_KEYS
        assert set(body["orders"].keys()) == _ORDERS_KEYS
        assert set(body["compliance"].keys()) == _COMPLIANCE_KEYS

    def test_orders_by_status_includes_every_enum_member(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_DASHBOARD_URL, headers=_auth(admin)
        )
        body = resp.json()
        by_status = body["orders"]["by_status"]
        expected = {s.value for s in OrderStatus}
        assert set(by_status.keys()) == expected
        # All zero on an empty DB.
        assert all(v == 0 for v in by_status.values())

    def test_recent_lists_are_arrays(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_DASHBOARD_URL, headers=_auth(admin)
        )
        body = resp.json()
        assert isinstance(body["orders"]["recent"], list)
        assert isinstance(body["recent_audit"], list)


# --------------------------------------------------------------------- #
# C. No query params required
# --------------------------------------------------------------------- #


class TestNoQueryParams:
    def test_endpoint_works_with_no_query_params(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_DASHBOARD_URL, headers=_auth(admin)
        )
        assert resp.status_code == 200, resp.text

    def test_endpoint_ignores_unknown_query_params(
        self, client: TestClient, make_user
    ):
        """The endpoint declares no query params; FastAPI silently
        ignores unknown ones (the OpenAPI surface stays clean and
        existing client tooling can't break the call by appending
        cache-busting params)."""
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_DASHBOARD_URL,
            headers=_auth(admin),
            params={"limit": 999, "store_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 200, resp.text


# --------------------------------------------------------------------- #
# D. Values are backend-computed from DB state
# --------------------------------------------------------------------- #


class TestBackendComputed:
    def test_store_counts_reflect_seeded_state(
        self, client: TestClient, make_user, make_store
    ):
        admin = make_user(role=UserRole.admin)
        make_store(is_active=True)
        make_store(is_active=True)
        make_store(is_active=False)

        resp = client.get(
            ADMIN_DASHBOARD_URL, headers=_auth(admin)
        )
        body = resp.json()
        assert body["stores"]["total"] == 3
        assert body["stores"]["active"] == 2
        assert body["stores"]["inactive"] == 1

    def test_user_counts_reflect_seeded_state(
        self,
        client: TestClient,
        make_user,
        make_store,
    ):
        admin = make_user(role=UserRole.admin)  # 1 active
        store = make_store()
        make_user(role=UserRole.owner, store_id=store.id, is_active=True)
        make_user(
            role=UserRole.staff, store_id=store.id, is_active=False
        )

        resp = client.get(
            ADMIN_DASHBOARD_URL, headers=_auth(admin)
        )
        body = resp.json()
        assert body["users"]["total"] == 3
        assert body["users"]["active"] == 2

    def test_inventory_low_stock_reflects_predicate(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_item,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        # 2 low-stock items.
        make_item(
            store=store,
            quantity_on_hand=2,
            quantity_reserved=0,
            reorder_threshold=5,
        )
        make_item(
            store=store,
            quantity_on_hand=0,
            quantity_reserved=0,
            reorder_threshold=0,
        )
        # 1 healthy item.
        make_item(
            store=store,
            quantity_on_hand=20,
            quantity_reserved=0,
            reorder_threshold=3,
        )

        resp = client.get(
            ADMIN_DASHBOARD_URL, headers=_auth(admin)
        )
        body = resp.json()
        assert body["inventory"]["low_stock_count"] == 2

    def test_orders_open_count_and_by_status(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_order,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        # 3 pending + 1 accepted = 4 open. 1 delivered = closed.
        make_order(store=store, order_status=OrderStatus.pending)
        make_order(store=store, order_status=OrderStatus.pending)
        make_order(store=store, order_status=OrderStatus.pending)
        make_order(store=store, order_status=OrderStatus.accepted)
        make_order(store=store, order_status=OrderStatus.delivered)

        resp = client.get(
            ADMIN_DASHBOARD_URL, headers=_auth(admin)
        )
        body = resp.json()
        assert body["orders"]["open_count"] == 4
        by_status = body["orders"]["by_status"]
        assert by_status["pending"] == 3
        assert by_status["accepted"] == 1
        assert by_status["delivered"] == 1
        assert by_status["canceled"] == 0

    def test_compliance_blocked_count_reflects_predicate(
        self,
        client: TestClient,
        make_user,
        make_product,
    ):
        admin = make_user(role=UserRole.admin)
        # blocked via allowed_for_sale=False
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=False,
        )
        # blocked via banned (implies allowed=False by CHECK constraint)
        make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        # blocked via restricted (allowed=True is permitted by model)
        make_product(
            compliance_status=ComplianceStatus.restricted,
            allowed_for_sale=True,
        )
        # not blocked
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )

        resp = client.get(
            ADMIN_DASHBOARD_URL, headers=_auth(admin)
        )
        body = resp.json()
        assert body["compliance"]["blocked_count"] == 3


# --------------------------------------------------------------------- #
# E. Bounded recent tails
# --------------------------------------------------------------------- #


class TestBoundedTails:
    def test_orders_recent_bounded_to_5(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_order,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        for index in range(7):
            make_order(
                store=store,
                order_status=OrderStatus.pending,
                created_at=base + timedelta(minutes=index),
            )

        resp = client.get(
            ADMIN_DASHBOARD_URL, headers=_auth(admin)
        )
        body = resp.json()
        assert len(body["orders"]["recent"]) == 5
        # by_status confirms total order count is still 7 — recent is
        # only a tail, not the full list.
        assert body["orders"]["by_status"]["pending"] == 7

    def test_orders_recent_sorted_desc(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_order,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        created = [
            make_order(
                store=store,
                order_status=OrderStatus.pending,
                created_at=base + timedelta(minutes=index),
            )
            for index in range(3)
        ]

        resp = client.get(
            ADMIN_DASHBOARD_URL, headers=_auth(admin)
        )
        body = resp.json()
        returned_ids = [row["id"] for row in body["orders"]["recent"]]
        expected_ids = [str(o.id) for o in reversed(created)]
        assert returned_ids == expected_ids

    def test_recent_audit_bounded_to_5(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_product,
        make_variant,
        make_item,
        make_inventory_log,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant)
        base = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
        for index in range(7):
            make_inventory_log(
                item=item,
                actor=admin,
                created_at=base + timedelta(minutes=index),
            )

        resp = client.get(
            ADMIN_DASHBOARD_URL, headers=_auth(admin)
        )
        body = resp.json()
        assert len(body["recent_audit"]) == 5
