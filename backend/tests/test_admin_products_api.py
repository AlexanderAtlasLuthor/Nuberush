"""API-level tests for the admin products list endpoint (F2.20.1).

Exercises `GET /admin/products` via the FastAPI TestClient. Service-
level filtering, ordering and pagination behavior are covered in
`test_admin_products_service.py`; this suite focuses on:

  - auth gate (anon / invalid token → 401).
  - RBAC matrix (admin → 200, every non-admin role → 403).
  - Response envelope + item shape.
  - Query-param validation (FastAPI `Query` bounds + enum coercion).
  - Filter wiring through the API surface.
  - `total` before pagination.
  - `store_id` is NOT a supported filter (F2.20.0 §4): FastAPI
    silently ignores unknown query params in this project; we lock
    that "no effect" behavior so a future code change cannot quietly
    introduce store_id-based filtering on the global Product list.
  - No mutation endpoints under `/admin/products`.

Style mirrors test_admin_operations_api.py + test_admin_dashboard_api.py.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import Product
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user


ADMIN_PRODUCTS_URL = "/admin/products"

_TOP_LEVEL_KEYS = {"items", "total", "limit", "offset"}
_PRODUCT_ITEM_KEYS = {
    "id",
    "name",
    "brand",
    "category",
    "description",
    "compliance_status",
    "allowed_for_sale",
    "is_active",
    "hold_reason",
    "jurisdiction",
    "last_compliance_check",
    "approval_status",
    "proposed_by_store_id",
    "proposed_by_user_id",
    "reviewed_by_user_id",
    "reviewed_at",
    "rejection_reason",
    "created_at",
    "updated_at",
    "primary_image",
}

_NON_ADMIN_ROLES = (
    UserRole.owner,
    UserRole.manager,
    UserRole.staff,
    UserRole.driver,
)


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(*, is_active: bool = True) -> Store:
        store = Store(
            name=f"APAPI-{uuid.uuid4().hex[:6]}",
            code=f"api-{uuid.uuid4().hex[:8]}",
            is_active=is_active,
        )
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


# Thin adapter over tests.helpers.auth.make_user (F2.22.2.C2).
@pytest.fixture
def make_user(db_session: Session) -> Callable[..., User]:
    def _create(
        *,
        role: UserRole,
        store_id: uuid.UUID | None = None,
        is_active: bool = True,
    ) -> User:
        sid = None if role == UserRole.admin else store_id
        return central_make_user(
            db_session,
            role=role,
            store_id=sid,
            is_active=is_active,
            full_name=f"APAPI {role.value}",
        )

    return _create


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create(
        *,
        name: str | None = None,
        brand: str | None = None,
        category: str = "vape",
        description: str | None = None,
        compliance_status: ComplianceStatus = ComplianceStatus.allowed,
        allowed_for_sale: bool = True,
        is_active: bool = True,
    ) -> Product:
        product = Product(
            name=name or f"P-{uuid.uuid4().hex[:6]}",
            brand=brand,
            category=category,
            description=description,
            compliance_status=compliance_status,
            allowed_for_sale=allowed_for_sale,
            is_active=is_active,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    return _create


# --------------------------------------------------------------------- #
# A. Auth gate / RBAC
# --------------------------------------------------------------------- #


class TestAuthRBAC:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.get(ADMIN_PRODUCTS_URL)
        assert resp.status_code == 401, resp.text

    def test_invalid_token_returns_401(self, client: TestClient):
        resp = client.get(
            ADMIN_PRODUCTS_URL,
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401, resp.text

    def test_admin_returns_200(self, client: TestClient, make_user):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_PRODUCTS_URL, headers=_auth(admin)
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
            ADMIN_PRODUCTS_URL, headers=_auth(actor)
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
            ADMIN_PRODUCTS_URL, headers=_auth(admin)
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert set(body.keys()) == _TOP_LEVEL_KEYS
        assert body["limit"] == 50
        assert body["offset"] == 0
        assert body["total"] == 0
        assert body["items"] == []

    def test_product_item_shape(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        product = make_product(name="ShapeTest")
        resp = client.get(
            ADMIN_PRODUCTS_URL, headers=_auth(admin)
        )
        body = resp.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert set(item.keys()) == _PRODUCT_ITEM_KEYS
        assert item["id"] == str(product.id)
        assert item["name"] == "ShapeTest"
        # Item must NOT carry a store_id field — Product is global
        # (F2.20.0 §4).
        assert "store_id" not in item


# --------------------------------------------------------------------- #
# C. Query-param validation
# --------------------------------------------------------------------- #


class TestQueryValidation:
    def test_limit_zero_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_PRODUCTS_URL,
            headers=_auth(admin),
            params={"limit": 0},
        )
        assert resp.status_code == 422, resp.text

    def test_limit_above_max_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_PRODUCTS_URL,
            headers=_auth(admin),
            params={"limit": 201},
        )
        assert resp.status_code == 422, resp.text

    def test_limit_max_200_accepted(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_PRODUCTS_URL,
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
            ADMIN_PRODUCTS_URL,
            headers=_auth(admin),
            params={"offset": -1},
        )
        assert resp.status_code == 422, resp.text

    def test_invalid_compliance_status_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            ADMIN_PRODUCTS_URL,
            headers=_auth(admin),
            params={"compliance_status": "not_a_status"},
        )
        assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------- #
# D. Filters wired through the API
# --------------------------------------------------------------------- #


class TestFilters:
    def test_q_filter(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        target = make_product(name="Mango Ice")
        make_product(name="Strawberry Burst")
        resp = client.get(
            ADMIN_PRODUCTS_URL,
            headers=_auth(admin),
            params={"q": "mango"},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(target.id)

    def test_compliance_status_filter(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        restricted = make_product(
            compliance_status=ComplianceStatus.restricted
        )
        make_product(compliance_status=ComplianceStatus.allowed)
        resp = client.get(
            ADMIN_PRODUCTS_URL,
            headers=_auth(admin),
            params={"compliance_status": "restricted"},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(restricted.id)

    def test_allowed_for_sale_filter_false(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        no = make_product(allowed_for_sale=False)
        make_product(allowed_for_sale=True)
        resp = client.get(
            ADMIN_PRODUCTS_URL,
            headers=_auth(admin),
            params={"allowed_for_sale": "false"},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(no.id)

    def test_is_active_filter_false(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        inactive = make_product(is_active=False)
        make_product(is_active=True)
        resp = client.get(
            ADMIN_PRODUCTS_URL,
            headers=_auth(admin),
            params={"is_active": "false"},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(inactive.id)

    def test_category_filter(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        vape = make_product(category="vape")
        make_product(category="edibles")
        resp = client.get(
            ADMIN_PRODUCTS_URL,
            headers=_auth(admin),
            params={"category": "vape"},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(vape.id)


# --------------------------------------------------------------------- #
# E. Pagination
# --------------------------------------------------------------------- #


class TestPagination:
    def test_total_before_pagination(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        for _ in range(5):
            make_product()
        resp = client.get(
            ADMIN_PRODUCTS_URL,
            headers=_auth(admin),
            params={"limit": 2, "offset": 0},
        )
        body = resp.json()
        assert body["total"] == 5
        assert len(body["items"]) == 2
        assert body["limit"] == 2
        assert body["offset"] == 0

    def test_offset_advances(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        for _ in range(5):
            make_product()
        first = client.get(
            ADMIN_PRODUCTS_URL,
            headers=_auth(admin),
            params={"limit": 2, "offset": 0},
        ).json()
        second = client.get(
            ADMIN_PRODUCTS_URL,
            headers=_auth(admin),
            params={"limit": 2, "offset": 2},
        ).json()
        first_ids = {i["id"] for i in first["items"]}
        second_ids = {i["id"] for i in second["items"]}
        assert first_ids.isdisjoint(second_ids)


# --------------------------------------------------------------------- #
# F. store_id is NOT a supported filter (F2.20.0 §4)
# --------------------------------------------------------------------- #


class TestNoStoreIdFilter:
    """Product is global (F2.20.0 §4): the admin products list must
    not accept or implement a `store_id` filter.

    FastAPI in this project ignores unknown query params by default
    (the route signature does not declare `store_id`, and no
    `Query(...)` parameter binds it). We lock the "no effect"
    behavior here so a future code change cannot quietly introduce
    store_id-based filtering on the global Product list.
    """

    def test_store_id_query_param_has_no_effect_on_results(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        for _ in range(3):
            make_product()
        baseline = client.get(
            ADMIN_PRODUCTS_URL, headers=_auth(admin)
        ).json()

        with_store = client.get(
            ADMIN_PRODUCTS_URL,
            headers=_auth(admin),
            params={"store_id": str(uuid.uuid4())},
        ).json()

        # store_id is silently ignored: same total, same items.
        assert with_store["total"] == baseline["total"]
        assert (
            [i["id"] for i in with_store["items"]]
            == [i["id"] for i in baseline["items"]]
        )

    def test_store_id_with_invalid_uuid_still_has_no_effect(
        self, client: TestClient, make_user, make_product
    ):
        """Even a junk store_id value must not error or filter —
        the parameter is not bound on the route, so FastAPI does
        not validate it. This locks: there is no store_id parameter
        on `GET /admin/products`.
        """
        admin = make_user(role=UserRole.admin)
        make_product()
        resp = client.get(
            ADMIN_PRODUCTS_URL,
            headers=_auth(admin),
            params={"store_id": "not-a-uuid"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["total"] == 1


# --------------------------------------------------------------------- #
# G. No mutation routes under /admin/products
# --------------------------------------------------------------------- #


class TestNoMutationActions:
    """The contract for F2.20.1 is read-only. Compliance changes
    flow through the existing `PATCH /products/{product_id}/compliance`,
    not through `/admin/products/...` routes. Method-not-allowed
    (405) or not-found (404) responses confirm no admin-products
    mutation handler exists.
    """

    @pytest.mark.parametrize(
        "method,path",
        [
            ("POST", "/admin/products"),
            ("PATCH", f"/admin/products/{uuid.uuid4()}"),
            ("DELETE", f"/admin/products/{uuid.uuid4()}"),
            ("PATCH", f"/admin/products/{uuid.uuid4()}/compliance"),
            ("POST", f"/admin/compliance/products/{uuid.uuid4()}/review"),
        ],
    )
    def test_no_admin_products_mutation_endpoints(
        self,
        client: TestClient,
        make_user,
        method: str,
        path: str,
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.request(method, path, headers=_auth(admin))
        assert resp.status_code in (404, 405), (
            f"{method} {path} responded with {resp.status_code} — "
            "admin-products mutations are forbidden."
        )
