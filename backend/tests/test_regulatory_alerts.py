"""Service tests for compliance alert generation from matches (F2.26.5.D).

Covers `create_compliance_alerts_from_matches`: alerts are created from a
notice's `RegulatoryProductMatch` rows with a deterministic severity +
recommended_action policy, start `open`, are idempotent across runs, and have
NO product / inventory / compliance-audit / decision-audit / operational-audit
side effects.

Style mirrors tests/test_regulatory_matching.py.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceAlert
from app.db.models import ComplianceAlertSeverity
from app.db.models import ComplianceAlertStatus
from app.db.models import ComplianceRecommendedAction
from app.db.models import ComplianceStatus
from app.db.models import Product
from app.db.models import ProductComplianceAuditLog
from app.db.models import ProductVariant
from app.db.models import RegulatoryDecisionAuditLog
from app.db.models import RegulatoryMatchStrategy
from app.db.models import RegulatoryNotice
from app.db.models import OperationalAuditLog
from app.schemas.regulatory import RegulatoryNoticeIngestRequest
from app.schemas.regulatory import RegulatorySourceCreate
from app.services import regulatory as svc


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create(
        *, name: str = "Example Vape", brand: str | None = "Example Brand",
        category: str = "ENDS",
    ) -> Product:
        product = Product(
            name=name,
            brand=brand,
            category=category,
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
            is_active=True,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        return product

    return _create


@pytest.fixture
def make_variant(db_session: Session) -> Callable[..., ProductVariant]:
    def _create(product: Product, **kw) -> ProductVariant:
        variant = ProductVariant(
            product_id=product.id,
            sku=kw.get("sku") or f"sku-{uuid.uuid4().hex[:8]}",
            barcode=kw.get("barcode"),
            flavor=kw.get("flavor"),
            price=Decimal("9.99"),
        )
        db_session.add(variant)
        db_session.commit()
        db_session.refresh(variant)
        return variant

    return _create


@pytest.fixture
def make_notice(db_session: Session) -> Callable[..., RegulatoryNotice]:
    def _create(payload: dict) -> RegulatoryNotice:
        source = svc.create_regulatory_source(
            db_session,
            RegulatorySourceCreate.model_validate(
                {"name": f"S {uuid.uuid4().hex[:8]}", "kind": "manual"}
            ),
        )
        read = svc.ingest_regulatory_notice(
            db_session,
            RegulatoryNoticeIngestRequest.model_validate(
                {
                    "source_id": source.id,
                    "title": "t",
                    "notice_type": "manual_snapshot",
                    "payload": payload,
                }
            ),
        )
        return db_session.get(RegulatoryNotice, read.id)

    return _create


def _matched_notice(
    make_product, make_notice, **payload
) -> RegulatoryNotice:
    """Create a product, a notice, and run matching so matches exist."""
    notice = make_notice(payload)
    return notice


# ===================================================================== #
# 1. Alert creation
# ===================================================================== #


def test_creates_alert_from_match(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    product = make_product(name="Example Vape", brand=None, category="c")
    notice = make_notice({"product_name": "Example Vape"})
    svc.detect_regulatory_product_matches(db_session, notice.id)

    alerts = svc.create_compliance_alerts_from_matches(db_session, notice.id)
    assert len(alerts) == 1
    a = alerts[0]
    assert a.notice_id == notice.id
    assert a.product_id == product.id
    assert a.match_id is not None
    assert a.status is ComplianceAlertStatus.open
    # name strategy -> high severity + hold recommendation.
    assert a.severity is ComplianceAlertSeverity.high
    assert a.recommended_action is ComplianceRecommendedAction.hold
    # Advisory: resolved fields stay null.
    assert a.resolved_at is None
    assert a.resolved_by_user_id is None


def test_no_matches_no_alerts(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    make_product(name="Something", brand=None, category="c")
    notice = make_notice({"product_name": "No Such Product"})
    svc.detect_regulatory_product_matches(db_session, notice.id)

    alerts = svc.create_compliance_alerts_from_matches(db_session, notice.id)
    assert alerts == []
    assert db_session.scalar(
        select(func.count()).select_from(ComplianceAlert)
    ) == 0


def test_invalid_notice_raises_404(db_session: Session):
    with pytest.raises(HTTPException) as exc:
        svc.create_compliance_alerts_from_matches(db_session, uuid.uuid4())
    assert exc.value.status_code == 404


@pytest.mark.parametrize(
    "strategy_payload,expected_severity,expected_action",
    [
        ({"barcode": "012345678905"}, ComplianceAlertSeverity.high, ComplianceRecommendedAction.hold),
        ({"sku": "SKU-9"}, ComplianceAlertSeverity.high, ComplianceRecommendedAction.hold),
        ({"product_name": "Policy Vape"}, ComplianceAlertSeverity.high, ComplianceRecommendedAction.hold),
        ({"brand": "Policy Brand"}, ComplianceAlertSeverity.medium, ComplianceRecommendedAction.none),
        ({"category": "PolicyCat"}, ComplianceAlertSeverity.low, ComplianceRecommendedAction.none),
        ({"flavor": "PolicyMint"}, ComplianceAlertSeverity.low, ComplianceRecommendedAction.none),
    ],
)
def test_severity_and_recommended_action_policy(
    make_product: Callable[..., Product],
    make_variant: Callable[..., ProductVariant],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
    strategy_payload: dict,
    expected_severity: ComplianceAlertSeverity,
    expected_action: ComplianceRecommendedAction,
):
    product = make_product(
        name="Policy Vape", brand="Policy Brand", category="PolicyCat"
    )
    make_variant(
        product, sku="SKU-9", barcode="012345678905", flavor="PolicyMint"
    )
    notice = make_notice(strategy_payload)
    svc.detect_regulatory_product_matches(db_session, notice.id)

    alerts = svc.create_compliance_alerts_from_matches(db_session, notice.id)
    assert len(alerts) == 1
    assert alerts[0].severity is expected_severity
    assert alerts[0].recommended_action is expected_action


def test_alert_generation_idempotent(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    make_product(name="Example Vape", brand=None, category="c")
    notice = make_notice({"product_name": "Example Vape"})
    svc.detect_regulatory_product_matches(db_session, notice.id)

    first = svc.create_compliance_alerts_from_matches(db_session, notice.id)
    second = svc.create_compliance_alerts_from_matches(db_session, notice.id)
    assert len(first) == 1
    assert len(second) == 1
    assert {a.id for a in first} == {a.id for a in second}
    assert db_session.scalar(
        select(func.count()).select_from(ComplianceAlert)
    ) == 1


def test_one_alert_per_match(
    make_product: Callable[..., Product],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    # name + brand + category all match the same product -> 3 matches -> 3
    # alerts, one per match/strategy.
    make_product(name="Example Vape", brand="Example Brand", category="ENDS")
    notice = make_notice(
        {
            "product_name": "Example Vape",
            "brand": "Example Brand",
            "category": "ENDS",
        }
    )
    svc.detect_regulatory_product_matches(db_session, notice.id)
    alerts = svc.create_compliance_alerts_from_matches(db_session, notice.id)
    assert len(alerts) == 3
    assert len({a.match_id for a in alerts}) == 3


# ===================================================================== #
# 2. No side effects on alert creation
# ===================================================================== #


def test_alert_creation_has_no_side_effects(
    make_product: Callable[..., Product],
    make_variant: Callable[..., ProductVariant],
    make_notice: Callable[..., RegulatoryNotice],
    db_session: Session,
):
    product = make_product(name="Example Vape", brand=None, category="c")
    variant = make_variant(product, sku="SKU-1")
    before = (
        product.compliance_status,
        product.allowed_for_sale,
        product.approval_status,
    )

    notice = make_notice({"product_name": "Example Vape", "sku": "SKU-1"})
    svc.detect_regulatory_product_matches(db_session, notice.id)
    svc.create_compliance_alerts_from_matches(db_session, notice.id)

    db_session.refresh(product)
    db_session.refresh(variant)
    # Product compliance / sellability / approval untouched.
    assert (
        product.compliance_status,
        product.allowed_for_sale,
        product.approval_status,
    ) == before
    # No product compliance audit log.
    assert db_session.scalar(
        select(func.count()).select_from(ProductComplianceAuditLog)
    ) == 0
    # No regulatory decision audit log.
    assert db_session.scalar(
        select(func.count()).select_from(RegulatoryDecisionAuditLog)
    ) == 0
    # No operational audit log targeting the product.
    assert db_session.scalar(
        select(func.count())
        .select_from(OperationalAuditLog)
        .where(OperationalAuditLog.target_id == product.id)
    ) == 0
