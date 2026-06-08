"""Service tests for the compliance-alert aggregate (F2.27.5).

Covers `app.services.regulatory.aggregate_compliance_alerts`: dense-by-enum
global counts over `compliance_alerts`, computed server-side before any
pagination. Verifies the empty state, mixed counts, dense zero-fill of every
enum member, that each filter dimension is respected (reusing the same
`_compliance_alert_filters` the list endpoint uses), and that list pagination
does not affect the aggregate.

Alerts are inserted directly via the ORM with chosen enum values so the test
controls the exact distribution — it does NOT exercise matching/alert-creation
(those have their own suites) and never touches lifecycle behavior.

Style mirrors tests/test_regulatory_alerts.py.
"""
from __future__ import annotations

import uuid
from typing import Callable

import pytest
from sqlalchemy.orm import Session

from app.db.models import ComplianceAlert
from app.db.models import ComplianceAlertSeverity
from app.db.models import ComplianceAlertStatus
from app.db.models import ComplianceRecommendedAction
from app.db.models import ComplianceStatus
from app.db.models import Product
from app.db.models import RegulatoryNotice
from app.schemas.regulatory import RegulatoryNoticeIngestRequest
from app.schemas.regulatory import RegulatorySourceCreate
from app.services import regulatory as svc


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create(*, name: str = "Agg Vape") -> Product:
        product = Product(
            name=name,
            brand=None,
            category="ENDS",
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
def notice(db_session: Session) -> RegulatoryNotice:
    """A single persisted notice to satisfy ComplianceAlert.notice_id (NOT NULL)."""
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
                "payload": {},
            }
        ),
    )
    return db_session.get(RegulatoryNotice, read.id)


@pytest.fixture
def make_alert(
    db_session: Session, notice: RegulatoryNotice
) -> Callable[..., ComplianceAlert]:
    def _create(
        *,
        status: ComplianceAlertStatus = ComplianceAlertStatus.open,
        severity: ComplianceAlertSeverity = ComplianceAlertSeverity.low,
        recommended_action: ComplianceRecommendedAction = (
            ComplianceRecommendedAction.none
        ),
        product_id: uuid.UUID | None = None,
        notice_override: RegulatoryNotice | None = None,
    ) -> ComplianceAlert:
        alert = ComplianceAlert(
            notice_id=(notice_override or notice).id,
            product_id=product_id,
            match_id=None,
            severity=severity,
            status=status,
            recommended_action=recommended_action,
        )
        db_session.add(alert)
        db_session.commit()
        db_session.refresh(alert)
        return alert

    return _create


# ===================================================================== #
# 1. Empty state — dense zero-fill of every enum member
# ===================================================================== #


def test_empty_state_is_dense_and_zero(db_session: Session):
    agg = svc.aggregate_compliance_alerts(db_session)

    assert agg.total == 0
    assert set(agg.by_status.keys()) == set(ComplianceAlertStatus)
    assert set(agg.by_severity.keys()) == set(ComplianceAlertSeverity)
    assert set(agg.by_recommended_action.keys()) == set(
        ComplianceRecommendedAction
    )
    assert all(v == 0 for v in agg.by_status.values())
    assert all(v == 0 for v in agg.by_severity.values())
    assert all(v == 0 for v in agg.by_recommended_action.values())


# ===================================================================== #
# 2. Mixed counts
# ===================================================================== #


def test_mixed_counts_exact(
    db_session: Session, make_alert: Callable[..., ComplianceAlert]
):
    # 2 open, 1 acknowledged, 1 dismissed.
    make_alert(
        status=ComplianceAlertStatus.open,
        severity=ComplianceAlertSeverity.high,
        recommended_action=ComplianceRecommendedAction.hold,
    )
    make_alert(
        status=ComplianceAlertStatus.open,
        severity=ComplianceAlertSeverity.critical,
        recommended_action=ComplianceRecommendedAction.ban,
    )
    make_alert(
        status=ComplianceAlertStatus.acknowledged,
        severity=ComplianceAlertSeverity.medium,
        recommended_action=ComplianceRecommendedAction.none,
    )
    make_alert(
        status=ComplianceAlertStatus.dismissed,
        severity=ComplianceAlertSeverity.low,
        recommended_action=ComplianceRecommendedAction.none,
    )

    agg = svc.aggregate_compliance_alerts(db_session)

    assert agg.total == 4
    assert agg.by_status[ComplianceAlertStatus.open] == 2
    assert agg.by_status[ComplianceAlertStatus.acknowledged] == 1
    assert agg.by_status[ComplianceAlertStatus.dismissed] == 1
    assert agg.by_status[ComplianceAlertStatus.actioned] == 0

    assert agg.by_severity[ComplianceAlertSeverity.high] == 1
    assert agg.by_severity[ComplianceAlertSeverity.critical] == 1
    assert agg.by_severity[ComplianceAlertSeverity.medium] == 1
    assert agg.by_severity[ComplianceAlertSeverity.low] == 1

    assert agg.by_recommended_action[ComplianceRecommendedAction.hold] == 1
    assert agg.by_recommended_action[ComplianceRecommendedAction.ban] == 1
    assert agg.by_recommended_action[ComplianceRecommendedAction.none] == 2


# ===================================================================== #
# 3. Dense zero-fill with data present (missing values still appear)
# ===================================================================== #


def test_dense_zero_fill_with_partial_data(
    db_session: Session, make_alert: Callable[..., ComplianceAlert]
):
    # Only `open` / `low` / `none` are present; every other enum member must
    # still appear with count 0.
    make_alert(
        status=ComplianceAlertStatus.open,
        severity=ComplianceAlertSeverity.low,
        recommended_action=ComplianceRecommendedAction.none,
    )

    agg = svc.aggregate_compliance_alerts(db_session)

    assert set(agg.by_status.keys()) == set(ComplianceAlertStatus)
    assert agg.by_status[ComplianceAlertStatus.acknowledged] == 0
    assert agg.by_status[ComplianceAlertStatus.actioned] == 0
    assert agg.by_severity[ComplianceAlertSeverity.critical] == 0
    assert agg.by_recommended_action[ComplianceRecommendedAction.ban] == 0
    assert agg.total == 1


# ===================================================================== #
# 4. Filters respected (same surface as list_compliance_alerts)
# ===================================================================== #


def test_status_filter_respected(
    db_session: Session, make_alert: Callable[..., ComplianceAlert]
):
    make_alert(status=ComplianceAlertStatus.open)
    make_alert(status=ComplianceAlertStatus.open)
    make_alert(status=ComplianceAlertStatus.dismissed)

    agg = svc.aggregate_compliance_alerts(
        db_session, status_filter=ComplianceAlertStatus.open
    )
    assert agg.total == 2
    assert agg.by_status[ComplianceAlertStatus.open] == 2
    assert agg.by_status[ComplianceAlertStatus.dismissed] == 0


def test_severity_filter_respected(
    db_session: Session, make_alert: Callable[..., ComplianceAlert]
):
    make_alert(severity=ComplianceAlertSeverity.high)
    make_alert(severity=ComplianceAlertSeverity.low)

    agg = svc.aggregate_compliance_alerts(
        db_session, severity=ComplianceAlertSeverity.high
    )
    assert agg.total == 1
    assert agg.by_severity[ComplianceAlertSeverity.high] == 1
    assert agg.by_severity[ComplianceAlertSeverity.low] == 0


def test_recommended_action_filter_respected(
    db_session: Session, make_alert: Callable[..., ComplianceAlert]
):
    make_alert(recommended_action=ComplianceRecommendedAction.hold)
    make_alert(recommended_action=ComplianceRecommendedAction.ban)
    make_alert(recommended_action=ComplianceRecommendedAction.none)

    agg = svc.aggregate_compliance_alerts(
        db_session, recommended_action=ComplianceRecommendedAction.hold
    )
    assert agg.total == 1
    assert agg.by_recommended_action[ComplianceRecommendedAction.hold] == 1
    assert agg.by_recommended_action[ComplianceRecommendedAction.ban] == 0


def test_product_id_filter_respected(
    db_session: Session,
    make_alert: Callable[..., ComplianceAlert],
    make_product: Callable[..., Product],
):
    target = make_product(name="Target")
    other = make_product(name="Other")
    make_alert(product_id=target.id)
    make_alert(product_id=other.id)
    make_alert(product_id=None)

    agg = svc.aggregate_compliance_alerts(db_session, product_id=target.id)
    assert agg.total == 1


def test_notice_id_filter_respected(
    db_session: Session,
    notice: RegulatoryNotice,
    make_alert: Callable[..., ComplianceAlert],
):
    # A second notice to scope against.
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
                "title": "t2",
                "notice_type": "manual_snapshot",
                "payload": {"x": 1},
            }
        ),
    )
    other_notice = db_session.get(RegulatoryNotice, read.id)

    make_alert()  # default notice
    make_alert()  # default notice
    make_alert(notice_override=other_notice)

    agg = svc.aggregate_compliance_alerts(db_session, notice_id=notice.id)
    assert agg.total == 2


# ===================================================================== #
# 5. Pagination independence
# ===================================================================== #


def test_pagination_does_not_affect_aggregate(
    db_session: Session, make_alert: Callable[..., ComplianceAlert]
):
    for _ in range(7):
        make_alert(status=ComplianceAlertStatus.open)

    # The list is bounded by limit; the aggregate must count ALL rows.
    page = svc.list_compliance_alerts(db_session, limit=2, offset=0)
    assert len(page.items) == 2

    agg = svc.aggregate_compliance_alerts(db_session)
    assert agg.total == 7
    assert agg.by_status[ComplianceAlertStatus.open] == 7
