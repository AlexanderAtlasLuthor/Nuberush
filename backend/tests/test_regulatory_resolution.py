"""Service tests for the compliance alert lifecycle + resolution (F2.26.5.D).

Covers acknowledge / dismiss / resolve(no_action|hold|ban):
  - status transitions + resolved-field semantics;
  - every decision writes a `regulatory_decision_audit_logs` row with
    before/after + provenance metadata;
  - acknowledge / dismiss / no_action NEVER call `set_product_compliance()`;
  - hold / ban DELEGATE to `set_product_compliance()` (spied), producing a
    `product_compliance_audit_logs` row and the real Product state change,
    with ban preserving the existing inventory-quarantine cascade;
  - regulatory decisions never write `operational_audit_logs`;
  - invalid terminal transitions, missing actor, and blank reason fail clearly.
"""
from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Callable

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceAlertStatus
from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import InventoryStatus
from app.db.models import OperationalAuditLog
from app.db.models import Product
from app.db.models import ProductComplianceAuditLog
from app.db.models import ProductVariant
from app.db.models import RegulatoryDecisionAuditLog
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.regulatory import ComplianceAlertActionRequest
from app.schemas.regulatory import ComplianceAlertResolveRequest
from app.services import regulatory as svc
from tests.helpers.auth import make_user


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def admin(db_session: Session) -> User:
    return make_user(db_session, role=UserRole.admin)


@pytest.fixture
def make_product(db_session: Session) -> Callable[..., Product]:
    def _create(*, name: str = "Example Vape") -> Product:
        product = Product(
            name=name,
            brand=None,
            category="c",
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
def make_notice(db_session: Session) -> Callable[..., object]:
    from app.db.models import RegulatoryNotice
    from app.schemas.regulatory import RegulatoryNoticeIngestRequest
    from app.schemas.regulatory import RegulatorySourceCreate

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


@pytest.fixture
def spy_set_compliance(monkeypatch: pytest.MonkeyPatch) -> list:
    """Record calls to set_product_compliance while delegating to the real one."""
    calls: list = []
    real = svc.set_product_compliance

    def _wrapper(db, product_id, payload, *, actor):
        calls.append(
            {"product_id": product_id, "payload": payload, "actor": actor}
        )
        return real(db, product_id, payload, actor=actor)

    monkeypatch.setattr(svc, "set_product_compliance", _wrapper)
    return calls


def _open_alert(db: Session, make_product, make_notice, *, name="Example Vape"):
    """Build a product + name-matched notice and one open ('high'/'hold') alert."""
    product = make_product(name=name)
    notice = make_notice({"product_name": name})
    svc.detect_regulatory_product_matches(db, notice.id)
    alerts = svc.create_compliance_alerts_from_matches(db, notice.id)
    assert len(alerts) == 1
    return product, notice, alerts[0]


def _action(reason: str = "reviewed") -> ComplianceAlertActionRequest:
    return ComplianceAlertActionRequest.model_validate({"reason": reason})


def _resolve(action: str, note: str = "resolved") -> ComplianceAlertResolveRequest:
    return ComplianceAlertResolveRequest.model_validate(
        {"action": action, "resolution_note": note}
    )


def _decision(db: Session, alert_id, action: str) -> RegulatoryDecisionAuditLog | None:
    return db.scalar(
        select(RegulatoryDecisionAuditLog).where(
            RegulatoryDecisionAuditLog.alert_id == alert_id,
            RegulatoryDecisionAuditLog.action == action,
        )
    )


# ===================================================================== #
# 1. Acknowledge
# ===================================================================== #


def test_acknowledge(
    db_session, admin, make_product, make_notice, spy_set_compliance
):
    product, notice, alert = _open_alert(db_session, make_product, make_notice)

    read = svc.acknowledge_compliance_alert(
        db_session, alert.id, _action("looking into it"), actor_user_id=admin.id
    )
    assert read.status is ComplianceAlertStatus.acknowledged
    assert read.resolved_at is None
    assert read.resolved_by_user_id is None

    log = _decision(db_session, alert.id, "alert_acknowledged")
    assert log is not None
    assert log.notice_id == notice.id
    assert log.product_id == product.id
    assert log.actor_user_id == admin.id
    assert log.before["status"] == "open"
    assert log.after["status"] == "acknowledged"
    assert log.event_metadata["notice_id"] == str(notice.id)
    assert log.reason == "looking into it"

    # No product change, no compliance audit, no set_product_compliance call.
    assert spy_set_compliance == []
    assert db_session.scalar(
        select(func.count()).select_from(ProductComplianceAuditLog)
    ) == 0


# ===================================================================== #
# 2. Dismiss
# ===================================================================== #


def test_dismiss(
    db_session, admin, make_product, make_notice, spy_set_compliance
):
    product, notice, alert = _open_alert(db_session, make_product, make_notice)

    read = svc.dismiss_compliance_alert(
        db_session, alert.id, _action("not our product"), actor_user_id=admin.id
    )
    assert read.status is ComplianceAlertStatus.dismissed
    assert read.resolved_by_user_id == admin.id
    assert read.resolved_at is not None
    assert read.resolution_note == "not our product"

    log = _decision(db_session, alert.id, "alert_dismissed")
    assert log is not None
    assert log.after["status"] == "dismissed"
    assert log.after["resolved_by_user_id"] == str(admin.id)

    assert spy_set_compliance == []
    assert db_session.scalar(
        select(func.count()).select_from(ProductComplianceAuditLog)
    ) == 0


# ===================================================================== #
# 3. Resolve — no action
# ===================================================================== #


def test_resolve_no_action(
    db_session, admin, make_product, make_notice, spy_set_compliance
):
    product, notice, alert = _open_alert(db_session, make_product, make_notice)
    before_status = product.compliance_status

    read = svc.resolve_compliance_alert(
        db_session, alert.id, _resolve("no_action", "reviewed, fine"),
        actor_user_id=admin.id,
    )
    assert read.status is ComplianceAlertStatus.actioned
    assert read.resolved_by_user_id == admin.id
    assert read.resolution_note == "reviewed, fine"

    assert _decision(db_session, alert.id, "alert_resolved_no_action") is not None
    # No product mutation / delegation.
    assert spy_set_compliance == []
    db_session.refresh(product)
    assert product.compliance_status == before_status
    assert db_session.scalar(
        select(func.count()).select_from(ProductComplianceAuditLog)
    ) == 0


# ===================================================================== #
# 4. Resolve — hold (delegates to set_product_compliance)
# ===================================================================== #


def test_resolve_hold(
    db_session, admin, make_product, make_notice, spy_set_compliance
):
    product, notice, alert = _open_alert(db_session, make_product, make_notice)

    read = svc.resolve_compliance_alert(
        db_session, alert.id, _resolve("hold", "pending PMTA review"),
        actor_user_id=admin.id,
    )
    assert read.status is ComplianceAlertStatus.actioned

    # Delegated exactly once, to set_product_compliance.
    assert len(spy_set_compliance) == 1
    call = spy_set_compliance[0]
    assert call["product_id"] == product.id

    db_session.refresh(product)
    # Hold = restricted + not sellable (no permanent ban).
    assert product.compliance_status == ComplianceStatus.restricted
    assert product.allowed_for_sale is False

    # Real product compliance audit log produced by set_product_compliance,
    # carrying regulatory provenance in its reason.
    audit = db_session.scalar(
        select(ProductComplianceAuditLog).where(
            ProductComplianceAuditLog.product_id == product.id
        )
    )
    assert audit is not None
    assert str(alert.id) in audit.reason
    assert str(notice.id) in audit.reason

    # Decision audit recorded with the hold action.
    assert _decision(db_session, alert.id, "alert_resolved_hold") is not None


# ===================================================================== #
# 5. Resolve — ban (delegates + inventory quarantine cascade)
# ===================================================================== #


def test_resolve_ban_cascades_inventory(
    db_session, admin, make_product, make_notice, spy_set_compliance
):
    product, notice, alert = _open_alert(db_session, make_product, make_notice)

    # A variant + available inventory item so the ban cascade can quarantine.
    variant = ProductVariant(
        product_id=product.id, sku=f"sku-{uuid.uuid4().hex[:8]}",
        price=Decimal("5.00"),
    )
    db_session.add(variant)
    db_session.flush()
    store = Store(name="S", code=f"c-{uuid.uuid4().hex[:8]}")
    db_session.add(store)
    db_session.flush()
    item = InventoryItem(
        store_id=store.id, variant_id=variant.id,
        quantity_on_hand=10, status=InventoryStatus.available,
    )
    db_session.add(item)
    db_session.commit()
    item_id = item.id

    read = svc.resolve_compliance_alert(
        db_session, alert.id, _resolve("ban", "FDA enforcement"),
        actor_user_id=admin.id,
    )
    assert read.status is ComplianceAlertStatus.actioned
    assert len(spy_set_compliance) == 1

    db_session.refresh(product)
    assert product.compliance_status == ComplianceStatus.banned
    assert product.allowed_for_sale is False

    # Existing ban->quarantine cascade preserved.
    db_session.refresh(item := db_session.get(InventoryItem, item_id))
    assert item.status == InventoryStatus.quarantined

    assert _decision(db_session, alert.id, "alert_resolved_ban") is not None
    assert db_session.scalar(
        select(func.count()).select_from(ProductComplianceAuditLog)
    ) == 1


# ===================================================================== #
# 6. No operational audit for regulatory decisions
# ===================================================================== #


def test_decisions_never_write_operational_audit(
    db_session, admin, make_product, make_notice
):
    product, notice, alert = _open_alert(db_session, make_product, make_notice)
    svc.resolve_compliance_alert(
        db_session, alert.id, _resolve("hold", "x"), actor_user_id=admin.id
    )
    assert db_session.scalar(
        select(func.count())
        .select_from(OperationalAuditLog)
        .where(OperationalAuditLog.target_id.in_([product.id, notice.id, alert.id]))
    ) == 0


# ===================================================================== #
# 7. Invalid lifecycle transitions
# ===================================================================== #


def test_cannot_acknowledge_terminal_alert(
    db_session, admin, make_product, make_notice
):
    _, _, alert = _open_alert(db_session, make_product, make_notice)
    svc.dismiss_compliance_alert(
        db_session, alert.id, _action("done"), actor_user_id=admin.id
    )
    with pytest.raises(HTTPException) as exc:
        svc.acknowledge_compliance_alert(
            db_session, alert.id, _action("again"), actor_user_id=admin.id
        )
    assert exc.value.status_code == 422


def test_cannot_resolve_already_actioned(
    db_session, admin, make_product, make_notice
):
    _, _, alert = _open_alert(db_session, make_product, make_notice)
    svc.resolve_compliance_alert(
        db_session, alert.id, _resolve("no_action", "ok"), actor_user_id=admin.id
    )
    with pytest.raises(HTTPException) as exc:
        svc.resolve_compliance_alert(
            db_session, alert.id, _resolve("hold", "again"),
            actor_user_id=admin.id,
        )
    assert exc.value.status_code == 422


def test_cannot_dismiss_already_dismissed(
    db_session, admin, make_product, make_notice
):
    _, _, alert = _open_alert(db_session, make_product, make_notice)
    svc.dismiss_compliance_alert(
        db_session, alert.id, _action("done"), actor_user_id=admin.id
    )
    with pytest.raises(HTTPException) as exc:
        svc.dismiss_compliance_alert(
            db_session, alert.id, _action("again"), actor_user_id=admin.id
        )
    assert exc.value.status_code == 422


def test_acknowledge_then_resolve_is_allowed(
    db_session, admin, make_product, make_notice
):
    _, _, alert = _open_alert(db_session, make_product, make_notice)
    svc.acknowledge_compliance_alert(
        db_session, alert.id, _action("seen"), actor_user_id=admin.id
    )
    read = svc.resolve_compliance_alert(
        db_session, alert.id, _resolve("no_action", "fine"),
        actor_user_id=admin.id,
    )
    assert read.status is ComplianceAlertStatus.actioned


# ===================================================================== #
# 8. Actor + reason validation
# ===================================================================== #


def test_missing_actor_user_raises_404(
    db_session, make_product, make_notice
):
    _, _, alert = _open_alert(db_session, make_product, make_notice)
    with pytest.raises(HTTPException) as exc:
        svc.acknowledge_compliance_alert(
            db_session, alert.id, _action("x"), actor_user_id=uuid.uuid4()
        )
    assert exc.value.status_code == 404


def test_none_actor_user_raises_422(
    db_session, make_product, make_notice
):
    _, _, alert = _open_alert(db_session, make_product, make_notice)
    with pytest.raises(HTTPException) as exc:
        svc.acknowledge_compliance_alert(
            db_session, alert.id, _action("x"), actor_user_id=None
        )
    assert exc.value.status_code == 422


def test_blank_reason_rejected_by_schema():
    with pytest.raises(ValidationError):
        ComplianceAlertActionRequest.model_validate({"reason": "   "})
    with pytest.raises(ValidationError):
        ComplianceAlertResolveRequest.model_validate(
            {"action": "hold", "resolution_note": ""}
        )


def test_resolve_request_rejects_extra_field_and_bad_action():
    with pytest.raises(ValidationError):
        ComplianceAlertResolveRequest.model_validate(
            {"action": "hold", "resolution_note": "x", "surprise": 1}
        )
    with pytest.raises(ValidationError):
        ComplianceAlertResolveRequest.model_validate(
            {"action": "explode", "resolution_note": "x"}
        )


def test_hold_on_alert_without_product_raises_422(
    db_session, admin, make_notice
):
    # A notice-level alert with no product cannot apply a hold/ban.
    from app.db.models import ComplianceAlert
    from app.db.models import ComplianceAlertSeverity

    notice = make_notice({"note": "no product"})
    alert = ComplianceAlert(
        notice_id=notice.id,
        product_id=None,
        severity=ComplianceAlertSeverity.high,
    )
    db_session.add(alert)
    db_session.commit()
    db_session.refresh(alert)

    with pytest.raises(HTTPException) as exc:
        svc.resolve_compliance_alert(
            db_session, alert.id, _resolve("hold", "x"), actor_user_id=admin.id
        )
    assert exc.value.status_code == 422
