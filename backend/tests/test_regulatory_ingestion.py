"""Service tests for regulatory source + manual notice ingestion (F2.26.5.B).

Exercises `app.services.regulatory` against the real (migrated) Postgres test
database via the transactional `db_session`:
  - source create/list/get + duplicate-name + missing-lookup behavior;
  - the stable content hash (deterministic, order-insensitive, metadata- and
    payload-sensitive, fixed format);
  - notice ingestion: persistence, payload preservation, hash population,
    `(source_id, content_hash)` idempotent dedupe, same-content-different-
    source distinctness, and invalid-source failure;
  - the negative scope guard: ingestion creates NO matches / alerts / decision
    audit rows / operational-audit rows and mutates NO product.

Style mirrors tests/test_regulatory_models.py and the self-committing service
test pattern of tests/test_operational_audit.py.
"""
from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from decimal import Decimal
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceAlert
from app.db.models import ComplianceStatus
from app.db.models import OperationalAuditLog
from app.db.models import Product
from app.db.models import RegulatoryDecisionAuditLog
from app.db.models import RegulatoryNotice
from app.db.models import RegulatoryProductMatch
from app.schemas.regulatory import RegulatoryNoticeIngestRequest
from app.schemas.regulatory import RegulatorySourceCreate
from app.services import regulatory as svc


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #


def _source_payload(**overrides) -> RegulatorySourceCreate:
    data = dict(
        name=f"FDA PMTA {uuid.uuid4().hex[:8]}",
        kind="fda_pmta",
    )
    data.update(overrides)
    return RegulatorySourceCreate.model_validate(data)


def _ingest_payload(source_id: uuid.UUID, **overrides) -> RegulatoryNoticeIngestRequest:
    data = dict(
        source_id=source_id,
        title="Authorized product list",
        notice_type="authorized_product_list",
        payload={"items": [{"name": "X"}], "version": 1},
    )
    data.update(overrides)
    return RegulatoryNoticeIngestRequest.model_validate(data)


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


# ===================================================================== #
# 1. Regulatory source service
# ===================================================================== #


def test_create_source_defaults_active(db_session: Session):
    read = svc.create_regulatory_source(db_session, _source_payload())
    assert read.id is not None
    assert read.is_active is True
    assert read.last_synced_at is None


def test_create_source_inactive(db_session: Session):
    read = svc.create_regulatory_source(
        db_session, _source_payload(is_active=False)
    )
    assert read.is_active is False


def test_create_source_duplicate_name_raises_422(db_session: Session):
    payload = _source_payload(name="Duplicate Source")
    svc.create_regulatory_source(db_session, payload)
    with pytest.raises(HTTPException) as exc:
        svc.create_regulatory_source(
            db_session, _source_payload(name="Duplicate Source")
        )
    assert exc.value.status_code == 422
    # Session remains usable after the rollback.
    assert (
        svc.create_regulatory_source(db_session, _source_payload()).id
        is not None
    )


def test_get_source_returns_row(db_session: Session):
    created = svc.create_regulatory_source(db_session, _source_payload())
    fetched = svc.get_regulatory_source(db_session, created.id)
    assert fetched.id == created.id
    assert fetched.name == created.name


def test_get_source_missing_raises_404(db_session: Session):
    with pytest.raises(HTTPException) as exc:
        svc.get_regulatory_source(db_session, uuid.uuid4())
    assert exc.value.status_code == 404


def test_list_sources_returns_created(db_session: Session):
    a = svc.create_regulatory_source(db_session, _source_payload())
    b = svc.create_regulatory_source(db_session, _source_payload())
    resp = svc.list_regulatory_sources(db_session, limit=50)
    ids = {item.id for item in resp.items}
    assert {a.id, b.id} <= ids
    assert resp.total >= 2


def test_list_sources_filters_by_active(db_session: Session):
    active = svc.create_regulatory_source(db_session, _source_payload())
    inactive = svc.create_regulatory_source(
        db_session, _source_payload(is_active=False)
    )
    resp = svc.list_regulatory_sources(db_session, is_active=True, limit=100)
    ids = {item.id for item in resp.items}
    assert active.id in ids
    assert inactive.id not in ids


def test_list_sources_rejects_bad_pagination(db_session: Session):
    with pytest.raises(HTTPException) as exc:
        svc.list_regulatory_sources(db_session, limit=0)
    assert exc.value.status_code == 422
    with pytest.raises(HTTPException) as exc2:
        svc.list_regulatory_sources(db_session, offset=-1)
    assert exc2.value.status_code == 422


# ===================================================================== #
# 2. Stable content hash
# ===================================================================== #


def _hash(**overrides) -> str:
    data = dict(
        notice_type="advisory",
        title="t",
        external_ref=None,
        published_at=None,
        payload={"a": 1, "b": {"x": 1, "y": 2}},
    )
    data.update(overrides)
    return svc.compute_regulatory_notice_content_hash(**data)


def test_hash_is_deterministic():
    assert _hash() == _hash()


def test_hash_format_is_sha256_hex():
    value = _hash()
    assert len(value) == 64
    assert all(c in "0123456789abcdef" for c in value)


def test_hash_ignores_payload_key_order():
    a = _hash(payload={"a": 1, "b": {"x": 1, "y": 2}})
    b = _hash(payload={"b": {"y": 2, "x": 1}, "a": 1})
    assert a == b


def test_hash_changes_with_payload():
    assert _hash(payload={"a": 1}) != _hash(payload={"a": 2})


def test_hash_changes_with_metadata():
    base = _hash()
    assert _hash(title="other") != base
    assert _hash(notice_type="enforcement_notice") != base
    assert _hash(external_ref="FDA-1") != base
    assert _hash(published_at=datetime(2026, 1, 1, tzinfo=UTC)) != base


def test_hash_accepts_enum_or_string_notice_type():
    from app.db.models import RegulatoryNoticeType

    assert _hash(notice_type="advisory") == _hash(
        notice_type=RegulatoryNoticeType.advisory
    )


def test_hash_handles_non_json_native_leaf():
    # Decimal in payload must not raise (default=str fallback).
    value = svc.compute_regulatory_notice_content_hash(
        notice_type="advisory",
        title="t",
        external_ref=None,
        published_at=None,
        payload={"price": Decimal("9.99")},
    )
    assert len(value) == 64


# ===================================================================== #
# 3. Notice ingestion
# ===================================================================== #


def test_ingest_persists_notice_with_source_and_hash(db_session: Session):
    source = svc.create_regulatory_source(db_session, _source_payload())
    read = svc.ingest_regulatory_notice(
        db_session, _ingest_payload(source.id)
    )
    assert read.id is not None
    assert read.source_id == source.id
    assert read.content_hash and len(read.content_hash) == 64

    # Actually persisted (re-readable from the DB).
    row = db_session.get(RegulatoryNotice, read.id)
    assert row is not None
    assert row.source_id == source.id


def test_ingest_preserves_raw_payload(db_session: Session):
    source = svc.create_regulatory_source(db_session, _source_payload())
    payload = {"items": [{"name": "X", "nested": {"k": "v"}}], "version": 7}
    read = svc.ingest_regulatory_notice(
        db_session, _ingest_payload(source.id, payload=payload)
    )
    assert read.payload == payload
    assert db_session.get(RegulatoryNotice, read.id).payload == payload


def test_ingest_is_idempotent_on_duplicate(db_session: Session):
    source = svc.create_regulatory_source(db_session, _source_payload())
    first = svc.ingest_regulatory_notice(
        db_session, _ingest_payload(source.id)
    )
    # Re-ingest the SAME content (different key order in payload) -> reuse.
    second = svc.ingest_regulatory_notice(
        db_session,
        _ingest_payload(
            source.id, payload={"version": 1, "items": [{"name": "X"}]}
        ),
    )
    assert second.id == first.id

    count = db_session.scalar(
        select(func.count())
        .select_from(RegulatoryNotice)
        .where(RegulatoryNotice.source_id == source.id)
    )
    assert count == 1


def test_ingest_same_content_different_source_creates_two(
    db_session: Session,
):
    source_a = svc.create_regulatory_source(db_session, _source_payload())
    source_b = svc.create_regulatory_source(db_session, _source_payload())
    a = svc.ingest_regulatory_notice(db_session, _ingest_payload(source_a.id))
    b = svc.ingest_regulatory_notice(db_session, _ingest_payload(source_b.id))
    assert a.id != b.id
    # Same content hash (content identical), different source scope.
    assert a.content_hash == b.content_hash
    assert a.source_id != b.source_id


def test_ingest_different_content_creates_distinct_notices(
    db_session: Session,
):
    source = svc.create_regulatory_source(db_session, _source_payload())
    a = svc.ingest_regulatory_notice(
        db_session, _ingest_payload(source.id, payload={"v": 1})
    )
    b = svc.ingest_regulatory_notice(
        db_session, _ingest_payload(source.id, payload={"v": 2})
    )
    assert a.id != b.id
    assert a.content_hash != b.content_hash


def test_ingest_invalid_source_raises_404(db_session: Session):
    with pytest.raises(HTTPException) as exc:
        svc.ingest_regulatory_notice(
            db_session, _ingest_payload(uuid.uuid4())
        )
    assert exc.value.status_code == 404
    # Nothing was written.
    assert db_session.scalar(
        select(func.count()).select_from(RegulatoryNotice)
    ) == 0


# ===================================================================== #
# 4. No side effects — ingestion is pure persistence
# ===================================================================== #


def test_ingest_creates_no_matches_alerts_audit_or_product_mutation(
    db_session: Session, make_product: Callable[..., Product]
):
    product = make_product()
    before_status = product.compliance_status
    before_allowed = product.allowed_for_sale

    source = svc.create_regulatory_source(db_session, _source_payload())
    read = svc.ingest_regulatory_notice(
        db_session, _ingest_payload(source.id)
    )

    # No product matches.
    assert db_session.scalar(
        select(func.count()).select_from(RegulatoryProductMatch)
    ) == 0
    # No compliance alerts.
    assert db_session.scalar(
        select(func.count()).select_from(ComplianceAlert)
    ) == 0
    # No regulatory decision audit rows.
    assert db_session.scalar(
        select(func.count()).select_from(RegulatoryDecisionAuditLog)
    ) == 0
    # No operational audit row referencing the notice or the product.
    assert db_session.scalar(
        select(func.count())
        .select_from(OperationalAuditLog)
        .where(
            OperationalAuditLog.target_id.in_([read.id, product.id])
        )
    ) == 0
    # Product compliance/sellability untouched.
    db_session.refresh(product)
    assert product.compliance_status == before_status
    assert product.allowed_for_sale == before_allowed


def test_ingest_module_does_not_import_operational_audit_or_inventory():
    # The regulatory module legitimately imports match/alert/decision-audit
    # models and `set_product_compliance` (F2.26.5.C + .D). The enduring
    # file-level invariants are: never write the operational audit log, never
    # touch Inventory models directly (the ban→quarantine cascade is owned by
    # set_product_compliance, not this module), and never import
    # notification/email. Re-asserted by tests/test_regulatory_matching.py.
    import ast

    import app.services.regulatory as mod

    with open(mod.__file__, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    imported: list[str] = []
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.append(node.module)
            names.extend(alias.name for alias in node.names)

    forbidden_names = {
        "write_operational_audit_log",
        "OperationalAuditLog",
        "InventoryItem",
        "InventoryLog",
        "InventoryStatus",
    }
    assert forbidden_names.isdisjoint(set(names)), (
        f"unexpected import: {forbidden_names & set(names)}"
    )
    assert "app.services.operational_audit" not in imported
    assert not any("notification" in m or "email" in m for m in imported)
