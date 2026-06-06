"""Schema-only tests for the regulatory foundation (F2.26.5.A).

No DB. Exercises:
  - the enum surface re-exported from app.db.models plus the schema-local
    RegulatoryDecisionAction;
  - Create schemas reject extra fields, validate required non-empty strings,
    and accept JSON payload structures;
  - Read schemas hydrate from ORM-like objects via `from_attributes`;
  - confidence range validation;
  - enum validation (valid hydrates, invalid raises);
  - the decision-audit `metadata` field hydrates from the ORM
    `event_metadata` attribute.

Style mirrors tests/test_store_applications_schemas.py.
"""
from __future__ import annotations

from datetime import UTC
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.db.models import ComplianceAlertSeverity as ModelSeverity
from app.db.models import RegulatorySourceKind as ModelSourceKind
from app.schemas.regulatory import ComplianceAlertRead
from app.schemas.regulatory import ComplianceAlertSeverity
from app.schemas.regulatory import ComplianceAlertStatus
from app.schemas.regulatory import ComplianceRecommendedAction
from app.schemas.regulatory import RegulatoryDecisionAction
from app.schemas.regulatory import RegulatoryDecisionAuditLogRead
from app.schemas.regulatory import RegulatoryNoticeCreate
from app.schemas.regulatory import RegulatoryNoticeRead
from app.schemas.regulatory import RegulatoryNoticeType
from app.schemas.regulatory import RegulatoryProductMatchCreate
from app.schemas.regulatory import RegulatoryProductMatchRead
from app.schemas.regulatory import RegulatorySourceCreate
from app.schemas.regulatory import RegulatorySourceKind
from app.schemas.regulatory import RegulatorySourceRead


# --------------------------------------------------------------------- #
# Enum surface
# --------------------------------------------------------------------- #


def test_enums_are_the_model_enums():
    # The schema layer re-exports the ORM enums: same object, not a copy.
    assert RegulatorySourceKind is ModelSourceKind
    assert ComplianceAlertSeverity is ModelSeverity


def test_decision_action_values():
    assert [a.value for a in RegulatoryDecisionAction] == [
        "alert_acknowledged",
        "alert_dismissed",
        "alert_resolved_hold",
        "alert_resolved_ban",
        "alert_resolved_no_action",
    ]


# --------------------------------------------------------------------- #
# RegulatorySourceCreate
# --------------------------------------------------------------------- #


def test_source_create_accepts_valid():
    model = RegulatorySourceCreate.model_validate(
        {"name": "FDA PMTA", "kind": "fda_pmta"}
    )
    assert model.name == "FDA PMTA"
    assert model.kind is RegulatorySourceKind.fda_pmta
    assert model.is_active is True  # default
    assert model.reference_url is None


def test_source_create_rejects_extra_field():
    with pytest.raises(ValidationError):
        RegulatorySourceCreate.model_validate(
            {"name": "X", "kind": "manual", "surprise": 1}
        )


def test_source_create_rejects_blank_name():
    with pytest.raises(ValidationError):
        RegulatorySourceCreate.model_validate(
            {"name": "   ", "kind": "manual"}
        )


def test_source_create_trims_name():
    model = RegulatorySourceCreate.model_validate(
        {"name": "  Retailer Guidance  ", "kind": "retailer_guidance"}
    )
    assert model.name == "Retailer Guidance"


def test_source_create_rejects_invalid_kind():
    with pytest.raises(ValidationError):
        RegulatorySourceCreate.model_validate(
            {"name": "X", "kind": "not_a_kind"}
        )


def test_source_read_hydrates_from_orm_like():
    now = datetime.now(UTC)
    ns = SimpleNamespace(
        id=uuid4(),
        name="FDA Enforcement",
        kind=ModelSourceKind.fda_enforcement,
        reference_url=None,
        is_active=True,
        last_synced_at=None,
        created_at=now,
        updated_at=now,
    )
    read = RegulatorySourceRead.model_validate(ns)
    assert read.name == "FDA Enforcement"
    assert read.kind is RegulatorySourceKind.fda_enforcement
    assert read.created_at == now


# --------------------------------------------------------------------- #
# RegulatoryNoticeCreate / Read
# --------------------------------------------------------------------- #


def _notice_create_kwargs(**overrides) -> dict:
    data = dict(
        source_id=uuid4(),
        title="Authorized product list",
        notice_type="authorized_product_list",
        payload={"items": [{"name": "X"}]},
        content_hash="abc123",
    )
    data.update(overrides)
    return data


def test_notice_create_accepts_valid_with_json_payload():
    model = RegulatoryNoticeCreate.model_validate(_notice_create_kwargs())
    assert model.notice_type is RegulatoryNoticeType.authorized_product_list
    assert model.payload == {"items": [{"name": "X"}]}
    assert model.published_at is None


def test_notice_create_defaults_empty_payload():
    kwargs = _notice_create_kwargs()
    kwargs.pop("payload")
    model = RegulatoryNoticeCreate.model_validate(kwargs)
    assert model.payload == {}


def test_notice_create_rejects_extra_field():
    with pytest.raises(ValidationError):
        RegulatoryNoticeCreate.model_validate(
            _notice_create_kwargs(extra="nope")
        )


def test_notice_create_rejects_blank_title():
    with pytest.raises(ValidationError):
        RegulatoryNoticeCreate.model_validate(
            _notice_create_kwargs(title="   ")
        )


def test_notice_create_rejects_blank_content_hash():
    with pytest.raises(ValidationError):
        RegulatoryNoticeCreate.model_validate(
            _notice_create_kwargs(content_hash="")
        )


def test_notice_create_rejects_invalid_notice_type():
    with pytest.raises(ValidationError):
        RegulatoryNoticeCreate.model_validate(
            _notice_create_kwargs(notice_type="bogus")
        )


def test_notice_read_hydrates_from_orm_like():
    now = datetime.now(UTC)
    ns = SimpleNamespace(
        id=uuid4(),
        source_id=uuid4(),
        external_ref="FDA-2026-001",
        title="Enforcement notice",
        notice_type=RegulatoryNoticeType.enforcement_notice,
        published_at=now,
        payload={"k": "v"},
        content_hash="deadbeef",
        created_at=now,
    )
    read = RegulatoryNoticeRead.model_validate(ns)
    assert read.external_ref == "FDA-2026-001"
    assert read.notice_type is RegulatoryNoticeType.enforcement_notice
    assert read.payload == {"k": "v"}


# --------------------------------------------------------------------- #
# RegulatoryProductMatch — confidence validation
# --------------------------------------------------------------------- #


def _match_create_kwargs(**overrides) -> dict:
    data = dict(
        notice_id=uuid4(),
        product_id=uuid4(),
        match_strategy="sku",
        confidence=Decimal("0.80"),
        matched_fields={"sku": "abc"},
    )
    data.update(overrides)
    return data


def test_match_create_accepts_valid():
    model = RegulatoryProductMatchCreate.model_validate(
        _match_create_kwargs()
    )
    assert model.confidence == Decimal("0.80")
    assert model.variant_id is None
    assert model.matched_fields == {"sku": "abc"}


@pytest.mark.parametrize("bad", [Decimal("1.50"), Decimal("-0.01")])
def test_match_create_rejects_confidence_out_of_range(bad: Decimal):
    with pytest.raises(ValidationError):
        RegulatoryProductMatchCreate.model_validate(
            _match_create_kwargs(confidence=bad)
        )


@pytest.mark.parametrize("good", [Decimal("0.00"), Decimal("1.00")])
def test_match_create_accepts_boundary_confidence(good: Decimal):
    model = RegulatoryProductMatchCreate.model_validate(
        _match_create_kwargs(confidence=good)
    )
    assert model.confidence == good


def test_match_create_rejects_extra_field():
    with pytest.raises(ValidationError):
        RegulatoryProductMatchCreate.model_validate(
            _match_create_kwargs(surprise=1)
        )


def test_match_read_hydrates_from_orm_like():
    now = datetime.now(UTC)
    ns = SimpleNamespace(
        id=uuid4(),
        notice_id=uuid4(),
        product_id=uuid4(),
        variant_id=None,
        match_strategy="brand",
        confidence=Decimal("0.33"),
        matched_fields={"brand": "Acme"},
        created_at=now,
    )
    read = RegulatoryProductMatchRead.model_validate(ns)
    assert read.confidence == Decimal("0.33")
    assert read.matched_fields == {"brand": "Acme"}


# --------------------------------------------------------------------- #
# ComplianceAlertRead
# --------------------------------------------------------------------- #


def test_alert_read_hydrates_unresolved():
    now = datetime.now(UTC)
    ns = SimpleNamespace(
        id=uuid4(),
        notice_id=uuid4(),
        product_id=uuid4(),
        match_id=None,
        severity=ComplianceAlertSeverity.high,
        status=ComplianceAlertStatus.open,
        recommended_action=ComplianceRecommendedAction.none,
        resolution_note=None,
        resolved_by_user_id=None,
        resolved_at=None,
        created_at=now,
        updated_at=now,
    )
    read = ComplianceAlertRead.model_validate(ns)
    assert read.severity is ComplianceAlertSeverity.high
    assert read.status is ComplianceAlertStatus.open
    assert read.recommended_action is ComplianceRecommendedAction.none
    assert read.resolved_at is None


def test_alert_read_hydrates_resolved():
    now = datetime.now(UTC)
    ns = SimpleNamespace(
        id=uuid4(),
        notice_id=uuid4(),
        product_id=uuid4(),
        match_id=uuid4(),
        severity=ComplianceAlertSeverity.critical,
        status=ComplianceAlertStatus.actioned,
        recommended_action=ComplianceRecommendedAction.hold,
        resolution_note="held for review",
        resolved_by_user_id=uuid4(),
        resolved_at=now,
        created_at=now,
        updated_at=now,
    )
    read = ComplianceAlertRead.model_validate(ns)
    assert read.status is ComplianceAlertStatus.actioned
    assert read.recommended_action is ComplianceRecommendedAction.hold
    assert read.resolved_at == now


# --------------------------------------------------------------------- #
# RegulatoryDecisionAuditLogRead — action enum + metadata alias
# --------------------------------------------------------------------- #


def test_decision_audit_read_hydrates_from_orm_event_metadata():
    now = datetime.now(UTC)
    # ORM attribute is `event_metadata` (column name is `metadata`).
    ns = SimpleNamespace(
        id=uuid4(),
        alert_id=uuid4(),
        notice_id=uuid4(),
        product_id=uuid4(),
        actor_user_id=uuid4(),
        action="alert_resolved_hold",
        before={"status": "open"},
        after={"status": "actioned"},
        event_metadata={"reason_code": "pmta"},
        reason="not authorized",
        created_at=now,
    )
    read = RegulatoryDecisionAuditLogRead.model_validate(ns)
    assert read.action is RegulatoryDecisionAction.alert_resolved_hold
    assert read.metadata == {"reason_code": "pmta"}
    assert read.before == {"status": "open"}
    assert read.reason == "not authorized"


def test_decision_audit_read_accepts_metadata_key_by_name():
    now = datetime.now(UTC)
    data = {
        "id": uuid4(),
        "alert_id": uuid4(),
        "notice_id": uuid4(),
        "product_id": None,
        "actor_user_id": uuid4(),
        "action": "alert_dismissed",
        "before": None,
        "after": None,
        "metadata": {"note": "n/a"},
        "reason": "dismissed",
        "created_at": now,
    }
    read = RegulatoryDecisionAuditLogRead.model_validate(data)
    assert read.metadata == {"note": "n/a"}
    assert read.product_id is None


def test_decision_audit_read_rejects_invalid_action():
    now = datetime.now(UTC)
    ns = SimpleNamespace(
        id=uuid4(),
        alert_id=uuid4(),
        notice_id=uuid4(),
        product_id=None,
        actor_user_id=uuid4(),
        action="alert_frobnicated",  # not in the closed set
        before=None,
        after=None,
        event_metadata=None,
        reason="x",
        created_at=now,
    )
    with pytest.raises(ValidationError):
        RegulatoryDecisionAuditLogRead.model_validate(ns)
