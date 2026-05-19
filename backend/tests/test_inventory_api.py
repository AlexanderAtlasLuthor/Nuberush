"""API-level tests for the inventory module (S4).

Exercises the FastAPI router via TestClient. Covers:
  - auth gate on every inventory endpoint (anon -> 401)
  - RBAC matrices per tier (read / manager / staff)
  - tenancy (cross-store rejection on store-scoped AND item-scoped
    endpoints, admin cross-store bypass)
  - service-error propagation (404 / 409 / 422) with no SQL leak
  - end-to-end integration (manager-receive → staff-sell flow,
    reserve/release round-trip, compliance cascade through API,
    quarantined item blocks sale through API)

Schema validation and service-level behaviour live in
test_inventory_schemas.py and test_inventory_services.py
respectively (S4.6) and are not duplicated here.

Concurrency is intentionally out of scope (S4.8).
"""

import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from decimal import Decimal
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import InventoryStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.products import ProductComplianceUpdate
from app.services import products as prod_svc
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(code: str | None = None) -> Store:
        store = Store(name="Inv-API", code=code or f"ia-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


# Thin adapter over tests.helpers.auth.make_user (F2.22.2.C2).
@pytest.fixture
def make_user(db_session: Session, make_store) -> Callable[..., User]:
    def _create(role: UserRole, store_id: uuid.UUID | None = None) -> User:
        if role == UserRole.admin:
            sid = None
        else:
            sid = store_id if store_id is not None else make_store().id
        return central_make_user(
            db_session,
            role=role,
            store_id=sid,
            full_name=f"Inv-API {role.value}",
            is_active=True,
        )

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
    def _create(product: Product | None = None) -> ProductVariant:
        prod = product if product is not None else make_product()
        variant = ProductVariant(
            product_id=prod.id,
            sku=f"SKU-{uuid.uuid4().hex[:8]}",
            price=Decimal("9.99"),
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


# Forbidden substrings that would indicate a raw SQL/psycopg leak in
# any error detail returned by the API.
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


# (method, path_template) — `{sid}` and `{iid}` are replaced at runtime.
_ALL_ENDPOINTS = [
    ("GET", "/stores/{sid}/inventory"),
    ("GET", "/inventory/{iid}"),
    ("GET", "/stores/{sid}/inventory/logs"),
    ("GET", "/inventory/{iid}/logs"),
    ("POST", "/stores/{sid}/inventory/items"),
    ("PATCH", "/inventory/{iid}/threshold"),
    ("PATCH", "/inventory/{iid}/status"),
    ("POST", "/inventory/{iid}/receive"),
    ("POST", "/inventory/{iid}/adjust"),
    ("POST", "/inventory/{iid}/damage"),
    ("POST", "/inventory/{iid}/sell"),
    ("POST", "/inventory/{iid}/reserve"),
    ("POST", "/inventory/{iid}/release"),
    ("POST", "/inventory/{iid}/return"),
]


class TestApiAuthGate:
    @pytest.mark.parametrize("method,path", _ALL_ENDPOINTS)
    def test_anon_denied_on_every_endpoint(
        self, client: TestClient, make_item, method, path
    ):
        item = make_item()
        url = path.format(sid=item.store_id, iid=item.id)
        if method == "GET":
            resp = client.request(method, url)
        else:
            resp = client.request(method, url, json={})
        assert resp.status_code == 401, (
            f"{method} {url} expected 401, got {resp.status_code}"
        )

    def test_invalid_token_returns_401(
        self, client: TestClient, make_item
    ):
        item = make_item()
        resp = client.get(
            f"/inventory/{item.id}",
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401


# --------------------------------------------------------------------- #
# Read tier — admin / owner / manager / staff allowed; driver denied
# --------------------------------------------------------------------- #


_READ_ENDPOINTS = [
    ("GET", "/stores/{sid}/inventory"),
    ("GET", "/inventory/{iid}"),
    ("GET", "/stores/{sid}/inventory/logs"),
    ("GET", "/inventory/{iid}/logs"),
]

_ROLES_AND_READ_EXPECT = [
    (UserRole.admin, 200),
    (UserRole.owner, 200),
    (UserRole.manager, 200),
    (UserRole.staff, 200),
    (UserRole.driver, 403),
]


class TestApiReadAccess:
    @pytest.mark.parametrize("method,path", _READ_ENDPOINTS)
    @pytest.mark.parametrize("role,expected", _ROLES_AND_READ_EXPECT)
    def test_role_matrix_on_read_endpoints(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        method,
        path,
        role,
        expected,
    ):
        store = make_store()
        item = make_item(store=store)
        # Bind non-admin users to the same store the item lives in so
        # the matrix isolates RBAC from tenancy. Admin gets no store_id.
        user = (
            make_user(role)
            if role == UserRole.admin
            else make_user(role, store_id=store.id)
        )
        url = path.format(sid=store.id, iid=item.id)
        resp = client.request(method, url, headers=_auth(user))
        assert resp.status_code == expected, resp.text


# --------------------------------------------------------------------- #
# Manager tier — admin / owner / manager allowed; staff / driver denied
# --------------------------------------------------------------------- #


_ROLES_AND_MGR_EXPECT = [
    (UserRole.admin, 200),
    (UserRole.owner, 200),
    (UserRole.manager, 200),
    (UserRole.staff, 403),
    (UserRole.driver, 403),
]


class TestApiManagerTier:
    @pytest.mark.parametrize("role,expected", _ROLES_AND_MGR_EXPECT)
    def test_receive_role_matrix(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        role,
        expected,
    ):
        store = make_store()
        item = make_item(store=store)
        user = (
            make_user(role)
            if role == UserRole.admin
            else make_user(role, store_id=store.id)
        )
        resp = client.post(
            f"/inventory/{item.id}/receive",
            headers=_auth(user),
            json={"quantity": 1},
        )
        assert resp.status_code == expected

    # Spot checks confirm the SAME gate is applied to every other
    # manager-tier endpoint. We hit each one with a staff token and
    # expect 403 (rejected before any business logic runs).

    def test_create_item_blocks_staff(
        self, client: TestClient, make_store, make_user, make_variant
    ):
        store = make_store()
        variant = make_variant()
        staff = make_user(UserRole.staff, store_id=store.id)
        resp = client.post(
            f"/stores/{store.id}/inventory/items",
            headers=_auth(staff),
            json={"variant_id": str(variant.id)},
        )
        assert resp.status_code == 403

    def test_threshold_blocks_staff(
        self, client: TestClient, make_store, make_user, make_item
    ):
        store = make_store()
        item = make_item(store=store)
        staff = make_user(UserRole.staff, store_id=store.id)
        resp = client.patch(
            f"/inventory/{item.id}/threshold",
            headers=_auth(staff),
            json={"reorder_threshold": 5},
        )
        assert resp.status_code == 403

    def test_status_blocks_staff(
        self, client: TestClient, make_store, make_user, make_item
    ):
        store = make_store()
        item = make_item(store=store)
        staff = make_user(UserRole.staff, store_id=store.id)
        resp = client.patch(
            f"/inventory/{item.id}/status",
            headers=_auth(staff),
            json={"status": "flagged"},
        )
        assert resp.status_code == 403

    def test_adjust_blocks_staff(
        self, client: TestClient, make_store, make_user, make_item
    ):
        store = make_store()
        item = make_item(store=store)
        staff = make_user(UserRole.staff, store_id=store.id)
        resp = client.post(
            f"/inventory/{item.id}/adjust",
            headers=_auth(staff),
            json={"delta": 1, "reason": "ok"},
        )
        assert resp.status_code == 403

    def test_damage_blocks_staff(
        self, client: TestClient, make_store, make_user, make_item
    ):
        store = make_store()
        item = make_item(store=store)
        staff = make_user(UserRole.staff, store_id=store.id)
        resp = client.post(
            f"/inventory/{item.id}/damage",
            headers=_auth(staff),
            json={"quantity": 1, "reason": "broken"},
        )
        assert resp.status_code == 403


# --------------------------------------------------------------------- #
# Staff tier — admin / owner / manager / staff allowed; driver denied
# --------------------------------------------------------------------- #


_ROLES_AND_STAFF_EXPECT = [
    (UserRole.admin, 200),
    (UserRole.owner, 200),
    (UserRole.manager, 200),
    (UserRole.staff, 200),
    (UserRole.driver, 403),
]


class TestApiStaffTier:
    @pytest.mark.parametrize("role,expected", _ROLES_AND_STAFF_EXPECT)
    def test_sell_role_matrix(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
        role,
        expected,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=20)
        user = (
            make_user(role)
            if role == UserRole.admin
            else make_user(role, store_id=store.id)
        )
        resp = client.post(
            f"/inventory/{item.id}/sell",
            headers=_auth(user),
            json={"quantity": 1},
        )
        assert resp.status_code == expected

    def test_reserve_blocks_driver(
        self, client: TestClient, make_store, make_user, make_item
    ):
        store = make_store()
        item = make_item(store=store)
        driver = make_user(UserRole.driver, store_id=store.id)
        resp = client.post(
            f"/inventory/{item.id}/reserve",
            headers=_auth(driver),
            json={"quantity": 1},
        )
        assert resp.status_code == 403

    def test_release_blocks_driver(
        self, client: TestClient, make_store, make_user, make_item
    ):
        store = make_store()
        item = make_item(store=store)
        driver = make_user(UserRole.driver, store_id=store.id)
        resp = client.post(
            f"/inventory/{item.id}/release",
            headers=_auth(driver),
            json={"quantity": 1},
        )
        assert resp.status_code == 403

    def test_return_blocks_driver(
        self, client: TestClient, make_store, make_user, make_item
    ):
        store = make_store()
        item = make_item(store=store)
        driver = make_user(UserRole.driver, store_id=store.id)
        resp = client.post(
            f"/inventory/{item.id}/return",
            headers=_auth(driver),
            json={"quantity": 1, "reason": "defect"},
        )
        assert resp.status_code == 403


# --------------------------------------------------------------------- #
# Tenancy — store-scoped AND item-scoped
# --------------------------------------------------------------------- #


class TestApiTenancy:
    def test_owner_blocked_from_other_store_inventory_list(
        self, client: TestClient, make_store, make_user
    ):
        own = make_store(code="own-store")
        other = make_store(code="other-store")
        owner = make_user(UserRole.owner, store_id=own.id)
        resp = client.get(
            f"/stores/{other.id}/inventory", headers=_auth(owner)
        )
        assert resp.status_code == 403

    def test_manager_blocked_from_other_store_logs(
        self, client: TestClient, make_store, make_user
    ):
        own = make_store(code="own-mgr")
        other = make_store(code="other-mgr")
        manager = make_user(UserRole.manager, store_id=own.id)
        resp = client.get(
            f"/stores/{other.id}/inventory/logs", headers=_auth(manager)
        )
        assert resp.status_code == 403

    def test_manager_blocked_from_mutation_on_other_store_item(
        self, client: TestClient, make_store, make_user, make_item
    ):
        own = make_store(code="own-mut")
        other = make_store(code="other-mut")
        item_in_other = make_item(store=other)
        manager = make_user(UserRole.manager, store_id=own.id)
        resp = client.post(
            f"/inventory/{item_in_other.id}/receive",
            headers=_auth(manager),
            json={"quantity": 1},
        )
        assert resp.status_code == 403

    def test_staff_blocked_from_sell_on_other_store_item(
        self, client: TestClient, make_store, make_user, make_item
    ):
        own = make_store(code="own-staff")
        other = make_store(code="other-staff")
        item_in_other = make_item(store=other, quantity_on_hand=10)
        staff = make_user(UserRole.staff, store_id=own.id)
        resp = client.post(
            f"/inventory/{item_in_other.id}/sell",
            headers=_auth(staff),
            json={"quantity": 1},
        )
        assert resp.status_code == 403

    def test_staff_blocked_from_read_on_other_store_item(
        self, client: TestClient, make_store, make_user, make_item
    ):
        own = make_store(code="own-readstaff")
        other = make_store(code="other-readstaff")
        item_in_other = make_item(store=other)
        staff = make_user(UserRole.staff, store_id=own.id)
        resp = client.get(
            f"/inventory/{item_in_other.id}", headers=_auth(staff)
        )
        assert resp.status_code == 403

    def test_admin_can_access_any_store(
        self, client: TestClient, make_store, make_user, make_item
    ):
        store_a = make_store(code="a-cross")
        store_b = make_store(code="b-cross")
        item_in_a = make_item(store=store_a)
        admin = make_user(UserRole.admin)

        # Cross-store list
        resp = client.get(
            f"/stores/{store_b.id}/inventory", headers=_auth(admin)
        )
        assert resp.status_code == 200

        # Cross-store item read
        resp = client.get(
            f"/inventory/{item_in_a.id}", headers=_auth(admin)
        )
        assert resp.status_code == 200

    def test_user_without_store_binding_rejected(
        self,
        client: TestClient,
        make_store,
        make_item,
        db_session,
    ):
        # Manager-shaped user but with no store_id is an inconsistent
        # state the schema technically allows. The router must still
        # block them from inventory operations.
        store = make_store()
        item = make_item(store=store)
        rogue = User(
            full_name="rogue",
            email=f"rogue-{uuid.uuid4().hex[:6]}@example.com",
            role=UserRole.manager,
            store_id=None,
            is_active=True,
            # F2.22.2.D: the rogue user must be authenticatable so the
            # router's tenancy check (the actual assertion) is what
            # rejects it — not the auth layer for a missing mapping.
            auth_user_id=uuid.uuid4(),
        )
        db_session.add(rogue)
        db_session.commit()
        db_session.refresh(rogue)
        resp = client.get(
            f"/inventory/{item.id}", headers=_auth(rogue)
        )
        assert resp.status_code == 403


# --------------------------------------------------------------------- #
# Error propagation — 404 / 409 / 422 with no SQL leak
# --------------------------------------------------------------------- #


class TestApiErrorPropagation:
    def test_missing_item_returns_404_clean_detail(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.get(
            f"/inventory/{uuid.uuid4()}", headers=_auth(admin)
        )
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        assert "not found" in detail.lower()
        assert _no_sql_leak(detail), f"SQL leak in detail: {detail!r}"

    def test_duplicate_create_returns_409_clean_detail(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_variant,
    ):
        store = make_store()
        variant = make_variant()
        admin = make_user(UserRole.admin)
        first = client.post(
            f"/stores/{store.id}/inventory/items",
            headers=_auth(admin),
            json={"variant_id": str(variant.id)},
        )
        assert first.status_code == 201
        dup = client.post(
            f"/stores/{store.id}/inventory/items",
            headers=_auth(admin),
            json={"variant_id": str(variant.id)},
        )
        assert dup.status_code == 409
        detail = dup.json()["detail"]
        assert "already exists" in detail.lower()
        assert _no_sql_leak(detail), f"SQL leak in detail: {detail!r}"

    def test_oversell_returns_422_clean_detail(
        self, client: TestClient, make_store, make_user, make_item
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=2)
        staff = make_user(UserRole.staff, store_id=store.id)
        resp = client.post(
            f"/inventory/{item.id}/sell",
            headers=_auth(staff),
            json={"quantity": 99},
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert "available" in detail.lower()
        assert _no_sql_leak(detail), f"SQL leak in detail: {detail!r}"

    def test_release_more_than_reserved_returns_422_clean_detail(
        self, client: TestClient, make_store, make_user, make_item
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=5, quantity_reserved=2)
        staff = make_user(UserRole.staff, store_id=store.id)
        resp = client.post(
            f"/inventory/{item.id}/release",
            headers=_auth(staff),
            json={"quantity": 5},
        )
        assert resp.status_code == 422
        detail = resp.json()["detail"]
        assert _no_sql_leak(detail)

    def test_status_update_with_legacy_value_returns_422(
        self, client: TestClient, make_store, make_user, make_item
    ):
        # Legacy enum values (`reserved`, `sold`) are rejected at the
        # service layer per inventory_rules §4. The service raises 422;
        # the router should propagate it.
        store = make_store()
        item = make_item(store=store)
        manager = make_user(UserRole.manager, store_id=store.id)
        resp = client.patch(
            f"/inventory/{item.id}/status",
            headers=_auth(manager),
            json={"status": "sold"},
        )
        assert resp.status_code == 422
        assert _no_sql_leak(resp.json()["detail"])


# --------------------------------------------------------------------- #
# Integration — end-to-end flows through the API
# --------------------------------------------------------------------- #


class TestApiIntegration:
    def test_manager_creates_item_then_receives_then_staff_sells(
        self,
        client: TestClient,
        db_session,
        make_store,
        make_user,
        make_variant,
    ):
        store = make_store()
        variant = make_variant()
        admin = make_user(UserRole.admin)
        manager = make_user(UserRole.manager, store_id=store.id)
        staff = make_user(UserRole.staff, store_id=store.id)

        # Admin creates the item (manager could too, but admin keeps
        # the role chain explicit)
        created = client.post(
            f"/stores/{store.id}/inventory/items",
            headers=_auth(admin),
            json={"variant_id": str(variant.id), "quantity_on_hand": 0},
        )
        assert created.status_code == 201
        item_id = uuid.UUID(created.json()["id"])

        # Manager receives 10 units
        recv = client.post(
            f"/inventory/{item_id}/receive",
            headers=_auth(manager),
            json={"quantity": 10},
        )
        assert recv.status_code == 200
        assert recv.json()["quantity_on_hand"] == 10

        # Staff sells 3 units
        sale = client.post(
            f"/inventory/{item_id}/sell",
            headers=_auth(staff),
            json={"quantity": 3},
        )
        assert sale.status_code == 200
        assert sale.json()["quantity_on_hand"] == 7

        # Logs visible via the API
        logs_resp = client.get(
            f"/inventory/{item_id}/logs", headers=_auth(staff)
        )
        assert logs_resp.status_code == 200
        log_types = [row["movement_type"] for row in logs_resp.json()]
        # logs_for_item returns DESC by created_at — sale most recent
        assert "sale" in log_types
        assert "receipt" in log_types

    def test_reserve_release_round_trip_via_api(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        staff = make_user(UserRole.staff, store_id=store.id)

        r = client.post(
            f"/inventory/{item.id}/reserve",
            headers=_auth(staff),
            json={"quantity": 4},
        )
        assert r.status_code == 200
        assert r.json()["quantity_reserved"] == 4

        r = client.post(
            f"/inventory/{item.id}/release",
            headers=_auth(staff),
            json={"quantity": 4},
        )
        assert r.status_code == 200
        assert r.json()["quantity_reserved"] == 0
        assert r.json()["quantity_on_hand"] == 10

    def test_sale_creates_log_via_api(
        self,
        client: TestClient,
        db_session,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, quantity_on_hand=10)
        staff = make_user(UserRole.staff, store_id=store.id)
        client.post(
            f"/inventory/{item.id}/sell",
            headers=_auth(staff),
            json={"quantity": 2},
        )
        logs = list(
            db_session.scalars(
                select(InventoryLog).where(
                    InventoryLog.inventory_item_id == item.id
                )
            ).all()
        )
        assert len(logs) == 1
        assert logs[0].quantity_delta == -2
        assert logs[0].quantity_after == 8

    def test_banned_product_blocks_sale_via_api(
        self,
        client: TestClient,
        db_session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
    ):
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        item = make_item(store=store, variant=variant, quantity_on_hand=10)
        admin = make_user(UserRole.admin)
        staff = make_user(UserRole.staff, store_id=store.id)

        # Ban the product through the products API
        ban_resp = client.patch(
            f"/products/{product.id}/compliance",
            headers=_auth(admin),
            json={
                "compliance_status": "banned",
                "allowed_for_sale": False,
                "reason": "qa banned via api",
            },
        )
        assert ban_resp.status_code == 200

        # Sale is blocked. The sellability gate (banned product) and the
        # status gate (cascade quarantined the item) are both reasons —
        # either appearing in the detail counts as defense in depth.
        sale = client.post(
            f"/inventory/{item.id}/sell",
            headers=_auth(staff),
            json={"quantity": 1},
        )
        assert sale.status_code == 422
        detail = sale.json()["detail"].lower()
        assert "banned" in detail or "quarantined" in detail or "sellable" in detail
        assert _no_sql_leak(sale.json()["detail"])

    def test_quarantined_item_blocks_sell_and_reserve_via_api(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        item = make_item(
            store=store,
            quantity_on_hand=10,
            status=InventoryStatus.quarantined,
        )
        staff = make_user(UserRole.staff, store_id=store.id)

        sell = client.post(
            f"/inventory/{item.id}/sell",
            headers=_auth(staff),
            json={"quantity": 1},
        )
        assert sell.status_code == 422
        assert "quarantined" in sell.json()["detail"].lower()

        reserve = client.post(
            f"/inventory/{item.id}/reserve",
            headers=_auth(staff),
            json={"quantity": 1},
        )
        assert reserve.status_code == 422
        assert "quarantined" in reserve.json()["detail"].lower()

    def test_receive_works_on_quarantined_item_via_api(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_item,
    ):
        # Per inventory_rules §4: corrective movements (receive,
        # adjust, damage, return, release) MAY proceed on quarantined
        # items so operators can rebuild state. Only sale and reserve
        # are blocked.
        store = make_store()
        item = make_item(
            store=store,
            quantity_on_hand=5,
            status=InventoryStatus.quarantined,
        )
        manager = make_user(UserRole.manager, store_id=store.id)
        resp = client.post(
            f"/inventory/{item.id}/receive",
            headers=_auth(manager),
            json={"quantity": 3},
        )
        assert resp.status_code == 200
        assert resp.json()["quantity_on_hand"] == 8


# --------------------------------------------------------------------- #
# Inventory list pagination
# --------------------------------------------------------------------- #


class TestApiInventoryPagination:
    def test_default_response_shape(
        self,
        client: TestClient,
        db_session: Session,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        items = [make_item(store=store) for _ in range(2)]
        _pin_created_at(db_session, items)
        manager = make_user(UserRole.manager, store_id=store.id)

        resp = client.get(
            f"/stores/{store.id}/inventory", headers=_auth(manager)
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == {"items", "total", "limit", "offset"}
        assert body["total"] == 2
        assert body["limit"] == 100
        assert body["offset"] == 0
        assert len(body["items"]) == 2

    def test_custom_limit_offset(
        self,
        client: TestClient,
        db_session: Session,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        items = [make_item(store=store) for _ in range(4)]
        _pin_created_at(db_session, items)
        manager = make_user(UserRole.manager, store_id=store.id)

        resp = client.get(
            f"/stores/{store.id}/inventory?limit=2&offset=1",
            headers=_auth(manager),
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["limit"] == 2
        assert body["offset"] == 1
        assert body["total"] == 4
        assert [row["id"] for row in body["items"]] == [
            str(item.id) for item in items[1:3]
        ]

    def test_total_reflects_filtered_rows_not_page_size(
        self,
        client: TestClient,
        db_session: Session,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        items = [make_item(store=store) for _ in range(5)]
        _pin_created_at(db_session, items)
        manager = make_user(UserRole.manager, store_id=store.id)

        resp = client.get(
            f"/stores/{store.id}/inventory?limit=2",
            headers=_auth(manager),
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total"] == 5

    def test_offset_beyond_total_returns_empty_items(
        self,
        client: TestClient,
        db_session: Session,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        items = [make_item(store=store) for _ in range(3)]
        _pin_created_at(db_session, items)
        manager = make_user(UserRole.manager, store_id=store.id)

        resp = client.get(
            f"/stores/{store.id}/inventory?limit=2&offset=10",
            headers=_auth(manager),
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["items"] == []
        assert body["total"] == 3
        assert body["limit"] == 2
        assert body["offset"] == 10

    def test_low_stock_only_works_with_pagination_and_total(
        self,
        client: TestClient,
        db_session: Session,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
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
        _pin_created_at(db_session, [low_a, not_low, low_b])
        manager = make_user(UserRole.manager, store_id=store.id)

        resp = client.get(
            f"/stores/{store.id}/inventory"
            "?low_stock_only=true&limit=1&offset=1",
            headers=_auth(manager),
        )

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total"] == 2
        assert body["limit"] == 1
        assert body["offset"] == 1
        assert [row["id"] for row in body["items"]] == [str(low_b.id)]

    def test_stable_ordering_across_pages(
        self,
        client: TestClient,
        db_session: Session,
        make_store,
        make_user,
        make_item,
    ):
        store = make_store()
        items = [make_item(store=store) for _ in range(3)]
        _pin_created_at(db_session, items, same_timestamp=True)
        manager = make_user(UserRole.manager, store_id=store.id)

        page_ids = []
        for offset in range(3):
            resp = client.get(
                f"/stores/{store.id}/inventory?limit=1&offset={offset}",
                headers=_auth(manager),
            )
            assert resp.status_code == 200, resp.text
            page_ids.append(resp.json()["items"][0]["id"])

        assert page_ids == sorted(str(item.id) for item in items)

    @pytest.mark.parametrize(
        "query",
        [
            "limit=0",
            "limit=501",
            "offset=-1",
        ],
    )
    def test_invalid_pagination_params_return_422(
        self, client: TestClient, make_store, make_user, query
    ):
        store = make_store()
        manager = make_user(UserRole.manager, store_id=store.id)

        resp = client.get(
            f"/stores/{store.id}/inventory?{query}", headers=_auth(manager)
        )

        assert resp.status_code == 422


# --------------------------------------------------------------------- #
# BIE: enriched response shape (variant + product summary)
# --------------------------------------------------------------------- #
#
# All endpoints sharing `response_model=InventoryItemRead` must surface
# the nested `variant.sku` and `variant.product.name` populated by the
# eager-load options in the service layer. We verify the read paths
# (list + detail) and one mutation path (receive) as a proxy for "every
# mutation returns the enriched shape" — the wiring is uniform across
# all 11 endpoints (single _refresh_eager helper) so testing one
# mutation is sufficient. Other mutation endpoints are exercised in
# the existing tier-matrix tests above and would fail loudly here if
# the response_model validation rejected an unenriched object.


class TestApiEnrichedResponse:
    def test_get_inventory_list_includes_enriched_variant(
        self,
        client: TestClient,
        db_session: Session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
    ):
        store = make_store()
        product = make_product()
        # Make the product visibly distinct so a placeholder/empty
        # serialization would not accidentally pass the assertions.
        product.name = "Fizzy Cola"
        product.brand = "Acme Beverages"
        db_session.commit()
        variant = make_variant(product=product)
        variant.sku = "FZ-001"
        variant.flavor = "cherry"
        db_session.commit()
        make_item(store=store, variant=variant)

        manager = make_user(UserRole.manager, store_id=store.id)
        resp = client.get(
            f"/stores/{store.id}/inventory", headers=_auth(manager)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == {"items", "total", "limit", "offset"}
        assert body["total"] == 1
        assert len(body["items"]) == 1
        row = body["items"][0]
        # Original fields still present.
        assert row["quantity_on_hand"] == 10
        # Enriched variant summary.
        assert row["variant"]["id"] == str(variant.id)
        assert row["variant"]["sku"] == "FZ-001"
        assert row["variant"]["flavor"] == "cherry"
        assert row["variant"]["is_active"] is True
        # Enriched product summary nested under variant.
        assert row["variant"]["product"]["id"] == str(product.id)
        assert row["variant"]["product"]["name"] == "Fizzy Cola"
        assert row["variant"]["product"]["brand"] == "Acme Beverages"
        assert row["variant"]["product"]["compliance_status"] == "allowed"
        assert row["variant"]["product"]["allowed_for_sale"] is True

    def test_get_inventory_item_includes_enriched_variant(
        self,
        client: TestClient,
        db_session: Session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
    ):
        store = make_store()
        product = make_product()
        product.name = "Mint Lozenge"
        db_session.commit()
        variant = make_variant(product=product)
        variant.sku = "ML-22"
        db_session.commit()
        item = make_item(store=store, variant=variant)

        staff = make_user(UserRole.staff, store_id=store.id)
        resp = client.get(f"/inventory/{item.id}", headers=_auth(staff))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["variant"]["sku"] == "ML-22"
        assert body["variant"]["product"]["name"] == "Mint Lozenge"

    def test_post_receive_response_includes_enriched_variant(
        self,
        client: TestClient,
        db_session: Session,
        make_store,
        make_user,
        make_product,
        make_variant,
        make_item,
    ):
        # Mutation responses share the same InventoryItemRead schema as
        # reads. If _refresh_eager is wired everywhere, this passes;
        # if any mutation reverted to db.refresh(item), the lazy-loaded
        # relationships expire post-commit and Pydantic would raise on
        # response_model serialization.
        store = make_store()
        product = make_product()
        product.name = "Bubble Tea"
        db_session.commit()
        variant = make_variant(product=product)
        variant.sku = "BT-09"
        db_session.commit()
        item = make_item(
            store=store, variant=variant, quantity_on_hand=5
        )

        manager = make_user(UserRole.manager, store_id=store.id)
        resp = client.post(
            f"/inventory/{item.id}/receive",
            headers=_auth(manager),
            json={"quantity": 3},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        # Quantity mutation landed.
        assert body["quantity_on_hand"] == 8
        # Enriched variant + product survived the mutation path.
        assert body["variant"]["sku"] == "BT-09"
        assert body["variant"]["product"]["name"] == "Bubble Tea"


# --------------------------------------------------------------------- #
# F2.18.1 — GET /admin/inventory (admin global feed)
# --------------------------------------------------------------------- #


ADMIN_INVENTORY_URL = "/admin/inventory"

_ADMIN_INV_LIST_KEYS = {"items", "total", "limit", "offset"}

_NON_ADMIN_ROLES_FOR_ADMIN_INVENTORY = (
    UserRole.owner,
    UserRole.manager,
    UserRole.staff,
    UserRole.driver,
)


def _pin_updated_at(
    db_session: Session,
    items: list[InventoryItem],
    *,
    start: datetime | None = None,
    same_timestamp: bool = False,
) -> None:
    """Pin updated_at to deterministic values for sort-order assertions.

    The `trg_inventory_items_set_updated_at` BEFORE UPDATE trigger
    unconditionally rewrites `NEW.updated_at = now()`, so any plain
    UPDATE here would lose the value we want. Disable it for the
    duration of the manual writes; the test session rolls back at
    teardown, so this never leaks into production behavior.
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


class TestAdminInventoryAuthRBAC:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.get(ADMIN_INVENTORY_URL)
        assert resp.status_code == 401, resp.text

    def test_invalid_token_returns_401(self, client: TestClient):
        resp = client.get(
            ADMIN_INVENTORY_URL,
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401, resp.text

    def test_admin_returns_200_empty(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.get(ADMIN_INVENTORY_URL, headers=_auth(admin))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == _ADMIN_INV_LIST_KEYS
        assert isinstance(body["items"], list)
        assert body["total"] == 0
        assert body["limit"] == 100
        assert body["offset"] == 0

    @pytest.mark.parametrize("role", _NON_ADMIN_ROLES_FOR_ADMIN_INVENTORY)
    def test_non_admin_forbidden(
        self,
        client: TestClient,
        make_user,
        role: UserRole,
    ):
        actor = make_user(role)
        resp = client.get(ADMIN_INVENTORY_URL, headers=_auth(actor))
        assert resp.status_code == 403, resp.text


class TestAdminInventoryGlobalFeed:
    def test_includes_items_from_multiple_stores(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_variant,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store_a = make_store()
        store_b = make_store()
        item_a = make_item(store=store_a, variant=make_variant())
        item_b = make_item(store=store_b, variant=make_variant())

        resp = client.get(ADMIN_INVENTORY_URL, headers=_auth(admin))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        ids = {row["id"] for row in body["items"]}
        assert str(item_a.id) in ids
        assert str(item_b.id) in ids

    def test_total_counts_pre_pagination(
        self,
        client: TestClient,
        db_session: Session,
        make_user,
        make_store,
        make_variant,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        items = [make_item(store=store, variant=make_variant()) for _ in range(5)]
        _pin_updated_at(db_session, items)

        resp = client.get(
            ADMIN_INVENTORY_URL,
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
        make_variant,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        items = [make_item(store=store, variant=make_variant()) for _ in range(4)]
        _pin_updated_at(db_session, items)

        first = client.get(
            ADMIN_INVENTORY_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id), "limit": 2, "offset": 0},
        ).json()
        second = client.get(
            ADMIN_INVENTORY_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id), "limit": 2, "offset": 2},
        ).json()

        first_ids = {row["id"] for row in first["items"]}
        second_ids = {row["id"] for row in second["items"]}
        assert first_ids.isdisjoint(second_ids)
        assert len(first_ids) == 2
        assert len(second_ids) == 2

    def test_sort_updated_at_desc(
        self,
        client: TestClient,
        db_session: Session,
        make_user,
        make_store,
        make_variant,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        items = [make_item(store=store, variant=make_variant()) for _ in range(3)]
        _pin_updated_at(db_session, items)

        resp = client.get(
            ADMIN_INVENTORY_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id), "limit": 10},
        )
        assert resp.status_code == 200, resp.text
        returned = [row["id"] for row in resp.json()["items"]]
        expected = [str(items[2].id), str(items[1].id), str(items[0].id)]
        assert returned == expected


class TestAdminInventoryStoreScope:
    def test_store_id_filter_scopes_to_one_store(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_variant,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store_a = make_store()
        store_b = make_store()
        item_a = make_item(store=store_a, variant=make_variant())
        make_item(store=store_b, variant=make_variant())

        resp = client.get(
            ADMIN_INVENTORY_URL,
            headers=_auth(admin),
            params={"store_id": str(store_a.id)},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        ids = {row["id"] for row in body["items"]}
        assert ids == {str(item_a.id)}
        for row in body["items"]:
            assert row["store_id"] == str(store_a.id)

    def test_unknown_store_id_returns_404(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.get(
            ADMIN_INVENTORY_URL,
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
        make_variant,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        item = make_item(store=store, variant=make_variant())
        store.is_active = False
        db_session.commit()

        resp = client.get(
            ADMIN_INVENTORY_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id)},
        )
        assert resp.status_code == 200, resp.text
        ids = {row["id"] for row in resp.json()["items"]}
        assert str(item.id) in ids


class TestAdminInventoryQueryFilters:
    def test_low_stock_filter(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_variant,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        low = make_item(
            store=store,
            variant=make_variant(),
            quantity_on_hand=2,
            quantity_reserved=1,
            reorder_threshold=2,
        )
        not_low = make_item(
            store=store,
            variant=make_variant(),
            quantity_on_hand=20,
            reorder_threshold=2,
        )

        resp = client.get(
            ADMIN_INVENTORY_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id), "low_stock": True},
        )
        assert resp.status_code == 200, resp.text
        ids = {row["id"] for row in resp.json()["items"]}
        assert str(low.id) in ids
        assert str(not_low.id) not in ids

    def test_status_filter(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_variant,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        flagged = make_item(
            store=store,
            variant=make_variant(),
            status=InventoryStatus.flagged,
        )
        make_item(store=store, variant=make_variant())

        resp = client.get(
            ADMIN_INVENTORY_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id), "status": "flagged"},
        )
        assert resp.status_code == 200, resp.text
        ids = {row["id"] for row in resp.json()["items"]}
        assert ids == {str(flagged.id)}

    def test_variant_id_filter(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_variant,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store_a = make_store()
        store_b = make_store()
        target = make_variant()
        other = make_variant()
        wanted_a = make_item(store=store_a, variant=target)
        wanted_b = make_item(store=store_b, variant=target)
        make_item(store=store_a, variant=other)

        resp = client.get(
            ADMIN_INVENTORY_URL,
            headers=_auth(admin),
            params={"variant_id": str(target.id)},
        )
        assert resp.status_code == 200, resp.text
        ids = {row["id"] for row in resp.json()["items"]}
        assert ids == {str(wanted_a.id), str(wanted_b.id)}

    def test_product_id_filter(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_product,
        make_variant,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        target_product = make_product()
        other_product = make_product()
        target_variant = make_variant(product=target_product)
        other_variant = make_variant(product=other_product)
        wanted = make_item(store=store, variant=target_variant)
        make_item(store=store, variant=other_variant)

        resp = client.get(
            ADMIN_INVENTORY_URL,
            headers=_auth(admin),
            params={"product_id": str(target_product.id)},
        )
        assert resp.status_code == 200, resp.text
        ids = {row["id"] for row in resp.json()["items"]}
        assert ids == {str(wanted.id)}

    def test_q_matches_variant_sku(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_variant,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        target = make_variant()
        other = make_variant()
        wanted = make_item(store=store, variant=target)
        make_item(store=store, variant=other)

        sku_fragment = target.sku[-6:]
        resp = client.get(
            ADMIN_INVENTORY_URL,
            headers=_auth(admin),
            params={"q": sku_fragment},
        )
        assert resp.status_code == 200, resp.text
        ids = {row["id"] for row in resp.json()["items"]}
        assert str(wanted.id) in ids

    def test_invalid_uuid_store_id_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.get(
            ADMIN_INVENTORY_URL,
            headers=_auth(admin),
            params={"store_id": "not-a-uuid"},
        )
        assert resp.status_code == 422

    def test_invalid_status_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.get(
            ADMIN_INVENTORY_URL,
            headers=_auth(admin),
            params={"status": "not-a-real-status"},
        )
        assert resp.status_code == 422

    def test_limit_above_500_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin)
        resp = client.get(
            ADMIN_INVENTORY_URL,
            headers=_auth(admin),
            params={"limit": 501},
        )
        assert resp.status_code == 422

    def test_response_envelope_includes_eager_variant_product(
        self,
        client: TestClient,
        make_user,
        make_store,
        make_product,
        make_variant,
        make_item,
    ):
        admin = make_user(UserRole.admin)
        store = make_store()
        product = make_product()
        variant = make_variant(product=product)
        make_item(store=store, variant=variant)

        resp = client.get(
            ADMIN_INVENTORY_URL,
            headers=_auth(admin),
            params={"store_id": str(store.id)},
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["items"], "expected at least one row"
        row = body["items"][0]
        assert row["variant"]["sku"] == variant.sku
        assert row["variant"]["product"]["name"] == product.name


class TestAdminInventoryDoesNotBreakStoreScoped:
    """GET /admin/inventory must not perturb the existing store-scoped
    inventory endpoint."""

    def test_store_scoped_list_still_works_for_staff(
        self,
        client: TestClient,
        make_store,
        make_user,
        make_variant,
        make_item,
    ):
        store = make_store()
        item = make_item(store=store, variant=make_variant())
        staff = make_user(UserRole.staff, store_id=store.id)

        resp = client.get(
            f"/stores/{store.id}/inventory", headers=_auth(staff)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        ids = {row["id"] for row in body["items"]}
        assert str(item.id) in ids
