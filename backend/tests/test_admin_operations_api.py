"""API-level tests for the admin operations alerts endpoint (F2.19.2).

Exercises `GET /admin/operations/alerts` via the FastAPI TestClient.
Service-level alert generation, severity rules, and ordering are
exhaustively tested in test_admin_operations_service.py — this suite
focuses on:

  - auth gate (anon / invalid token → 401).
  - RBAC matrix (admin → 200, every non-admin role → 403).
  - Response envelope + item shape.
  - Query-param validation (FastAPI Query bounds + enum coercion).
  - Filter wiring through the API surface.
  - Total before pagination.
  - Backend-computed values driven by seeded DB state.
  - No alert-mutation actions are exposed.

Style mirrors test_admin_dashboard_api.py + test_audit_api.py.
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
from app.db.models import InventoryStatus
from app.db.models import Order
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole


ADMIN_OPERATIONS_URL = "/admin/operations/alerts"

_TOP_LEVEL_KEYS = {"items", "total", "limit", "offset"}
_ALERT_ITEM_KEYS = {
    "id",
    "category",
    "severity",
    "store_id",
    "entity_type",
    "entity_id",
    "summary",
    "created_at",
}

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
        *, name: str | None = None, is_active: bool = True
    ) -> Store:
        store = Store(
            name=name or f"OpsAPI-{uuid.uuid4().hex[:6]}",
            code=f"oa-{uuid.uuid4().hex[:8]}",
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
            full_name=f"OpsAPI {role.value}",
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


# --------------------------------------------------------------------- #
# A. Auth gate / RBAC
# --------------------------------------------------------------------- #


class TestAuthRBAC:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.get(ADMIN_OPERATIONS_URL)
        assert resp.status_code == 401, resp.text

    def test_invalid_token_returns_401(self, client: TestClient):
        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401, resp.text

    def test_admin_returns_200(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_OPERATIONS_URL, headers=_auth(admin)
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
            ADMIN_OPERATIONS_URL, headers=_auth(actor)
        )
        assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------- #
# B. Response envelope + item shape
# --------------------------------------------------------------------- #


class TestEnvelope:
    def test_top_level_keys_and_defaults(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_OPERATIONS_URL, headers=_auth(admin)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == _TOP_LEVEL_KEYS
        assert body["limit"] == 50
        assert body["offset"] == 0
        assert body["total"] == 0
        assert body["items"] == []

    def test_alert_item_shape(
        self,
        client: TestClient,
        make_user,
        make_store,
    ):
        admin = make_user(role=UserRole.admin)
        make_store(is_active=False)  # generates 2 alerts.

        resp = client.get(
            ADMIN_OPERATIONS_URL, headers=_auth(admin)
        )
        body = resp.json()
        assert body["total"] >= 1
        alert = body["items"][0]
        assert set(alert.keys()) == _ALERT_ITEM_KEYS
        # Enum values serialize as bare strings.
        assert alert["category"] in {
            "low_stock",
            "aging_order",
            "compliance_blocker",
            "inactive_store",
            "store_no_inventory",
        }
        assert alert["severity"] in {"low", "medium", "high"}
        assert alert["entity_type"] in {
            "store",
            "inventory_item",
            "order",
            "product",
        }
        # id is a non-empty string with category prefix.
        assert isinstance(alert["id"], str)
        assert alert["id"].split(":", 1)[0] == alert["category"]


# --------------------------------------------------------------------- #
# C. Query-param validation
# --------------------------------------------------------------------- #


class TestQueryValidation:
    def test_limit_zero_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"limit": 0},
        )
        assert resp.status_code == 422, resp.text

    def test_limit_above_max_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"limit": 201},
        )
        assert resp.status_code == 422, resp.text

    def test_limit_max_200_accepted(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"limit": 200},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["limit"] == 200

    def test_negative_offset_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"offset": -1},
        )
        assert resp.status_code == 422, resp.text

    def test_aging_minutes_zero_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"aging_minutes": 0},
        )
        assert resp.status_code == 422, resp.text

    def test_invalid_category_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"category": "not_a_category"},
        )
        assert resp.status_code == 422, resp.text

    def test_invalid_severity_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"severity": "critical"},
        )
        assert resp.status_code == 422, resp.text

    def test_invalid_store_id_uuid_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"store_id": "not-a-uuid"},
        )
        assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------- #
# D. Defaults
# --------------------------------------------------------------------- #


class TestDefaults:
    def test_limit_default_50(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_OPERATIONS_URL, headers=_auth(admin)
        )
        assert resp.json()["limit"] == 50

    def test_offset_default_0(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_OPERATIONS_URL, headers=_auth(admin)
        )
        assert resp.json()["offset"] == 0

    def test_aging_minutes_default_1440(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_order,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        # 25 hours = 1500 minutes — crosses the 1440 default.
        make_order(
            store=store,
            order_status=OrderStatus.pending,
            created_at=datetime.now(UTC) - timedelta(minutes=1500),
        )

        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"category": "aging_order"},
        )
        body = resp.json()
        assert body["total"] == 1
        # id suffix proves the default 1440 was applied.
        assert body["items"][0]["id"].endswith(":1440")


# --------------------------------------------------------------------- #
# E. Filters
# --------------------------------------------------------------------- #


class TestFilters:
    def test_category_filter(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_product,
    ):
        admin = make_user(role=UserRole.admin)
        make_store(is_active=False)  # inactive_store + store_no_inventory
        make_product(allowed_for_sale=False)  # compliance_blocker

        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"category": "compliance_blocker"},
        )
        body = resp.json()
        assert body["total"] == 1
        for alert in body["items"]:
            assert alert["category"] == "compliance_blocker"

    def test_severity_filter(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_item,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        make_item(
            store=store,
            quantity_on_hand=0,
            reorder_threshold=0,
        )
        make_store(is_active=False)  # medium alerts

        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"severity": "high"},
        )
        body = resp.json()
        assert body["total"] >= 1
        for alert in body["items"]:
            assert alert["severity"] == "high"

    def test_store_id_filter_scopes_alerts(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_product,
    ):
        admin = make_user(role=UserRole.admin)
        store_a = make_store(is_active=False)
        make_store(is_active=False)
        # compliance_blocker → store_id None, must be excluded.
        make_product(allowed_for_sale=False)

        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"store_id": str(store_a.id)},
        )
        body = resp.json()
        assert body["total"] >= 1
        for alert in body["items"]:
            assert alert["store_id"] == str(store_a.id)


# --------------------------------------------------------------------- #
# F. Pagination
# --------------------------------------------------------------------- #


class TestPagination:
    def test_total_before_pagination(
        self,
        client: TestClient,
        make_user,
        make_store,
    ):
        admin = make_user(role=UserRole.admin)
        for _ in range(4):
            make_store(is_active=False)  # 8 alerts total

        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"limit": 2, "offset": 0},
        )
        body = resp.json()
        assert body["total"] == 8
        assert len(body["items"]) == 2

    def test_offset_advances(
        self,
        client: TestClient,
        make_user,
        make_store,
    ):
        admin = make_user(role=UserRole.admin)
        for _ in range(4):
            make_store(is_active=False)

        first = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"limit": 4, "offset": 0},
        ).json()
        second = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"limit": 4, "offset": 4},
        ).json()
        first_ids = {a["id"] for a in first["items"]}
        second_ids = {a["id"] for a in second["items"]}
        assert first_ids.isdisjoint(second_ids)
        assert len(first_ids) == 4
        assert len(second_ids) == 4


# --------------------------------------------------------------------- #
# G. Backend-computed values from seeded DB state
# --------------------------------------------------------------------- #


class TestBackendComputed:
    def test_seeded_low_stock_surfaces_as_high(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_item,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        item = make_item(
            store=store,
            quantity_on_hand=0,
            quantity_reserved=0,
            reorder_threshold=0,
        )

        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={"category": "low_stock"},
        )
        body = resp.json()
        assert body["total"] == 1
        alert = body["items"][0]
        assert alert["id"] == f"low_stock:{item.id}"
        assert alert["severity"] == "high"
        assert alert["entity_type"] == "inventory_item"
        assert alert["entity_id"] == str(item.id)
        assert alert["store_id"] == str(store.id)

    def test_seeded_aging_order_id_includes_aging_minutes(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_order,
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store()
        order = make_order(
            store=store,
            order_status=OrderStatus.pending,
            created_at=datetime.now(UTC) - timedelta(hours=5),
        )

        resp = client.get(
            ADMIN_OPERATIONS_URL,
            headers=_auth(admin),
            params={
                "category": "aging_order",
                "aging_minutes": 60,
            },
        )
        body = resp.json()
        assert body["total"] == 1
        alert = body["items"][0]
        assert alert["id"] == f"aging_order:{order.id}:60"
        assert alert["entity_id"] == str(order.id)


# --------------------------------------------------------------------- #
# H. No mutation actions
# --------------------------------------------------------------------- #


class TestNoMutationActions:
    """The contract forbids acknowledge / dismiss / resolve / snooze
    actions on alerts. None of those paths should be wired up.
    Method-not-allowed (405) or not-found (404) responses confirm
    no handler exists; a 401/403 would indicate a wired-up but
    auth-gated route which is also a contract violation, so we
    explicitly reject those status codes for action-style paths.
    """

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/admin/operations/alerts/x/acknowledge"),
            ("POST", "/admin/operations/alerts/x/dismiss"),
            ("POST", "/admin/operations/alerts/x/resolve"),
            ("PATCH", "/admin/operations/alerts/x"),
            ("DELETE", "/admin/operations/alerts/x"),
        ],
    )
    def test_no_mutation_endpoints(
        self,
        client: TestClient,
        make_user,
        method: str,
        path: str,
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.request(method, path, headers=_auth(admin))
        # 404 (no route) or 405 (method not allowed) are both
        # acceptable; 200/201/202/204 would mean we wired a mutation.
        assert resp.status_code in (404, 405), (
            f"{method} {path} responded with "
            f"{resp.status_code} — alert mutations are forbidden."
        )

    def test_post_to_list_endpoint_not_allowed(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.post(
            ADMIN_OPERATIONS_URL, headers=_auth(admin), json={}
        )
        assert resp.status_code == 405
