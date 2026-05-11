"""API-level tests for the orders module (S5.6).

Exercises the FastAPI router via TestClient. Covers:
  - auth gate on every orders endpoint (anon → 401)
  - RBAC matrices per tier (staff-tier endpoints + manager-tier
    endpoints for cancel/return)
  - tenancy on store-scoped paths AND order-scoped paths
  - service-error propagation (404 / 422) without SQL leaks
  - trust boundary at the API surface (extra="forbid" on the schemas
    keeps the client out of monetary fields and the inventory binding)

Schema validation lives in test_order_schemas.py and service-level
behaviour in test_orders_service.py — those concerns are not
duplicated here.
"""

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
from app.db.models import InventoryItem
from app.db.models import InventoryStatus
from app.db.models import Order
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(code: str | None = None) -> Store:
        store = Store(name="Ord-API", code=code or f"oa-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_user(db_session: Session, make_store) -> Callable[..., User]:
    def _create(role: UserRole, store_id: uuid.UUID | None = None) -> User:
        if role == UserRole.admin:
            sid = None
        else:
            sid = store_id if store_id is not None else make_store().id
        user = User(
            full_name=f"Ord-API {role.value}",
            email=f"{role.value}-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("supersecret123"),
            role=role,
            store_id=sid,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create() -> Product:
        product = Product(name=f"P-{uuid.uuid4().hex[:6]}", category="vape")
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
        price: Decimal = Decimal("9.99"),
    ) -> ProductVariant:
        prod = product if product is not None else make_product()
        variant = ProductVariant(
            product_id=prod.id,
            sku=f"SKU-{uuid.uuid4().hex[:8]}",
            price=price,
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


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


def _create_pending(
    client: TestClient,
    user: User,
    store: Store,
    variant_id: uuid.UUID,
    quantity: int = 1,
    idempotency_key: str | None = None,
) -> dict:
    payload = {
        "idempotency_key": idempotency_key or f"k-{uuid.uuid4().hex[:8]}",
        "items": [{"variant_id": str(variant_id), "quantity": quantity}],
    }
    resp = client.post(
        f"/stores/{store.id}/orders", headers=_auth(user), json=payload
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _set_order_created_at(
    db_session: Session, order_id: str, created_at: datetime
) -> None:
    order = db_session.get(Order, uuid.UUID(order_id))
    assert order is not None
    order.created_at = created_at
    db_session.add(order)
    db_session.commit()


def _assert_order_items_enriched(order: dict) -> None:
    assert order["items"]
    for item in order["items"]:
        assert item["variant_id"] == item["variant"]["id"]
        assert item["variant"]["sku"]
        assert "unit_price" in item
        assert "line_total" in item
        assert isinstance(item["unit_price"], str)
        assert isinstance(item["line_total"], str)
        product = item["variant"]["product"]
        assert product["id"]
        assert product["name"]
        assert product["category"]
        assert "compliance_status" in product
        assert "allowed_for_sale" in product
        assert "is_active" in product


def _walk(client: TestClient, user: User, order_id: str, target: str) -> None:
    resp = client.patch(
        f"/orders/{order_id}/status",
        headers=_auth(user),
        json={"new_status": target},
    )
    assert resp.status_code == 200, resp.text


_SQL_LEAK_TOKENS = [
    "psycopg",
    "DETAIL:",
    "duplicate key",
    "ERROR:",
    "violates check",
    "violates foreign key",
    "INSERT INTO",
    "UPDATE ",
    "SELECT ",
]


def _no_sql_leak(detail: str) -> bool:
    return not any(token in detail for token in _SQL_LEAK_TOKENS)


# --------------------------------------------------------------------- #
# Auth gate — anon denied on every endpoint
# --------------------------------------------------------------------- #


# (method, path_template) — `{sid}` and `{oid}` are runtime substitutions.
_ALL_ENDPOINTS = [
    ("POST", "/stores/{sid}/orders"),
    ("GET", "/stores/{sid}/orders"),
    ("GET", "/orders/{oid}"),
    ("GET", "/orders/{oid}/audit-logs"),
    ("PATCH", "/orders/{oid}/status"),
    ("POST", "/orders/{oid}/cancel"),
    ("POST", "/orders/{oid}/return"),
]


class TestApiAuthGate:
    @pytest.mark.parametrize("method,path", _ALL_ENDPOINTS)
    def test_anon_denied_on_every_endpoint(
        self, client: TestClient, make_store, method, path
    ):
        sid = make_store().id
        oid = uuid.uuid4()
        url = path.format(sid=sid, oid=oid)
        if method == "GET":
            resp = client.request(method, url)
        else:
            resp = client.request(method, url, json={})
        assert resp.status_code == 401, (
            f"{method} {url} expected 401, got {resp.status_code}"
        )

    def test_invalid_token_returns_401(
        self, client: TestClient, make_store
    ):
        store = make_store()
        resp = client.get(
            f"/stores/{store.id}/orders",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401


# --------------------------------------------------------------------- #
# Group A — Create order
# --------------------------------------------------------------------- #


_ROLES_AND_STAFF_EXPECT = [
    (UserRole.admin, 201),
    (UserRole.owner, 201),
    (UserRole.manager, 201),
    (UserRole.staff, 201),
    (UserRole.driver, 403),
]


class TestApiCreateOrder:
    @pytest.mark.parametrize("role,expected", _ROLES_AND_STAFF_EXPECT)
    def test_create_role_matrix(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        role,
        expected,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        user = (
            make_user(role)
            if role == UserRole.admin
            else make_user(role, store_id=store.id)
        )
        resp = client.post(
            f"/stores/{store.id}/orders",
            headers=_auth(user),
            json={
                "idempotency_key": f"k-{uuid.uuid4().hex[:8]}",
                "items": [
                    {"variant_id": str(item.variant_id), "quantity": 1}
                ],
            },
        )
        assert resp.status_code == expected, resp.text

    def test_created_order_is_pending(
        self, client: TestClient, make_store, make_user, make_item
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        body = _create_pending(client, staff, store, item.variant_id)
        assert body["status"] == "pending"
        assert body["store_id"] == str(store.id)
        assert len(body["items"]) == 1
        _assert_order_items_enriched(body)

    def test_create_reserves_inventory(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        db_session,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        staff = make_user(UserRole.staff, store_id=store.id)
        _create_pending(client, staff, store, item.variant_id, quantity=3)
        db_session.refresh(item)
        assert item.quantity_reserved == 3
        assert item.quantity_on_hand == 10  # not consumed yet

    def test_create_idempotency_replay_returns_same_order(
        self, client: TestClient, make_store, make_user, make_item
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        staff = make_user(UserRole.staff, store_id=store.id)
        key = f"k-{uuid.uuid4().hex[:8]}"
        first = _create_pending(
            client, staff, store, item.variant_id, idempotency_key=key
        )
        replay = _create_pending(
            client, staff, store, item.variant_id, idempotency_key=key
        )
        assert replay["id"] == first["id"]

    def test_create_with_missing_inventory_returns_422(
        self, client: TestClient, make_store, make_user, make_variant
    ):
        store = make_store()
        variant = make_variant()  # variant exists, no inventory in this store
        admin = make_user(UserRole.admin)
        resp = client.post(
            f"/stores/{store.id}/orders",
            headers=_auth(admin),
            json={
                "idempotency_key": "k-no-inv",
                "items": [
                    {"variant_id": str(variant.id), "quantity": 1}
                ],
            },
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert _no_sql_leak(detail), f"SQL leak in detail: {detail!r}"


# --------------------------------------------------------------------- #
# Group B — List + read
# --------------------------------------------------------------------- #


_ROLES_AND_READ_EXPECT = [
    (UserRole.admin, 200),
    (UserRole.owner, 200),
    (UserRole.manager, 200),
    (UserRole.staff, 200),
    (UserRole.driver, 403),
]


class TestApiListOrders:
    @pytest.mark.parametrize("role,expected", _ROLES_AND_READ_EXPECT)
    def test_list_role_matrix(
        self,
        client: TestClient,
        make_store,
        make_user,
        role,
        expected,
    ):
        store = make_store()
        user = (
            make_user(role)
            if role == UserRole.admin
            else make_user(role, store_id=store.id)
        )
        resp = client.get(
            f"/stores/{store.id}/orders", headers=_auth(user)
        )
        assert resp.status_code == expected

    def test_list_returns_only_orders_for_this_store(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store_a = make_store(code="la")
        store_b = make_store(code="lb")
        item_a = make_item(store=store_a, quantity_on_hand=5)
        item_b = make_item(store=store_b, quantity_on_hand=5)
        admin = make_user(UserRole.admin)

        oa = _create_pending(client, admin, store_a, item_a.variant_id)
        ob = _create_pending(client, admin, store_b, item_b.variant_id)

        resp = client.get(
            f"/stores/{store_a.id}/orders", headers=_auth(admin)
        )
        assert resp.status_code == 200
        body = resp.json()
        ids = [o["id"] for o in body["items"]]
        assert body["total"] == 1
        assert oa["id"] in ids
        assert ob["id"] not in ids

    def test_list_returns_paginated_envelope_with_defaults(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        admin = make_user(UserRole.admin)
        order = _create_pending(client, admin, store, item.variant_id)

        resp = client.get(
            f"/stores/{store.id}/orders", headers=_auth(admin)
        )

        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"items", "total", "limit", "offset"}
        assert body["total"] == 1
        assert body["limit"] == 100
        assert body["offset"] == 0
        assert body["items"][0]["id"] == order["id"]
        assert len(body["items"][0]["items"]) == 1
        _assert_order_items_enriched(body["items"][0])

    def test_list_custom_pagination_limits_items_but_not_total(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_user(UserRole.admin)
        for _ in range(3):
            _create_pending(client, admin, store, item.variant_id)

        resp = client.get(
            f"/stores/{store.id}/orders?limit=2&offset=1",
            headers=_auth(admin),
        )

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total"] == 3
        assert body["limit"] == 2
        assert body["offset"] == 1

    @pytest.mark.parametrize(
        "query",
        ["limit=0", "limit=501", "offset=-1"],
    )
    def test_list_rejects_invalid_pagination_params(
        self, client: TestClient, make_store, make_user, query
    ):
        store = make_store()
        admin = make_user(UserRole.admin)
        resp = client.get(
            f"/stores/{store.id}/orders?{query}", headers=_auth(admin)
        )
        assert resp.status_code == 422

    def test_list_filter_by_status_query_param(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_user(UserRole.admin)

        kept = _create_pending(client, admin, store, item.variant_id)
        canceled_target = _create_pending(
            client, admin, store, item.variant_id
        )
        # Cancel the second order.
        cancel = client.post(
            f"/orders/{canceled_target['id']}/cancel",
            headers=_auth(admin),
            json={"reason": "no longer wanted"},
        )
        assert cancel.status_code == 200

        resp = client.get(
            f"/stores/{store.id}/orders?status=pending",
            headers=_auth(admin),
        )
        assert resp.status_code == 200
        body = resp.json()
        ids = [o["id"] for o in body["items"]]
        assert body["total"] == 1
        assert kept["id"] in ids
        assert canceled_target["id"] not in ids

    def test_list_filter_by_created_from_updates_items_and_total(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        db_session,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_user(UserRole.admin)
        old = _create_pending(client, admin, store, item.variant_id)
        new = _create_pending(client, admin, store, item.variant_id)
        base = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
        _set_order_created_at(db_session, old["id"], base - timedelta(days=2))
        _set_order_created_at(db_session, new["id"], base)

        resp = client.get(
            f"/stores/{store.id}/orders",
            headers=_auth(admin),
            params={"created_from": base.isoformat()},
        )

        assert resp.status_code == 200
        body = resp.json()
        ids = [o["id"] for o in body["items"]]
        assert body["total"] == 1
        assert new["id"] in ids
        assert old["id"] not in ids

    def test_list_filter_by_created_to_updates_items_and_total(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        db_session,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_user(UserRole.admin)
        old = _create_pending(client, admin, store, item.variant_id)
        new = _create_pending(client, admin, store, item.variant_id)
        base = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
        _set_order_created_at(db_session, old["id"], base - timedelta(days=2))
        _set_order_created_at(db_session, new["id"], base)

        cutoff = base - timedelta(days=1)
        resp = client.get(
            f"/stores/{store.id}/orders",
            headers=_auth(admin),
            params={"created_to": cutoff.isoformat()},
        )

        assert resp.status_code == 200
        body = resp.json()
        ids = [o["id"] for o in body["items"]]
        assert body["total"] == 1
        assert old["id"] in ids
        assert new["id"] not in ids

    def test_list_orders_by_created_at_desc_then_id_desc(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        db_session,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        admin = make_user(UserRole.admin)
        older = _create_pending(client, admin, store, item.variant_id)
        tied_a = _create_pending(client, admin, store, item.variant_id)
        tied_b = _create_pending(client, admin, store, item.variant_id)
        base = datetime(2026, 1, 10, 12, 0, tzinfo=UTC)
        _set_order_created_at(db_session, older["id"], base - timedelta(days=1))
        _set_order_created_at(db_session, tied_a["id"], base)
        _set_order_created_at(db_session, tied_b["id"], base)

        resp = client.get(
            f"/stores/{store.id}/orders", headers=_auth(admin)
        )

        assert resp.status_code == 200
        ids = [o["id"] for o in resp.json()["items"]]
        tied_expected = sorted([tied_a["id"], tied_b["id"]], reverse=True)
        assert ids[:2] == tied_expected
        assert ids[2] == older["id"]


class TestApiGetOrder:
    def test_member_can_read_order(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)
        resp = client.get(
            f"/orders/{order['id']}", headers=_auth(staff)
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == order["id"]
        _assert_order_items_enriched(resp.json())

    def test_get_missing_order_returns_404(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.get(
            f"/orders/{uuid.uuid4()}", headers=_auth(admin)
        )
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert _no_sql_leak(detail)

    def test_admin_can_read_cross_store_order(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        other = make_store(code="other")
        item = make_item(store=store, quantity_on_hand=5)
        staff_in_store = make_user(UserRole.staff, store_id=store.id)
        admin = make_user(UserRole.admin)

        order = _create_pending(
            client, staff_in_store, store, item.variant_id
        )

        # Admin doesn't even need a store-scoped path — direct read works.
        resp = client.get(
            f"/orders/{order['id']}", headers=_auth(admin)
        )
        assert resp.status_code == 200

    def test_user_from_other_store_cannot_read(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        own = make_store(code="own-r")
        other = make_store(code="other-r")
        item = make_item(store=own, quantity_on_hand=5)
        owner_in_own = make_user(UserRole.owner, store_id=own.id)
        intruder = make_user(UserRole.owner, store_id=other.id)

        order = _create_pending(
            client, owner_in_own, own, item.variant_id
        )

        resp = client.get(
            f"/orders/{order['id']}", headers=_auth(intruder)
        )
        assert resp.status_code == 403


# --------------------------------------------------------------------- #
# Group C — Status transitions
# --------------------------------------------------------------------- #


class TestApiTransitionStatus:
    def test_staff_can_advance_pending_to_accepted(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)
        resp = client.patch(
            f"/orders/{order['id']}/status",
            headers=_auth(staff),
            json={"new_status": "accepted"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"
        assert resp.json()["accepted_at"] is not None
        _assert_order_items_enriched(resp.json())

    def test_invalid_transition_returns_422(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)
        # pending → ready is not allowed.
        resp = client.patch(
            f"/orders/{order['id']}/status",
            headers=_auth(staff),
            json={"new_status": "ready"},
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert _no_sql_leak(detail)

    def test_status_endpoint_rejects_canceled_target(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)
        resp = client.patch(
            f"/orders/{order['id']}/status",
            headers=_auth(staff),
            json={"new_status": "canceled"},
        )
        # Service routes operators to /cancel for cancellation.
        assert resp.status_code == 422

    def test_status_endpoint_rejects_returned_target(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)
        resp = client.patch(
            f"/orders/{order['id']}/status",
            headers=_auth(staff),
            json={"new_status": "returned"},
        )
        assert resp.status_code == 422

    def test_driver_denied_on_status(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        driver = make_user(UserRole.driver, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)
        resp = client.patch(
            f"/orders/{order['id']}/status",
            headers=_auth(driver),
            json={"new_status": "accepted"},
        )
        assert resp.status_code == 403


# --------------------------------------------------------------------- #
# Group D — Cancel
# --------------------------------------------------------------------- #


_ROLES_AND_MGR_EXPECT = [
    (UserRole.admin, 200),
    (UserRole.owner, 200),
    (UserRole.manager, 200),
    (UserRole.staff, 403),
    (UserRole.driver, 403),
]


class TestApiCancel:
    @pytest.mark.parametrize("role,expected", _ROLES_AND_MGR_EXPECT)
    def test_cancel_role_matrix(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        role,
        expected,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        # Always use a staff member to first create the order.
        staff = make_user(UserRole.staff, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)

        actor = (
            make_user(role)
            if role == UserRole.admin
            else make_user(role, store_id=store.id)
        )
        resp = client.post(
            f"/orders/{order['id']}/cancel",
            headers=_auth(actor),
            json={"reason": "test cancel"},
        )
        assert resp.status_code == expected

    def test_cancel_releases_reservation(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        db_session,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        staff = make_user(UserRole.staff, store_id=store.id)
        manager = make_user(UserRole.manager, store_id=store.id)
        order = _create_pending(
            client, staff, store, item.variant_id, quantity=4
        )
        db_session.refresh(item)
        assert item.quantity_reserved == 4

        resp = client.post(
            f"/orders/{order['id']}/cancel",
            headers=_auth(manager),
            json={"reason": "operational"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "canceled"
        assert body["canceled_at"] is not None
        assert body["cancel_reason"] == "operational"
        _assert_order_items_enriched(body)

        db_session.refresh(item)
        assert item.quantity_reserved == 0
        assert item.quantity_on_hand == 10

    def test_cancel_cross_store_denied(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        own = make_store(code="own-c")
        other = make_store(code="other-c")
        item = make_item(store=own, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=own.id)
        intruder_mgr = make_user(UserRole.manager, store_id=other.id)
        order = _create_pending(client, staff, own, item.variant_id)

        resp = client.post(
            f"/orders/{order['id']}/cancel",
            headers=_auth(intruder_mgr),
            json={"reason": "trying"},
        )
        assert resp.status_code == 403


# --------------------------------------------------------------------- #
# Group E — Return
# --------------------------------------------------------------------- #


class TestApiReturn:
    @pytest.mark.parametrize("role,expected", _ROLES_AND_MGR_EXPECT)
    def test_return_role_matrix_after_delivery(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        role,
        expected,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        staff = make_user(UserRole.staff, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)
        # Walk to delivered first.
        for s in ("accepted", "preparing", "ready", "delivered"):
            _walk(client, staff, order["id"], s)

        actor = (
            make_user(role)
            if role == UserRole.admin
            else make_user(role, store_id=store.id)
        )
        resp = client.post(
            f"/orders/{order['id']}/return",
            headers=_auth(actor),
            json={"reason": "defective"},
        )
        assert resp.status_code == expected

    def test_return_replenishes_inventory(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        db_session,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        staff = make_user(UserRole.staff, store_id=store.id)
        manager = make_user(UserRole.manager, store_id=store.id)
        order = _create_pending(
            client, staff, store, item.variant_id, quantity=2
        )
        for s in ("accepted", "preparing", "ready", "delivered"):
            _walk(client, staff, order["id"], s)
        db_session.refresh(item)
        assert item.quantity_on_hand == 8  # consumed at delivered

        resp = client.post(
            f"/orders/{order['id']}/return",
            headers=_auth(manager),
            json={"reason": "warranty"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "returned"
        assert body["returned_at"] is not None
        _assert_order_items_enriched(body)

        db_session.refresh(item)
        assert item.quantity_on_hand == 10  # back up

    def test_return_from_pending_returns_422(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        manager = make_user(UserRole.manager, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)
        resp = client.post(
            f"/orders/{order['id']}/return",
            headers=_auth(manager),
            json={"reason": "early"},
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert _no_sql_leak(detail)


# --------------------------------------------------------------------- #
# Group F — Audit logs
# --------------------------------------------------------------------- #


class TestApiAuditLogs:
    def test_member_can_read_audit_logs(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)

        resp = client.get(
            f"/orders/{order['id']}/audit-logs", headers=_auth(staff)
        )
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) == 1
        assert logs[0]["action"] == "order_created"
        assert logs[0]["new_status"] == "pending"

    def test_audit_logs_grow_per_transition(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)
        _walk(client, staff, order["id"], "accepted")

        resp = client.get(
            f"/orders/{order['id']}/audit-logs", headers=_auth(staff)
        )
        assert resp.status_code == 200
        logs = resp.json()
        actions = [lg["action"] for lg in logs]
        assert "order_created" in actions
        assert "status_changed" in actions

    def test_audit_logs_cross_store_denied(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        own = make_store(code="own-al")
        other = make_store(code="other-al")
        item = make_item(store=own, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=own.id)
        intruder = make_user(UserRole.staff, store_id=other.id)
        order = _create_pending(client, staff, own, item.variant_id)

        resp = client.get(
            f"/orders/{order['id']}/audit-logs",
            headers=_auth(intruder),
        )
        assert resp.status_code == 403

    def test_audit_logs_missing_order_returns_404(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.get(
            f"/orders/{uuid.uuid4()}/audit-logs",
            headers=_auth(admin),
        )
        assert resp.status_code == 404


# --------------------------------------------------------------------- #
# Tenancy — store-scoped paths
# --------------------------------------------------------------------- #


class TestApiTenancy:
    def test_owner_blocked_from_other_store_create(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        own = make_store(code="own-t-c")
        other = make_store(code="other-t-c")
        item_in_other = make_item(store=other, quantity_on_hand=5)
        owner_of_own = make_user(UserRole.owner, store_id=own.id)
        resp = client.post(
            f"/stores/{other.id}/orders",
            headers=_auth(owner_of_own),
            json={
                "idempotency_key": f"k-{uuid.uuid4().hex[:8]}",
                "items": [
                    {"variant_id": str(item_in_other.variant_id), "quantity": 1}
                ],
            },
        )
        assert resp.status_code == 403

    def test_manager_blocked_from_other_store_list(
        self, client: TestClient, make_store, make_user
    ):
        own = make_store(code="own-t-l")
        other = make_store(code="other-t-l")
        manager = make_user(UserRole.manager, store_id=own.id)
        resp = client.get(
            f"/stores/{other.id}/orders", headers=_auth(manager)
        )
        assert resp.status_code == 403

    def test_user_without_store_binding_rejected(
        self,
        client: TestClient,
        make_store,
        make_item,
        db_session,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        rogue = User(
            full_name="rogue",
            email=f"rogue-{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("p"),
            role=UserRole.manager,
            store_id=None,
            is_active=True,
        )
        db_session.add(rogue)
        db_session.commit()
        db_session.refresh(rogue)
        resp = client.get(
            f"/stores/{store.id}/orders", headers=_auth(rogue)
        )
        assert resp.status_code == 403

    def test_admin_can_create_in_any_store(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        admin = make_user(UserRole.admin)
        resp = client.post(
            f"/stores/{store.id}/orders",
            headers=_auth(admin),
            json={
                "idempotency_key": f"k-{uuid.uuid4().hex[:8]}",
                "items": [
                    {"variant_id": str(item.variant_id), "quantity": 1}
                ],
            },
        )
        assert resp.status_code == 201


# --------------------------------------------------------------------- #
# Group G — Trust boundary at the API surface
# --------------------------------------------------------------------- #


class TestApiTrustBoundary:
    @pytest.mark.parametrize(
        "forbidden_key,forbidden_value",
        [
            ("subtotal_amount", "9.99"),
            ("tax_amount", "0.50"),
            ("total_amount", "10.49"),
            ("status", "delivered"),
            ("id", "00000000-0000-0000-0000-000000000000"),
            ("store_id", "00000000-0000-0000-0000-000000000000"),
            ("customer_user_id", "00000000-0000-0000-0000-000000000000"),
            ("created_at", "2026-01-01T00:00:00Z"),
            ("delivered_at", "2026-01-01T00:00:00Z"),
            ("cancel_reason", "anything"),
        ],
    )
    def test_create_rejects_server_managed_field(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        forbidden_key,
        forbidden_value,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        body = {
            "idempotency_key": f"k-{uuid.uuid4().hex[:8]}",
            "items": [{"variant_id": str(item.variant_id), "quantity": 1}],
            forbidden_key: forbidden_value,
        }
        resp = client.post(
            f"/stores/{store.id}/orders", headers=_auth(staff), json=body
        )
        # FastAPI returns 422 for Pydantic validation errors (extra="forbid").
        assert resp.status_code == 422

    @pytest.mark.parametrize(
        "forbidden_key,forbidden_value",
        [
            ("unit_price", "9.99"),
            ("line_total", "19.98"),
            ("inventory_item_id", "00000000-0000-0000-0000-000000000000"),
        ],
    )
    def test_create_rejects_server_managed_item_field(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        forbidden_key,
        forbidden_value,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        body = {
            "idempotency_key": f"k-{uuid.uuid4().hex[:8]}",
            "items": [
                {
                    "variant_id": str(item.variant_id),
                    "quantity": 1,
                    forbidden_key: forbidden_value,
                }
            ],
        }
        resp = client.post(
            f"/stores/{store.id}/orders", headers=_auth(staff), json=body
        )
        assert resp.status_code == 422

    def test_status_endpoint_rejects_extra_fields(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)
        resp = client.patch(
            f"/orders/{order['id']}/status",
            headers=_auth(staff),
            json={"new_status": "accepted", "delivered_at": "2026-01-01T00:00:00Z"},
        )
        assert resp.status_code == 422

    def test_cancel_endpoint_rejects_extra_fields(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        manager = make_user(UserRole.manager, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)
        resp = client.post(
            f"/orders/{order['id']}/cancel",
            headers=_auth(manager),
            json={"reason": "x", "status": "canceled"},
        )
        assert resp.status_code == 422

    def test_create_totals_come_from_db_not_payload(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_variant,
        make_item,
    ):
        """The schema rejects monetary fields outright; this test confirms
        that even when the request body is clean, the persisted totals
        match the DB price (not anything the client could have sent)."""
        store = make_store()
        variant = make_variant(price=Decimal("12.34"))
        make_item(store=store, variant=variant, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        order = _create_pending(
            client, staff, store, variant.id, quantity=3
        )
        assert order["subtotal_amount"] == "37.02"  # 12.34 * 3
        assert order["tax_amount"] == "0.00"
        assert order["total_amount"] == "37.02"
        assert order["items"][0]["unit_price"] == "12.34"
        assert order["items"][0]["line_total"] == "37.02"


# --------------------------------------------------------------------- #
# Error propagation
# --------------------------------------------------------------------- #


class TestApiErrorPropagation:
    def test_oversell_on_create_returns_422(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=2)
        staff = make_user(UserRole.staff, store_id=store.id)
        resp = client.post(
            f"/stores/{store.id}/orders",
            headers=_auth(staff),
            json={
                "idempotency_key": f"k-{uuid.uuid4().hex[:8]}",
                "items": [
                    {"variant_id": str(item.variant_id), "quantity": 99}
                ],
            },
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert _no_sql_leak(detail)

    def test_cancel_after_delivered_returns_422(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        manager = make_user(UserRole.manager, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)
        for s in ("accepted", "preparing", "ready", "delivered"):
            _walk(client, staff, order["id"], s)
        resp = client.post(
            f"/orders/{order['id']}/cancel",
            headers=_auth(manager),
            json={"reason": "too late"},
        )
        assert resp.status_code == 422


# --------------------------------------------------------------------- #
# F2.18.1B — GET /admin/orders (admin global feed)
# --------------------------------------------------------------------- #


ADMIN_ORDERS_URL = "/admin/orders"

_ADMIN_ORDERS_LIST_KEYS = {"items", "total", "limit", "offset"}

_NON_ADMIN_ROLES_FOR_ADMIN_ORDERS = (
    UserRole.owner,
    UserRole.manager,
    UserRole.staff,
    UserRole.driver,
)


class TestAdminOrdersAuthRBAC:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.get(ADMIN_ORDERS_URL)
        assert resp.status_code == 401, resp.text

    def test_invalid_token_returns_401(self, client: TestClient):
        resp = client.get(
            ADMIN_ORDERS_URL,
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401, resp.text

    def test_admin_returns_200_empty(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.get(ADMIN_ORDERS_URL, headers=_auth(admin))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == _ADMIN_ORDERS_LIST_KEYS
        assert isinstance(body["items"], list)
        assert body["total"] == 0
        assert body["limit"] == 50
        assert body["offset"] == 0

    @pytest.mark.parametrize("role", _NON_ADMIN_ROLES_FOR_ADMIN_ORDERS)
    def test_non_admin_forbidden(
        self,
        client: TestClient,
        make_user,
        role: UserRole,
    ):
        actor = make_user(role)
        resp = client.get(ADMIN_ORDERS_URL, headers=_auth(actor))
        assert resp.status_code == 403, resp.text


class TestAdminOrdersGlobalFeed:
    def test_includes_orders_from_multiple_stores(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store_a = make_store()
        store_b = make_store()
        item_a = make_item(store=store_a, quantity_on_hand=5)
        item_b = make_item(store=store_b, quantity_on_hand=5)
        staff_a = make_user(UserRole.staff, store_id=store_a.id)
        staff_b = make_user(UserRole.staff, store_id=store_b.id)
        order_a = _create_pending(client, staff_a, store_a, item_a.variant_id)
        order_b = _create_pending(client, staff_b, store_b, item_b.variant_id)

        resp = client.get(ADMIN_ORDERS_URL, headers=_auth(admin))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        ids = {row["id"] for row in body["items"]}
        assert order_a["id"] in ids
        assert order_b["id"] in ids

    def test_total_counts_pre_pagination(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        staff = make_user(UserRole.staff, store_id=store.id)
        for _ in range(5):
            item = make_item(store=store, quantity_on_hand=5)
            _create_pending(client, staff, store, item.variant_id)

        resp = client.get(
            ADMIN_ORDERS_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id), "limit": 2, "offset": 0},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2

    def test_pagination_offset(
        self,
        client: TestClient,
        db_session: Session,
        make_user,
        make_store,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        staff = make_user(UserRole.staff, store_id=store.id)
        orders = []
        for _ in range(4):
            item = make_item(store=store, quantity_on_hand=5)
            orders.append(
                _create_pending(client, staff, store, item.variant_id)
            )
        # Pin distinct created_at so DESC sort is deterministic.
        base = datetime(2025, 6, 1, tzinfo=UTC)
        for index, order in enumerate(orders):
            _set_order_created_at(
                db_session, order["id"], base + timedelta(minutes=index)
            )

        first = client.get(
            ADMIN_ORDERS_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id), "limit": 2, "offset": 0},
        ).json()
        second = client.get(
            ADMIN_ORDERS_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id), "limit": 2, "offset": 2},
        ).json()

        first_ids = {row["id"] for row in first["items"]}
        second_ids = {row["id"] for row in second["items"]}
        assert first_ids.isdisjoint(second_ids)
        assert len(first_ids) == 2
        assert len(second_ids) == 2

    def test_sort_created_at_desc(
        self,
        client: TestClient,
        db_session: Session,
        make_user,
        make_store,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        staff = make_user(UserRole.staff, store_id=store.id)
        orders = []
        for _ in range(3):
            item = make_item(store=store, quantity_on_hand=5)
            orders.append(
                _create_pending(client, staff, store, item.variant_id)
            )
        base = datetime(2025, 6, 1, tzinfo=UTC)
        for index, order in enumerate(orders):
            _set_order_created_at(
                db_session, order["id"], base + timedelta(minutes=index)
            )

        resp = client.get(
            ADMIN_ORDERS_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id), "limit": 10},
        )
        assert resp.status_code == 200, resp.text
        returned = [row["id"] for row in resp.json()["items"]]
        expected = [orders[2]["id"], orders[1]["id"], orders[0]["id"]]
        assert returned == expected


class TestAdminOrdersStoreScope:
    def test_store_id_filter_scopes_to_one_store(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store_a = make_store()
        store_b = make_store()
        item_a = make_item(store=store_a, quantity_on_hand=5)
        item_b = make_item(store=store_b, quantity_on_hand=5)
        staff_a = make_user(UserRole.staff, store_id=store_a.id)
        staff_b = make_user(UserRole.staff, store_id=store_b.id)
        order_a = _create_pending(client, staff_a, store_a, item_a.variant_id)
        _create_pending(client, staff_b, store_b, item_b.variant_id)

        resp = client.get(
            ADMIN_ORDERS_URL,
            headers=_auth(admin),
            params={"store_id": str(store_a.id)},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        ids = {row["id"] for row in body["items"]}
        assert ids == {order_a["id"]}
        for row in body["items"]:
            assert row["store_id"] == str(store_a.id)

    def test_unknown_store_id_returns_404(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.get(
            ADMIN_ORDERS_URL,
            headers=_auth(admin),
            params={"store_id": str(uuid.uuid4())},
        )
        assert resp.status_code == 404, resp.text

    def test_inactive_store_id_returns_200(
        self,
        client: TestClient,
        db_session: Session,
        make_user,
        make_store,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)
        store.is_active = False
        db_session.commit()

        resp = client.get(
            ADMIN_ORDERS_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id)},
        )
        assert resp.status_code == 200, resp.text
        ids = {row["id"] for row in resp.json()["items"]}
        assert order["id"] in ids


class TestAdminOrdersQueryFilters:
    def test_status_filter(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        staff = make_user(UserRole.staff, store_id=store.id)
        item_pending = make_item(store=store, quantity_on_hand=5)
        item_accepted = make_item(store=store, quantity_on_hand=5)
        _create_pending(client, staff, store, item_pending.variant_id)
        accepted = _create_pending(
            client, staff, store, item_accepted.variant_id
        )
        _walk(client, staff, accepted["id"], "accepted")

        resp = client.get(
            ADMIN_ORDERS_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id), "status": "accepted"},
        )
        assert resp.status_code == 200, resp.text
        ids = {row["id"] for row in resp.json()["items"]}
        assert ids == {accepted["id"]}

    def test_date_from_inclusive(
        self,
        client: TestClient,
        db_session: Session,
        make_user,
        make_store,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        staff = make_user(UserRole.staff, store_id=store.id)
        orders = []
        for _ in range(3):
            item = make_item(store=store, quantity_on_hand=5)
            orders.append(
                _create_pending(client, staff, store, item.variant_id)
            )
        base = datetime(2025, 6, 1, tzinfo=UTC)
        for index, order in enumerate(orders):
            _set_order_created_at(
                db_session, order["id"], base + timedelta(days=index)
            )

        cutoff = (base + timedelta(days=1)).isoformat()
        resp = client.get(
            ADMIN_ORDERS_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id), "date_from": cutoff},
        )
        assert resp.status_code == 200, resp.text
        ids = {row["id"] for row in resp.json()["items"]}
        assert ids == {orders[1]["id"], orders[2]["id"]}

    def test_date_to_inclusive(
        self,
        client: TestClient,
        db_session: Session,
        make_user,
        make_store,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        staff = make_user(UserRole.staff, store_id=store.id)
        orders = []
        for _ in range(3):
            item = make_item(store=store, quantity_on_hand=5)
            orders.append(
                _create_pending(client, staff, store, item.variant_id)
            )
        base = datetime(2025, 6, 1, tzinfo=UTC)
        for index, order in enumerate(orders):
            _set_order_created_at(
                db_session, order["id"], base + timedelta(days=index)
            )

        cutoff = (base + timedelta(days=1)).isoformat()
        resp = client.get(
            ADMIN_ORDERS_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id), "date_to": cutoff},
        )
        assert resp.status_code == 200, resp.text
        ids = {row["id"] for row in resp.json()["items"]}
        assert ids == {orders[0]["id"], orders[1]["id"]}

    def test_invalid_uuid_store_id_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.get(
            ADMIN_ORDERS_URL,
            headers=_auth(admin),
            params={"store_id": "not-a-uuid"},
        )
        assert resp.status_code == 422

    def test_invalid_status_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.get(
            ADMIN_ORDERS_URL,
            headers=_auth(admin),
            params={"status": "not-a-real-status"},
        )
        assert resp.status_code == 422

    def test_invalid_date_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.get(
            ADMIN_ORDERS_URL,
            headers=_auth(admin),
            params={"date_from": "not-a-date"},
        )
        assert resp.status_code == 422

    def test_limit_above_200_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.get(
            ADMIN_ORDERS_URL,
            headers=_auth(admin),
            params={"limit": 201},
        )
        assert resp.status_code == 422

    def test_response_envelope_includes_eager_items(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        staff = make_user(UserRole.staff, store_id=store.id)
        item = make_item(store=store, quantity_on_hand=5)
        _create_pending(client, staff, store, item.variant_id)

        resp = client.get(
            ADMIN_ORDERS_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id)},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["items"], "expected at least one row"
        row = body["items"][0]
        # Same eager shape as the store-scoped endpoint.
        _assert_order_items_enriched(row)


class TestAdminOrdersDoesNotBreakStoreScoped:
    """GET /admin/orders must not perturb the existing store-scoped
    orders endpoint."""

    def test_store_scoped_list_still_works_for_staff(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5)
        staff = make_user(UserRole.staff, store_id=store.id)
        order = _create_pending(client, staff, store, item.variant_id)

        resp = client.get(
            f"/stores/{store.id}/orders", headers=_auth(staff)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        ids = {row["id"] for row in body["items"]}
        assert order["id"] in ids
