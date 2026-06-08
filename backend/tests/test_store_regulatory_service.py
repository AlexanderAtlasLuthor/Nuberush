"""Service-level tests for the store-scoped Regulatory surface (F2.27.6).

Exercises `app.services.store_regulatory` directly against the transactional
`db_session`. The contract under test is the tenancy boundary

    Store -> InventoryItem -> ProductVariant -> Product -> ComplianceAlert

and the store-safe projection: a store sees only alerts for products it carries,
never product-less (notice-level) alerts, never duplicated when it stocks
several variants of one product, and never any admin resolution metadata.
"""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from sqlalchemy.orm import Session

from app.db.models import ComplianceAlert
from app.db.models import ComplianceAlertSeverity
from app.db.models import ComplianceAlertStatus
from app.db.models import ComplianceRecommendedAction
from app.db.models import InventoryItem
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import RegulatoryNotice
from app.db.models import RegulatoryNoticeType
from app.db.models import RegulatorySource
from app.db.models import RegulatorySourceKind
from app.db.models import Store
from app.services import store_regulatory as svc


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "Reg-Svc") -> Store:
        store = Store(name=name, code=f"rs-{uuid.uuid4().hex[:8]}")
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
            store_id=store.id,
            variant_id=variant.id,
            quantity_on_hand=5,
        )
        db_session.add(item)
        db_session.commit()
        db_session.refresh(item)
        return item

    return _create


@pytest.fixture
def make_notice(db_session: Session) -> Callable[..., RegulatoryNotice]:
    def _create(title: str = "Notice") -> RegulatoryNotice:
        source = RegulatorySource(
            name=f"src-{uuid.uuid4().hex[:8]}",
            kind=RegulatorySourceKind.manual,
        )
        db_session.add(source)
        db_session.commit()
        db_session.refresh(source)
        notice = RegulatoryNotice(
            source_id=source.id,
            title=title,
            notice_type=RegulatoryNoticeType.advisory,
            payload={"items": []},
            content_hash=uuid.uuid4().hex,
        )
        db_session.add(notice)
        db_session.commit()
        db_session.refresh(notice)
        return notice

    return _create


@pytest.fixture
def make_alert(
    db_session: Session, make_notice
) -> Callable[..., ComplianceAlert]:
    def _create(
        *,
        product: Product | None,
        severity: ComplianceAlertSeverity = ComplianceAlertSeverity.high,
        status: ComplianceAlertStatus = ComplianceAlertStatus.open,
        recommended_action: ComplianceRecommendedAction = (
            ComplianceRecommendedAction.none
        ),
        notice: RegulatoryNotice | None = None,
    ) -> ComplianceAlert:
        nt = notice if notice is not None else make_notice()
        alert = ComplianceAlert(
            notice_id=nt.id,
            product_id=product.id if product is not None else None,
            severity=severity,
            status=status,
            recommended_action=recommended_action,
        )
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)
        return alert

    return _create


# --------------------------------------------------------------------- #
# Tenancy boundary
# --------------------------------------------------------------------- #


def test_store_sees_only_its_own_inventory_alerts(
    db_session, make_store, make_variant, make_item, make_alert
):
    store_a = make_store("A")
    variant = make_variant()
    make_item(store_a, variant)
    product = db_session.get(Product, variant.product_id)
    alert = make_alert(product=product)

    resp = svc.list_store_regulatory_alerts(db_session, store_id=store_a.id)

    assert resp.total == 1
    assert [a.id for a in resp.items] == [alert.id]
    assert resp.items[0].product_id == product.id


def test_store_b_does_not_see_store_a_alerts(
    db_session, make_store, make_variant, make_item, make_alert
):
    store_a = make_store("A")
    store_b = make_store("B")
    variant = make_variant()
    make_item(store_a, variant)
    product = db_session.get(Product, variant.product_id)
    make_alert(product=product)

    resp = svc.list_store_regulatory_alerts(db_session, store_id=store_b.id)

    assert resp.total == 0
    assert resp.items == []


def test_alert_for_product_not_in_inventory_is_hidden(
    db_session, make_store, make_variant, make_item, make_product, make_alert
):
    store = make_store()
    carried = make_variant()
    make_item(store, carried)
    # Alert for an unrelated product the store does not stock.
    other_product = make_product()
    make_alert(product=other_product)

    resp = svc.list_store_regulatory_alerts(db_session, store_id=store.id)

    assert resp.total == 0
    assert resp.items == []


def test_null_product_alert_is_hidden(
    db_session, make_store, make_variant, make_item, make_alert
):
    store = make_store()
    variant = make_variant()
    make_item(store, variant)
    # Notice-level alert (no product) must never surface to a store.
    make_alert(product=None)

    resp = svc.list_store_regulatory_alerts(db_session, store_id=store.id)

    assert resp.total == 0
    assert resp.items == []


def test_multiple_variants_of_same_product_do_not_duplicate(
    db_session, make_store, make_variant, make_item, make_alert
):
    store = make_store()
    product = None
    # Two variants of the SAME product, both stocked by the store.
    v1 = make_variant()
    product = db_session.get(Product, v1.product_id)
    v2 = make_variant(product=product)
    make_item(store, v1)
    make_item(store, v2)
    alert = make_alert(product=product)

    resp = svc.list_store_regulatory_alerts(db_session, store_id=store.id)

    assert resp.total == 1
    assert [a.id for a in resp.items] == [alert.id]


# --------------------------------------------------------------------- #
# Filters
# --------------------------------------------------------------------- #


def test_product_id_filter_within_boundary(
    db_session, make_store, make_variant, make_item, make_alert
):
    store = make_store()
    v1 = make_variant()
    v2 = make_variant()
    make_item(store, v1)
    make_item(store, v2)
    p1 = db_session.get(Product, v1.product_id)
    p2 = db_session.get(Product, v2.product_id)
    a1 = make_alert(product=p1)
    make_alert(product=p2)

    resp = svc.list_store_regulatory_alerts(
        db_session, store_id=store.id, product_id=p1.id
    )

    assert resp.total == 1
    assert [a.id for a in resp.items] == [a1.id]


def test_product_id_filter_outside_boundary_returns_empty(
    db_session, make_store, make_variant, make_item, make_product, make_alert
):
    store = make_store()
    carried = make_variant()
    make_item(store, carried)
    outside_product = make_product()
    make_alert(product=outside_product)

    resp = svc.list_store_regulatory_alerts(
        db_session, store_id=store.id, product_id=outside_product.id
    )

    assert resp.total == 0
    assert resp.items == []


def test_status_filter(
    db_session, make_store, make_variant, make_item, make_alert
):
    store = make_store()
    v1 = make_variant()
    v2 = make_variant()
    make_item(store, v1)
    make_item(store, v2)
    p1 = db_session.get(Product, v1.product_id)
    p2 = db_session.get(Product, v2.product_id)
    open_alert = make_alert(product=p1, status=ComplianceAlertStatus.open)
    make_alert(product=p2, status=ComplianceAlertStatus.dismissed)

    resp = svc.list_store_regulatory_alerts(
        db_session, store_id=store.id, status_filter=ComplianceAlertStatus.open
    )

    assert resp.total == 1
    assert [a.id for a in resp.items] == [open_alert.id]


def test_severity_filter(
    db_session, make_store, make_variant, make_item, make_alert
):
    store = make_store()
    v1 = make_variant()
    v2 = make_variant()
    make_item(store, v1)
    make_item(store, v2)
    p1 = db_session.get(Product, v1.product_id)
    p2 = db_session.get(Product, v2.product_id)
    critical = make_alert(
        product=p1, severity=ComplianceAlertSeverity.critical
    )
    make_alert(product=p2, severity=ComplianceAlertSeverity.low)

    resp = svc.list_store_regulatory_alerts(
        db_session,
        store_id=store.id,
        severity=ComplianceAlertSeverity.critical,
    )

    assert resp.total == 1
    assert [a.id for a in resp.items] == [critical.id]


def test_recommended_action_filter(
    db_session, make_store, make_variant, make_item, make_alert
):
    store = make_store()
    v1 = make_variant()
    v2 = make_variant()
    make_item(store, v1)
    make_item(store, v2)
    p1 = db_session.get(Product, v1.product_id)
    p2 = db_session.get(Product, v2.product_id)
    ban = make_alert(
        product=p1, recommended_action=ComplianceRecommendedAction.ban
    )
    make_alert(
        product=p2, recommended_action=ComplianceRecommendedAction.none
    )

    resp = svc.list_store_regulatory_alerts(
        db_session,
        store_id=store.id,
        recommended_action=ComplianceRecommendedAction.ban,
    )

    assert resp.total == 1
    assert [a.id for a in resp.items] == [ban.id]


def test_pagination_total_and_items_respect_boundary(
    db_session, make_store, make_variant, make_item, make_alert
):
    store = make_store()
    alerts = []
    for _ in range(3):
        v = make_variant()
        make_item(store, v)
        p = db_session.get(Product, v.product_id)
        alerts.append(make_alert(product=p))

    page = svc.list_store_regulatory_alerts(
        db_session, store_id=store.id, limit=2, offset=0
    )

    assert page.total == 3
    assert page.limit == 2
    assert page.offset == 0
    assert len(page.items) == 2

    page2 = svc.list_store_regulatory_alerts(
        db_session, store_id=store.id, limit=2, offset=2
    )
    assert page2.total == 3
    assert len(page2.items) == 1


# --------------------------------------------------------------------- #
# Detail
# --------------------------------------------------------------------- #


def test_detail_returns_alert_in_inventory(
    db_session, make_store, make_variant, make_item, make_alert
):
    store = make_store()
    variant = make_variant()
    make_item(store, variant)
    product = db_session.get(Product, variant.product_id)
    alert = make_alert(product=product)

    detail = svc.get_store_regulatory_alert_detail(
        db_session, store_id=store.id, alert_id=alert.id
    )

    assert detail is not None
    assert detail.id == alert.id
    assert detail.product_id == product.id
    assert detail.product_name == product.name


def test_detail_returns_none_outside_inventory(
    db_session, make_store, make_variant, make_item, make_product, make_alert
):
    store = make_store()
    carried = make_variant()
    make_item(store, carried)
    outside_product = make_product()
    alert = make_alert(product=outside_product)

    detail = svc.get_store_regulatory_alert_detail(
        db_session, store_id=store.id, alert_id=alert.id
    )

    assert detail is None


def test_detail_hides_null_product_alert(
    db_session, make_store, make_variant, make_item, make_alert
):
    store = make_store()
    variant = make_variant()
    make_item(store, variant)
    alert = make_alert(product=None)

    detail = svc.get_store_regulatory_alert_detail(
        db_session, store_id=store.id, alert_id=alert.id
    )

    assert detail is None


def test_store_alert_read_omits_admin_decision_fields(
    db_session, make_store, make_variant, make_item, make_alert
):
    store = make_store()
    variant = make_variant()
    make_item(store, variant)
    product = db_session.get(Product, variant.product_id)
    make_alert(product=product)

    resp = svc.list_store_regulatory_alerts(db_session, store_id=store.id)

    fields = set(resp.items[0].model_dump().keys())
    for forbidden in (
        "match_id",
        "resolution_note",
        "resolved_by_user_id",
        "resolved_at",
    ):
        assert forbidden not in fields
