"""API-level tests for admin compliance oversight (F2.20.2).

Exercises:

  - `GET /admin/compliance`
  - `GET /admin/compliance/products`

via the FastAPI TestClient. Service-level filtering, counts, and
queue behavior are covered in `test_admin_compliance_service.py`;
this suite focuses on:

  - auth gate (anon / invalid token → 401).
  - RBAC matrix (admin → 200, every non-admin role → 403).
  - Response envelope + item shape.
  - Query-param validation.
  - Filter wiring through the API surface.
  - Default queue behavior end-to-end.
  - `store_id` has no effect on the queue endpoint (F2.20.0 §4).
  - No mutation endpoints exist under `/admin/compliance/...`.

Style mirrors test_admin_products_api.py + test_admin_operations_api.py.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import Product
from app.db.models import ProductComplianceAuditLog
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user


SUMMARY_URL = "/admin/compliance"
QUEUE_URL = "/admin/compliance/products"


_SUMMARY_TOP_LEVEL_KEYS = {"products", "reviews", "queue"}
_PRODUCT_COUNT_KEYS = {
    "total",
    "allowed",
    "restricted",
    "banned",
    "blocked",
    "allowed_for_sale",
    "not_allowed_for_sale",
    "inactive",
}
_REVIEW_KEYS = {"recent_count", "recent"}
_QUEUE_COUNT_KEYS = {
    "total",
    "banned",
    "restricted",
    "not_allowed_for_sale",
}
_AUDIT_ITEM_KEYS = {
    "id",
    "product_id",
    "previous_compliance_status",
    "new_compliance_status",
    "previous_allowed_for_sale",
    "new_allowed_for_sale",
    "reason",
    "changed_by_user_id",
    "created_at",
}

_LIST_TOP_LEVEL_KEYS = {"items", "total", "limit", "offset"}
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
            name=f"CmpAPI-{uuid.uuid4().hex[:6]}",
            code=f"ca-{uuid.uuid4().hex[:8]}",
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
            full_name=f"CmpAPI {role.value}",
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


@pytest.fixture
def make_audit(
    db_session: Session,
) -> Callable[..., ProductComplianceAuditLog]:
    def _create(
        *,
        product: Product,
        reason: str = "routine review",
    ) -> ProductComplianceAuditLog:
        row = ProductComplianceAuditLog(
            product_id=product.id,
            previous_compliance_status=ComplianceStatus.allowed,
            new_compliance_status=ComplianceStatus.restricted,
            previous_allowed_for_sale=True,
            new_allowed_for_sale=True,
            reason=reason,
        )
        db_session.add(row)
        db_session.commit()
        db_session.refresh(row)
        return row

    return _create


# --------------------------------------------------------------------- #
# A. GET /admin/compliance — auth gate / RBAC
# --------------------------------------------------------------------- #


class TestSummaryAuthRBAC:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.get(SUMMARY_URL)
        assert resp.status_code == 401, resp.text

    def test_invalid_token_returns_401(self, client: TestClient):
        resp = client.get(
            SUMMARY_URL,
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401, resp.text

    def test_admin_returns_200(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(SUMMARY_URL, headers=_auth(admin))
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
        resp = client.get(SUMMARY_URL, headers=_auth(actor))
        assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------- #
# B. GET /admin/compliance — response shape + counts
# --------------------------------------------------------------------- #


class TestSummaryResponse:
    def test_top_level_shape_empty_db(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(SUMMARY_URL, headers=_auth(admin))
        body = resp.json()
        assert set(body.keys()) == _SUMMARY_TOP_LEVEL_KEYS
        assert set(body["products"].keys()) == _PRODUCT_COUNT_KEYS
        assert set(body["reviews"].keys()) == _REVIEW_KEYS
        assert set(body["queue"].keys()) == _QUEUE_COUNT_KEYS

        assert body["products"]["total"] == 0
        assert body["reviews"]["recent_count"] == 0
        assert body["reviews"]["recent"] == []
        assert body["queue"]["total"] == 0

    def test_counts_reflect_seeded_state(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        make_product(compliance_status=ComplianceStatus.allowed)
        make_product(
            compliance_status=ComplianceStatus.restricted,
            allowed_for_sale=True,
        )
        make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )

        resp = client.get(SUMMARY_URL, headers=_auth(admin))
        body = resp.json()
        assert body["products"]["total"] == 3
        assert body["products"]["allowed"] == 1
        assert body["products"]["restricted"] == 1
        assert body["products"]["banned"] == 1
        # restricted (1) + banned (1) = 2 blockers.
        assert body["products"]["blocked"] == 2
        assert body["queue"]["total"] == 2
        assert body["queue"]["banned"] == 1
        assert body["queue"]["restricted"] == 1
        assert body["queue"]["not_allowed_for_sale"] == 1

    def test_recent_review_shape(
        self,
        client: TestClient,
        make_user,
        make_product,
        make_audit,
    ):
        admin = make_user(role=UserRole.admin)
        product = make_product()
        make_audit(product=product)
        resp = client.get(SUMMARY_URL, headers=_auth(admin))
        body = resp.json()
        assert body["reviews"]["recent_count"] == 1
        item = body["reviews"]["recent"][0]
        assert set(item.keys()) == _AUDIT_ITEM_KEYS
        assert item["product_id"] == str(product.id)


# --------------------------------------------------------------------- #
# C. GET /admin/compliance/products — auth gate / RBAC
# --------------------------------------------------------------------- #


class TestQueueAuthRBAC:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.get(QUEUE_URL)
        assert resp.status_code == 401, resp.text

    def test_invalid_token_returns_401(self, client: TestClient):
        resp = client.get(
            QUEUE_URL,
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401, resp.text

    def test_admin_returns_200(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(QUEUE_URL, headers=_auth(admin))
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
        resp = client.get(QUEUE_URL, headers=_auth(actor))
        assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------- #
# D. GET /admin/compliance/products — envelope + shape
# --------------------------------------------------------------------- #


class TestQueueEnvelope:
    def test_top_level_keys_and_defaults(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(QUEUE_URL, headers=_auth(admin))
        body = resp.json()
        assert set(body.keys()) == _LIST_TOP_LEVEL_KEYS
        assert body["limit"] == 50
        assert body["offset"] == 0
        assert body["total"] == 0
        assert body["items"] == []

    def test_product_item_shape(
        self,
        client: TestClient,
        make_user,
        make_product,
    ):
        admin = make_user(role=UserRole.admin)
        make_product(
            compliance_status=ComplianceStatus.restricted,
            name="ShapeQueue",
        )
        resp = client.get(QUEUE_URL, headers=_auth(admin))
        body = resp.json()
        assert body["total"] == 1
        item = body["items"][0]
        assert set(item.keys()) == _PRODUCT_ITEM_KEYS
        assert "store_id" not in item


# --------------------------------------------------------------------- #
# E. Query-param validation
# --------------------------------------------------------------------- #


class TestQueueQueryValidation:
    def test_limit_zero_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            QUEUE_URL, headers=_auth(admin), params={"limit": 0}
        )
        assert resp.status_code == 422, resp.text

    def test_limit_above_max_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            QUEUE_URL, headers=_auth(admin), params={"limit": 201}
        )
        assert resp.status_code == 422, resp.text

    def test_limit_max_200_accepted(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            QUEUE_URL, headers=_auth(admin), params={"limit": 200}
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["limit"] == 200

    def test_negative_offset_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            QUEUE_URL, headers=_auth(admin), params={"offset": -1}
        )
        assert resp.status_code == 422, resp.text

    def test_invalid_compliance_status_returns_422(
        self, client: TestClient, make_user
    ):
        admin = make_user(role=UserRole.admin)
        resp = client.get(
            QUEUE_URL,
            headers=_auth(admin),
            params={"compliance_status": "not_a_status"},
        )
        assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------- #
# F. Filters
# --------------------------------------------------------------------- #


class TestQueueFilters:
    def test_q_filter(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        target = make_product(
            name="Mango",
            compliance_status=ComplianceStatus.restricted,
        )
        make_product(
            name="Strawberry",
            compliance_status=ComplianceStatus.restricted,
        )
        resp = client.get(
            QUEUE_URL,
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
        make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        resp = client.get(
            QUEUE_URL,
            headers=_auth(admin),
            params={"compliance_status": "restricted"},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(restricted.id)

    def test_allowed_for_sale_false_filter(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        no = make_product(
            compliance_status=ComplianceStatus.banned,
            allowed_for_sale=False,
        )
        make_product(
            compliance_status=ComplianceStatus.restricted,
            allowed_for_sale=True,
        )
        resp = client.get(
            QUEUE_URL,
            headers=_auth(admin),
            params={"allowed_for_sale": "false"},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(no.id)

    def test_is_active_filter_combines_with_default_queue(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        inactive_blocker = make_product(
            compliance_status=ComplianceStatus.restricted,
            is_active=False,
        )
        make_product(
            compliance_status=ComplianceStatus.restricted,
            is_active=True,
        )
        resp = client.get(
            QUEUE_URL,
            headers=_auth(admin),
            params={"is_active": "false"},
        )
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == str(inactive_blocker.id)


# --------------------------------------------------------------------- #
# G. Default queue behavior end-to-end
# --------------------------------------------------------------------- #


class TestDefaultQueueViaAPI:
    def test_default_excludes_allowed_plus_allowed_for_sale(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        make_product(
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
        )
        resp = client.get(QUEUE_URL, headers=_auth(admin))
        body = resp.json()
        assert body["total"] == 0


# --------------------------------------------------------------------- #
# H. store_id has no effect (F2.20.0 §4)
# --------------------------------------------------------------------- #


class TestNoStoreIdFilter:
    """Product is global (F2.20.0 §4): the compliance queue must
    not accept or implement a `store_id` filter. The route has no
    `Query(...)` parameter bound to `store_id`, so FastAPI silently
    ignores it.
    """

    def test_store_id_has_no_effect_on_results(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        for _ in range(3):
            make_product(
                compliance_status=ComplianceStatus.restricted
            )
        baseline = client.get(QUEUE_URL, headers=_auth(admin)).json()
        with_store = client.get(
            QUEUE_URL,
            headers=_auth(admin),
            params={"store_id": str(uuid.uuid4())},
        ).json()
        assert with_store["total"] == baseline["total"]
        assert (
            [i["id"] for i in with_store["items"]]
            == [i["id"] for i in baseline["items"]]
        )

    def test_invalid_store_id_value_still_has_no_effect(
        self, client: TestClient, make_user, make_product
    ):
        admin = make_user(role=UserRole.admin)
        make_product(compliance_status=ComplianceStatus.banned, allowed_for_sale=False)
        resp = client.get(
            QUEUE_URL,
            headers=_auth(admin),
            params={"store_id": "not-a-uuid"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["total"] == 1


# --------------------------------------------------------------------- #
# I. No mutation endpoints under /admin/compliance/...
# --------------------------------------------------------------------- #


class TestNoMutationActions:
    """F2.20.0 §3 / §12: compliance changes flow through the
    existing canonical `PATCH /products/{product_id}/compliance`,
    not through `/admin/compliance/...`. No duplicate review
    endpoint, no incidents/tasks workflow, no mutations under
    the compliance namespace.
    """

    @pytest.mark.parametrize(
        "method,path",
        [
            ("PATCH", f"/admin/compliance/products/{uuid.uuid4()}/review"),
            ("POST", f"/admin/compliance/products/{uuid.uuid4()}/review"),
            ("PATCH", f"/admin/compliance/products/{uuid.uuid4()}"),
            ("POST", "/admin/compliance/incidents"),
            ("POST", "/admin/compliance/tasks"),
            ("POST", SUMMARY_URL),
            ("POST", QUEUE_URL),
            ("DELETE", QUEUE_URL),
        ],
    )
    def test_no_admin_compliance_mutation_endpoints(
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
            "admin-compliance mutations are forbidden."
        )
