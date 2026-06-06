"""DB-level model + constraint tests for the regulatory foundation (F2.26.5.A).

Exercises the persisted regulatory data model against the real (migrated)
Postgres test database:
  - all five models insert and their FKs resolve;
  - source/content-hash dedupe uniqueness holds;
  - match confidence is bounded to [0, 1];
  - match FK to product + optional variant works;
  - a compliance alert references notice/product/match and may be
    unresolved or resolved (with the resolved-pair CHECK);
  - the decision audit log inserts and requires action/reason/actor;
  - source/notice deletion cascades as designed;
  - NO operational-audit product target is used (the dedicated
    regulatory_decision_audit_logs table is used instead).

Style mirrors tests/test_store_applications_model.py (local make_* helpers
over the transactional db_session, IntegrityError for DB constraints).
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from sqlalchemy import inspect
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import ComplianceAlert
from app.db.models import ComplianceAlertSeverity
from app.db.models import ComplianceAlertStatus
from app.db.models import ComplianceRecommendedAction
from app.db.models import ComplianceStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import RegulatoryDecisionAuditLog
from app.db.models import RegulatoryMatchStrategy
from app.db.models import RegulatoryNotice
from app.db.models import RegulatoryNoticeType
from app.db.models import RegulatoryProductMatch
from app.db.models import RegulatorySource
from app.db.models import RegulatorySourceKind
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import make_user as central_make_user


# --------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------- #


@pytest.fixture
def make_admin(db_session: Session) -> Callable[..., User]:
    def _create() -> User:
        return central_make_user(
            db_session,
            role=UserRole.admin,
            store_id=None,
            full_name="Reg Reviewer",
        )

    return _create


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create() -> Product:
        product = Product(
            name=f"Reg-{uuid.uuid4().hex[:6]}",
            category="vape",
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
def make_variant(
    db_session: Session, make_product: Callable[..., Product]
) -> Callable[..., ProductVariant]:
    def _create() -> ProductVariant:
        product = make_product()
        variant = ProductVariant(
            product_id=product.id,
            sku=f"sku-{uuid.uuid4().hex[:8]}",
            price=Decimal("9.99"),
        )
        db_session.add(variant)
        db_session.commit()
        db_session.refresh(variant)
        return variant

    return _create


def _make_source(db: Session, **overrides) -> RegulatorySource:
    data = dict(
        name=f"FDA PMTA {uuid.uuid4().hex[:8]}",
        kind=RegulatorySourceKind.fda_pmta,
    )
    data.update(overrides)
    source = RegulatorySource(**data)
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def _make_notice(db: Session, source_id: uuid.UUID, **overrides) -> RegulatoryNotice:
    data = dict(
        source_id=source_id,
        title="Authorized product list",
        notice_type=RegulatoryNoticeType.authorized_product_list,
        payload={"items": []},
        content_hash=uuid.uuid4().hex,
    )
    data.update(overrides)
    notice = RegulatoryNotice(**data)
    db.add(notice)
    db.commit()
    db.refresh(notice)
    return notice


# --------------------------------------------------------------------- #
# 1. Import surface + enum values
# --------------------------------------------------------------------- #


def test_models_and_enums_importable():
    assert RegulatorySource.__tablename__ == "regulatory_sources"
    assert RegulatoryNotice.__tablename__ == "regulatory_notices"
    assert (
        RegulatoryProductMatch.__tablename__ == "regulatory_product_matches"
    )
    assert ComplianceAlert.__tablename__ == "compliance_alerts"
    assert (
        RegulatoryDecisionAuditLog.__tablename__
        == "regulatory_decision_audit_logs"
    )

    assert [k.value for k in RegulatorySourceKind] == [
        "fda_pmta",
        "fda_enforcement",
        "fda_advisory",
        "retailer_guidance",
        "manual",
    ]
    assert [t.value for t in RegulatoryNoticeType] == [
        "authorized_product_list",
        "enforcement_notice",
        "advisory",
        "retailer_guidance",
        "manual_snapshot",
    ]
    assert [s.value for s in RegulatoryMatchStrategy] == [
        "name",
        "brand",
        "category",
        "sku",
        "barcode",
        "flavor",
        "manual",
    ]
    assert [s.value for s in ComplianceAlertSeverity] == [
        "low",
        "medium",
        "high",
        "critical",
    ]
    assert [s.value for s in ComplianceAlertStatus] == [
        "open",
        "acknowledged",
        "actioned",
        "dismissed",
    ]
    assert [a.value for a in ComplianceRecommendedAction] == [
        "none",
        "hold",
        "ban",
    ]


# --------------------------------------------------------------------- #
# 2. Source persistence + defaults + uniqueness
# --------------------------------------------------------------------- #


def test_source_persists_with_defaults(db_session: Session):
    source = _make_source(db_session)
    assert source.id is not None
    assert source.is_active is True
    assert source.last_synced_at is None
    assert source.created_at is not None
    assert source.updated_at is not None


def test_source_name_is_unique(db_session: Session):
    _make_source(db_session, name="Duplicate Source")
    with pytest.raises(IntegrityError):
        _make_source(db_session, name="Duplicate Source")


def test_source_name_must_be_non_empty(db_session: Session):
    source = RegulatorySource(name="", kind=RegulatorySourceKind.manual)
    db_session.add(source)
    with pytest.raises(IntegrityError):
        db_session.commit()


# --------------------------------------------------------------------- #
# 3. Notice persistence + FK + dedupe uniqueness
# --------------------------------------------------------------------- #


def test_notice_persists_and_links_source(db_session: Session):
    source = _make_source(db_session)
    notice = _make_notice(db_session, source.id)
    assert notice.id is not None
    assert notice.source_id == source.id
    assert notice.payload == {"items": []}
    assert notice.created_at is not None
    # Append-only: no updated_at attribute on the model.
    assert not hasattr(notice, "updated_at")


def test_notice_requires_valid_source(db_session: Session):
    notice = RegulatoryNotice(
        source_id=uuid.uuid4(),  # no such source
        title="x",
        notice_type=RegulatoryNoticeType.advisory,
        payload={},
        content_hash=uuid.uuid4().hex,
    )
    db_session.add(notice)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_notice_source_content_hash_dedupe(db_session: Session):
    source = _make_source(db_session)
    _make_notice(db_session, source.id, content_hash="hash-abc")
    with pytest.raises(IntegrityError):
        _make_notice(db_session, source.id, content_hash="hash-abc")


def test_notice_same_hash_different_source_is_allowed(db_session: Session):
    source_a = _make_source(db_session)
    source_b = _make_source(db_session)
    _make_notice(db_session, source_a.id, content_hash="shared-hash")
    # Same content_hash under a different source is fine — uniqueness is the
    # (source_id, content_hash) pair.
    notice_b = _make_notice(
        db_session, source_b.id, content_hash="shared-hash"
    )
    assert notice_b.id is not None


def test_notice_title_and_hash_non_empty(db_session: Session):
    source = _make_source(db_session)
    bad_title = RegulatoryNotice(
        source_id=source.id,
        title="",
        notice_type=RegulatoryNoticeType.advisory,
        payload={},
        content_hash=uuid.uuid4().hex,
    )
    db_session.add(bad_title)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()

    bad_hash = RegulatoryNotice(
        source_id=source.id,
        title="ok",
        notice_type=RegulatoryNoticeType.advisory,
        payload={},
        content_hash="",
    )
    db_session.add(bad_hash)
    with pytest.raises(IntegrityError):
        db_session.commit()


# --------------------------------------------------------------------- #
# 4. Product match: FK + confidence range + optional variant + dedupe
# --------------------------------------------------------------------- #


def test_match_persists_with_product_and_variant(
    db_session: Session,
    make_variant: Callable[..., ProductVariant],
):
    variant = make_variant()
    source = _make_source(db_session)
    notice = _make_notice(db_session, source.id)

    match = RegulatoryProductMatch(
        notice_id=notice.id,
        product_id=variant.product_id,
        variant_id=variant.id,
        match_strategy=RegulatoryMatchStrategy.sku,
        confidence=Decimal("0.87"),
        matched_fields={"sku": variant.sku},
    )
    db_session.add(match)
    db_session.commit()
    db_session.refresh(match)
    assert match.id is not None
    assert match.variant_id == variant.id
    assert match.confidence == Decimal("0.87")


def test_match_variant_is_optional(
    db_session: Session, make_product: Callable[..., Product]
):
    product = make_product()
    source = _make_source(db_session)
    notice = _make_notice(db_session, source.id)
    match = RegulatoryProductMatch(
        notice_id=notice.id,
        product_id=product.id,
        variant_id=None,
        match_strategy=RegulatoryMatchStrategy.name,
        confidence=Decimal("0.50"),
        matched_fields={"name": product.name},
    )
    db_session.add(match)
    db_session.commit()
    db_session.refresh(match)
    assert match.variant_id is None


@pytest.mark.parametrize("bad_confidence", [Decimal("1.50"), Decimal("-0.10")])
def test_match_confidence_out_of_range_rejected(
    db_session: Session,
    make_product: Callable[..., Product],
    bad_confidence: Decimal,
):
    product = make_product()
    source = _make_source(db_session)
    notice = _make_notice(db_session, source.id)
    match = RegulatoryProductMatch(
        notice_id=notice.id,
        product_id=product.id,
        match_strategy=RegulatoryMatchStrategy.brand,
        confidence=bad_confidence,
        matched_fields={},
    )
    db_session.add(match)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_match_boundary_confidences_allowed(
    db_session: Session, make_product: Callable[..., Product]
):
    product = make_product()
    source = _make_source(db_session)
    notice = _make_notice(db_session, source.id)
    for value, strategy in (
        (Decimal("0.00"), RegulatoryMatchStrategy.category),
        (Decimal("1.00"), RegulatoryMatchStrategy.manual),
    ):
        match = RegulatoryProductMatch(
            notice_id=notice.id,
            product_id=product.id,
            match_strategy=strategy,
            confidence=value,
            matched_fields={},
        )
        db_session.add(match)
        db_session.commit()
        db_session.refresh(match)
        assert match.confidence == value


def test_match_dedupe_uniqueness(
    db_session: Session, make_variant: Callable[..., ProductVariant]
):
    # Dedupe is keyed on (notice_id, product_id, variant_id, match_strategy).
    # Postgres treats NULLs as distinct in a unique constraint, so this guard
    # only deduplicates rows that carry a concrete variant_id; the test uses
    # one so the constraint actually fires.
    variant = make_variant()
    source = _make_source(db_session)
    notice = _make_notice(db_session, source.id)
    first = RegulatoryProductMatch(
        notice_id=notice.id,
        product_id=variant.product_id,
        variant_id=variant.id,
        match_strategy=RegulatoryMatchStrategy.barcode,
        confidence=Decimal("0.40"),
        matched_fields={},
    )
    db_session.add(first)
    db_session.commit()

    dupe = RegulatoryProductMatch(
        notice_id=notice.id,
        product_id=variant.product_id,
        variant_id=variant.id,
        match_strategy=RegulatoryMatchStrategy.barcode,
        confidence=Decimal("0.90"),
        matched_fields={},
    )
    db_session.add(dupe)
    with pytest.raises(IntegrityError):
        db_session.commit()


# --------------------------------------------------------------------- #
# 5. Compliance alert: references + unresolved/resolved + advisory action
# --------------------------------------------------------------------- #


def test_alert_persists_unresolved_with_defaults(
    db_session: Session, make_product: Callable[..., Product]
):
    product = make_product()
    source = _make_source(db_session)
    notice = _make_notice(db_session, source.id)
    match = RegulatoryProductMatch(
        notice_id=notice.id,
        product_id=product.id,
        match_strategy=RegulatoryMatchStrategy.name,
        confidence=Decimal("0.75"),
        matched_fields={},
    )
    db_session.add(match)
    db_session.commit()
    db_session.refresh(match)

    alert = ComplianceAlert(
        notice_id=notice.id,
        product_id=product.id,
        match_id=match.id,
        severity=ComplianceAlertSeverity.high,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    assert alert.id is not None
    assert alert.status is ComplianceAlertStatus.open  # server default
    # Advisory only — recommended_action defaults to 'none', no auto-mutation.
    assert alert.recommended_action is ComplianceRecommendedAction.none
    assert alert.resolved_at is None
    assert alert.resolved_by_user_id is None
    assert alert.created_at is not None
    assert alert.updated_at is not None


def test_alert_allows_null_product_and_match(db_session: Session):
    source = _make_source(db_session)
    notice = _make_notice(db_session, source.id)
    alert = ComplianceAlert(
        notice_id=notice.id,
        product_id=None,
        match_id=None,
        severity=ComplianceAlertSeverity.low,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    assert alert.product_id is None
    assert alert.match_id is None


def test_alert_can_be_resolved(
    db_session: Session,
    make_product: Callable[..., Product],
    make_admin: Callable[..., User],
):
    from datetime import UTC
    from datetime import datetime

    product = make_product()
    admin = make_admin()
    source = _make_source(db_session)
    notice = _make_notice(db_session, source.id)
    alert = ComplianceAlert(
        notice_id=notice.id,
        product_id=product.id,
        severity=ComplianceAlertSeverity.critical,
        status=ComplianceAlertStatus.actioned,
        recommended_action=ComplianceRecommendedAction.hold,
        resolution_note="placed product on review hold",
        resolved_by_user_id=admin.id,
        resolved_at=datetime.now(UTC),
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    assert alert.status is ComplianceAlertStatus.actioned
    assert alert.resolved_by_user_id == admin.id
    assert alert.resolved_at is not None


def test_alert_resolution_pair_must_be_consistent(
    db_session: Session,
    make_product: Callable[..., Product],
    make_admin: Callable[..., User],
):
    from datetime import UTC
    from datetime import datetime

    product = make_product()
    source = _make_source(db_session)
    notice = _make_notice(db_session, source.id)
    # resolved_at set but resolver NULL -> violates the pair CHECK.
    alert = ComplianceAlert(
        notice_id=notice.id,
        product_id=product.id,
        severity=ComplianceAlertSeverity.medium,
        resolved_at=datetime.now(UTC),
        resolved_by_user_id=None,
    )
    db_session.add(alert)
    with pytest.raises(IntegrityError):
        db_session.commit()


# --------------------------------------------------------------------- #
# 6. Regulatory decision audit log: insert + required fields + dedicated
# --------------------------------------------------------------------- #


def _make_alert(db: Session, product_id: uuid.UUID | None = None) -> ComplianceAlert:
    source = _make_source(db)
    notice = _make_notice(db, source.id)
    alert = ComplianceAlert(
        notice_id=notice.id,
        product_id=product_id,
        severity=ComplianceAlertSeverity.high,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def test_decision_audit_log_persists(
    db_session: Session,
    make_product: Callable[..., Product],
    make_admin: Callable[..., User],
):
    product = make_product()
    admin = make_admin()
    alert = _make_alert(db_session, product_id=product.id)

    log = RegulatoryDecisionAuditLog(
        alert_id=alert.id,
        notice_id=alert.notice_id,
        product_id=product.id,
        actor_user_id=admin.id,
        action="alert_resolved_hold",
        before={"status": "open"},
        after={"status": "actioned"},
        event_metadata={"reason_code": "pmta_not_authorized"},
        reason="product not on the authorized list",
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)

    assert log.id is not None
    assert log.actor_user_id == admin.id
    assert log.action == "alert_resolved_hold"
    assert log.before == {"status": "open"}
    assert log.after == {"status": "actioned"}
    assert log.event_metadata == {"reason_code": "pmta_not_authorized"}
    assert log.reason == "product not on the authorized list"
    assert log.created_at is not None
    # Append-only: no updated_at on the model.
    assert not hasattr(log, "updated_at")


def test_decision_audit_log_allows_null_product(
    db_session: Session, make_admin: Callable[..., User]
):
    admin = make_admin()
    alert = _make_alert(db_session, product_id=None)
    log = RegulatoryDecisionAuditLog(
        alert_id=alert.id,
        notice_id=alert.notice_id,
        product_id=None,
        actor_user_id=admin.id,
        action="alert_dismissed",
        reason="notice-level advisory, no single product",
    )
    db_session.add(log)
    db_session.commit()
    db_session.refresh(log)
    assert log.product_id is None


def test_decision_audit_log_requires_actor(
    db_session: Session, make_admin: Callable[..., User]
):
    alert = _make_alert(db_session)
    log = RegulatoryDecisionAuditLog(
        alert_id=alert.id,
        notice_id=alert.notice_id,
        actor_user_id=None,  # required
        action="alert_acknowledged",
        reason="seen",
    )
    db_session.add(log)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_decision_audit_log_requires_non_empty_action(
    db_session: Session, make_admin: Callable[..., User]
):
    admin = make_admin()
    alert = _make_alert(db_session)
    log = RegulatoryDecisionAuditLog(
        alert_id=alert.id,
        notice_id=alert.notice_id,
        actor_user_id=admin.id,
        action="",
        reason="seen",
    )
    db_session.add(log)
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_decision_audit_log_requires_non_empty_reason(
    db_session: Session, make_admin: Callable[..., User]
):
    admin = make_admin()
    alert = _make_alert(db_session)
    log = RegulatoryDecisionAuditLog(
        alert_id=alert.id,
        notice_id=alert.notice_id,
        actor_user_id=admin.id,
        action="alert_acknowledged",
        reason="",
    )
    db_session.add(log)
    with pytest.raises(IntegrityError):
        db_session.commit()


# --------------------------------------------------------------------- #
# 7. Deletion behavior: source/notice cascade through the chain
# --------------------------------------------------------------------- #


def test_deleting_source_cascades_to_notices_and_matches(
    db_session: Session, make_product: Callable[..., Product]
):
    product = make_product()
    source = _make_source(db_session)
    notice = _make_notice(db_session, source.id)
    match = RegulatoryProductMatch(
        notice_id=notice.id,
        product_id=product.id,
        match_strategy=RegulatoryMatchStrategy.name,
        confidence=Decimal("0.60"),
        matched_fields={},
    )
    db_session.add(match)
    db_session.commit()
    notice_id, match_id = notice.id, match.id

    # Delete via SQL DELETE so the DB-level ON DELETE CASCADE drives the
    # cascade (not the ORM relationship cascade).
    db_session.execute(
        RegulatorySource.__table__.delete().where(
            RegulatorySource.id == source.id
        )
    )
    db_session.commit()

    assert db_session.get(RegulatoryNotice, notice_id) is None
    assert db_session.get(RegulatoryProductMatch, match_id) is None


def test_deleting_notice_cascades_to_alerts_and_audit(
    db_session: Session,
    make_product: Callable[..., Product],
    make_admin: Callable[..., User],
):
    product = make_product()
    admin = make_admin()
    source = _make_source(db_session)
    notice = _make_notice(db_session, source.id)
    alert = ComplianceAlert(
        notice_id=notice.id,
        product_id=product.id,
        severity=ComplianceAlertSeverity.high,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    log = RegulatoryDecisionAuditLog(
        alert_id=alert.id,
        notice_id=notice.id,
        product_id=product.id,
        actor_user_id=admin.id,
        action="alert_acknowledged",
        reason="seen",
    )
    db_session.add(log)
    db_session.commit()
    alert_id, log_id = alert.id, log.id

    db_session.execute(
        RegulatoryNotice.__table__.delete().where(
            RegulatoryNotice.id == notice.id
        )
    )
    db_session.commit()

    assert db_session.get(ComplianceAlert, alert_id) is None
    assert db_session.get(RegulatoryDecisionAuditLog, log_id) is None


def test_deleting_product_sets_alert_product_null_but_keeps_alert(
    db_session: Session, make_product: Callable[..., Product]
):
    product = make_product()
    source = _make_source(db_session)
    notice = _make_notice(db_session, source.id)
    alert = ComplianceAlert(
        notice_id=notice.id,
        product_id=product.id,
        severity=ComplianceAlertSeverity.medium,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)
    alert_id = alert.id

    db_session.execute(
        Product.__table__.delete().where(Product.id == product.id)
    )
    db_session.commit()

    surviving = db_session.get(ComplianceAlert, alert_id)
    assert surviving is not None  # alert preserved
    assert surviving.product_id is None  # SET NULL


# --------------------------------------------------------------------- #
# 8. Scope guard: regulatory decisions are NOT routed through the
# operational audit table, and that table's taxonomy is untouched.
# --------------------------------------------------------------------- #


def test_regulatory_decisions_use_dedicated_table_not_operational(
    db_session: Session,
    make_product: Callable[..., Product],
    make_admin: Callable[..., User],
):
    from app.db.models import OperationalAuditLog

    product = make_product()
    admin = make_admin()
    alert = _make_alert(db_session, product_id=product.id)
    log = RegulatoryDecisionAuditLog(
        alert_id=alert.id,
        notice_id=alert.notice_id,
        product_id=product.id,
        actor_user_id=admin.id,
        action="alert_resolved_ban",
        reason="banned product",
    )
    db_session.add(log)
    db_session.commit()

    # The regulatory decision landed in its own table...
    assert (
        db_session.scalar(
            select(RegulatoryDecisionAuditLog).where(
                RegulatoryDecisionAuditLog.id == log.id
            )
        )
        is not None
    )
    # ...and left NO operational_audit_logs row targeting the product.
    assert (
        db_session.scalar(
            select(OperationalAuditLog).where(
                OperationalAuditLog.target_id == product.id
            )
        )
        is None
    )


def test_operational_audit_target_columns_unchanged(test_engine: Engine):
    # The operational audit table still carries only its generic
    # target_type/target_id columns — no product/regulatory-specific column
    # was added to it by this subphase.
    cols = {
        c["name"]
        for c in inspect(test_engine).get_columns("operational_audit_logs")
    }
    assert cols == {
        "id",
        "actor_user_id",
        "target_type",
        "target_id",
        "action",
        "store_id",
        "before",
        "after",
        "metadata",
        "created_at",
    }


# --------------------------------------------------------------------- #
# 9. Migration inspection — tables + key indexes exist
# --------------------------------------------------------------------- #


def test_regulatory_tables_exist(test_engine: Engine):
    tables = set(inspect(test_engine).get_table_names())
    assert {
        "regulatory_sources",
        "regulatory_notices",
        "regulatory_product_matches",
        "compliance_alerts",
        "regulatory_decision_audit_logs",
    } <= tables


def test_alert_indexes_exist(test_engine: Engine):
    names = {
        ix["name"]
        for ix in inspect(test_engine).get_indexes("compliance_alerts")
    }
    assert {
        "ix_compliance_alerts_status",
        "ix_compliance_alerts_created_at",
        "ix_compliance_alerts_product_id",
        "ix_compliance_alerts_notice_id",
    } <= names
