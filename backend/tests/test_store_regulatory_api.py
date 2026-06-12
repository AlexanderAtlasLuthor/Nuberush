"""API-level tests for the store-scoped Regulatory routes (F2.27.6).

Exercises `/stores/{store_id}/regulatory/*` via the FastAPI TestClient:
  - the store-member RBAC/tenancy gate (owner/manager/staff on own store →
    200; wrong-store user → 403; anon → 401);
  - the store inventory boundary (only own-inventory product alerts; never
    product-less/global alerts; 404 for an out-of-scope alert detail);
  - response shape safety (no admin resolution/decision fields);
  - the absence of any lifecycle mutation endpoint.

Admin keeps `/admin/regulatory/*`; this surface adds no mutations.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import ComplianceAlert
from app.db.models import ComplianceAlertSeverity
from app.db.models import ComplianceAlertStatus
from app.db.models import InventoryItem
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import RegulatoryNotice
from app.db.models import RegulatoryNoticeType
from app.db.models import RegulatorySource
from app.db.models import RegulatorySourceKind
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
    def _create(name: str = "Reg-API") -> Store:
        store = Store(name=name, code=f"ra-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create(name: str | None = None) -> Product:
        product = Product(
            name=name or f"P-{uuid.uuid4().hex[:6]}", category="vape"
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
def make_item(db_session: Session) -> Callable[..., InventoryItem]:
    def _create(store: Store, variant: ProductVariant) -> InventoryItem:
        item = InventoryItem(
            store_id=store.id, variant_id=variant.id, quantity_on_hand=5
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        return item

    return _create


@pytest.fixture
def make_alert(db_session: Session) -> Callable[..., ComplianceAlert]:
    def _create(
        *,
        product: Product | None,
        severity: ComplianceAlertSeverity = ComplianceAlertSeverity.high,
        status: ComplianceAlertStatus = ComplianceAlertStatus.open,
    ) -> ComplianceAlert:
        source = RegulatorySource(
            name=f"src-{uuid.uuid4().hex[:8]}",
            kind=RegulatorySourceKind.manual,
        )
        db_session.add(source)
        db_session.commit()
        db_session.refresh(source)
        notice = RegulatoryNotice(
            source_id=source.id,
            title="Recall notice",
            notice_type=RegulatoryNoticeType.enforcement_notice,
            payload={"items": []},
            content_hash=uuid.uuid4().hex,
        )
        db_session.add(notice)
        db_session.commit()
        db_session.refresh(notice)
        alert = ComplianceAlert(
            notice_id=notice.id,
            product_id=product.id if product is not None else None,
            severity=severity,
            status=status,
        )
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)
        return alert

    return _create


def _alerts_url(store_id) -> str:
    return f"/stores/{store_id}/regulatory/alerts"


@pytest.fixture
def store_with_alert(
    db_session: Session, make_store, make_variant, make_item, make_alert
):
    """A store carrying one product that has one open alert."""
    store = make_store()
    variant = make_variant()
    make_item(store, variant)
    product = db_session.get(Product, variant.product_id)
    alert = make_alert(product=product)
    return store, product, alert


# --------------------------------------------------------------------- #
# RBAC / tenancy
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "role", [UserRole.owner, UserRole.manager, UserRole.staff]
)
def test_store_member_can_list_own_store(
    client: TestClient, db_session: Session, store_with_alert, role
):
    store, _product, alert = store_with_alert
    user = central_make_user(db_session, role=role, store_id=store.id)

    resp = client.get(_alerts_url(store.id), headers=_auth(user))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert {"items", "total", "limit", "offset"} <= body.keys()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(alert.id)


def test_wrong_store_user_is_blocked(
    client: TestClient, db_session: Session, store_with_alert, make_store
):
    store, _product, _alert = store_with_alert
    other_store = make_store("other")
    intruder = central_make_user(
        db_session, role=UserRole.owner, store_id=other_store.id
    )

    resp = client.get(_alerts_url(store.id), headers=_auth(intruder))

    assert resp.status_code == 403


def test_driver_is_blocked_even_on_own_store(
    client: TestClient, db_session: Session, store_with_alert
):
    """Dr.1.1.B: a driver assigned to THIS store still gets 403.

    The store-member tenancy gate passes for a same-store driver, so this
    proves the role gate (`require_staff_or_above`) — not tenancy — is what
    keeps drivers out of the store regulatory surface.
    """
    store, _product, _alert = store_with_alert
    driver = central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )

    resp = client.get(_alerts_url(store.id), headers=_auth(driver))

    assert resp.status_code == 403


def test_anonymous_is_blocked(client: TestClient, store_with_alert):
    store, _product, _alert = store_with_alert
    assert client.get(_alerts_url(store.id)).status_code == 401


# --------------------------------------------------------------------- #
# Detail
# --------------------------------------------------------------------- #


def test_detail_for_own_inventory_product(
    client: TestClient, db_session: Session, store_with_alert
):
    store, product, alert = store_with_alert
    user = central_make_user(
        db_session, role=UserRole.owner, store_id=store.id
    )

    resp = client.get(
        f"{_alerts_url(store.id)}/{alert.id}", headers=_auth(user)
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(alert.id)
    assert body["product_id"] == str(product.id)


def test_detail_404_for_alert_outside_inventory(
    client: TestClient,
    db_session: Session,
    make_store,
    make_variant,
    make_item,
    make_product,
    make_alert,
):
    store = make_store()
    carried = make_variant()
    make_item(store, carried)
    outside_product = make_product()
    alert = make_alert(product=outside_product)
    user = central_make_user(
        db_session, role=UserRole.owner, store_id=store.id
    )

    resp = client.get(
        f"{_alerts_url(store.id)}/{alert.id}", headers=_auth(user)
    )

    assert resp.status_code == 404


# --------------------------------------------------------------------- #
# Boundary + shape
# --------------------------------------------------------------------- #


def test_list_excludes_null_product_alerts(
    client: TestClient,
    db_session: Session,
    make_store,
    make_variant,
    make_item,
    make_alert,
):
    store = make_store()
    variant = make_variant()
    make_item(store, variant)
    product = db_session.get(Product, variant.product_id)
    make_alert(product=product)
    make_alert(product=None)  # notice-level / global — must not appear
    user = central_make_user(
        db_session, role=UserRole.owner, store_id=store.id
    )

    resp = client.get(_alerts_url(store.id), headers=_auth(user))

    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert all(item["product_id"] is not None for item in body["items"])


def test_response_shape_omits_admin_fields(
    client: TestClient, db_session: Session, store_with_alert
):
    store, _product, _alert = store_with_alert
    user = central_make_user(
        db_session, role=UserRole.owner, store_id=store.id
    )

    resp = client.get(_alerts_url(store.id), headers=_auth(user))

    assert resp.status_code == 200
    item = resp.json()["items"][0]
    for forbidden in (
        "resolution_note",
        "resolved_by_user_id",
        "resolved_at",
        "match_id",
    ):
        assert forbidden not in item


# --------------------------------------------------------------------- #
# No lifecycle mutation endpoints
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("verb", ["acknowledge", "dismiss", "resolve"])
def test_no_lifecycle_mutation_endpoints(
    client: TestClient, db_session: Session, store_with_alert, verb
):
    store, _product, alert = store_with_alert
    user = central_make_user(
        db_session, role=UserRole.owner, store_id=store.id
    )

    resp = client.post(
        f"{_alerts_url(store.id)}/{alert.id}/{verb}",
        headers=_auth(user),
        json={"reason": "x"},
    )

    # The route does not exist (404) or rejects the method (405); never a 2xx.
    assert resp.status_code in (404, 405)


def test_admin_regulatory_still_admin_only(
    client: TestClient, db_session: Session
):
    """Regression: the store surface did not loosen the admin gate."""
    owner = central_make_user(
        db_session, role=UserRole.owner, store_id=None
    )
    resp = client.get(
        "/admin/regulatory/alerts", headers=_auth(owner)
    )
    assert resp.status_code == 403
