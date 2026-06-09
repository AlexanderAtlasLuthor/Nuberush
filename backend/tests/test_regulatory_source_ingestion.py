"""Service tests for the regulatory ingestion orchestrator (F2.27.7.C).

Drives `run_regulatory_source_ingestion` with an INJECTED in-memory client
(`StaticRegulatorySourceClient`) — no network, no credentials. Verifies the
run/item ledger, counters, source bookkeeping, created-vs-deduped, failure /
partial handling, and that the orchestrator feeds the EXISTING advisory
pipeline WITHOUT mutating a product, inventory, an alert lifecycle, or any
audit table. A static guard asserts the orchestrator never references the
forbidden compliance/lifecycle/audit symbols.
"""
from __future__ import annotations

import pathlib
import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Callable

import pytest
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceAlert
from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import OperationalAuditLog
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import RegulatoryDecisionAuditLog
from app.db.models import RegulatoryIngestionItem
from app.db.models import RegulatoryIngestionRun
from app.db.models import RegulatoryNotice
from app.db.models import RegulatorySource
from app.db.models import RegulatorySourceKind
from app.db.models import Store
from app.services import regulatory_ingestion as svc
from app.services.regulatory_sources import StaticRegulatorySourceClient


# --------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------- #


def _raw_item(**over: Any) -> dict[str, Any]:
    """A minimal valid FDA-shaped raw item (parser-compatible)."""
    item = {
        "document_number": f"FDA-{uuid.uuid4().hex[:10]}",
        "document_type": "enforcement_notice",
        "title": "FDA enforcement notice",
        "publication_date": "2024-09-15",
        "url": "https://www.fda.gov/example",
        "summary": "Short summary.",
        "products": [
            {
                "product_name": "Cloud Max Disposable",
                "brand": "CloudMax",
                "category": "Disposable Vape",
                "upc": "812345678901",
                "item_number": "CM-DISP-5000",
                "flavor": "Blue Razz Ice",
            }
        ],
    }
    item.update(over)
    return item


@pytest.fixture
def make_source(db_session: Session) -> Callable[..., RegulatorySource]:
    def _create(**over: Any) -> RegulatorySource:
        source = RegulatorySource(
            name=over.get("name", f"src-{uuid.uuid4().hex[:10]}"),
            kind=over.get("kind", RegulatorySourceKind.fda_enforcement),
            is_active=over.get("is_active", True),
        )
        db_session.add(source)
        db_session.commit()
        db_session.refresh(source)
        return source

    return _create


@pytest.fixture
def make_catalog(db_session: Session) -> Callable[..., ProductVariant]:
    """Catalog product/variant matching the default raw item (for matching)."""

    def _create() -> ProductVariant:
        product = Product(
            name="Cloud Max Disposable",
            brand="CloudMax",
            category="Disposable Vape",
            compliance_status=ComplianceStatus.allowed,
            allowed_for_sale=True,
            is_active=True,
        )
        db_session.add(product)
        db_session.commit()
        db_session.refresh(product)
        variant = ProductVariant(
            product_id=product.id,
            sku="CM-DISP-5000",
            barcode="812345678901",
            flavor="Blue Razz Ice",
            price=10,
        )
        db_session.add(variant)
        db_session.commit()
        db_session.refresh(variant)
        return variant

    return _create


def _client(items: list[dict[str, Any]]) -> StaticRegulatorySourceClient:
    return StaticRegulatorySourceClient(items)


# --------------------------------------------------------------------- #
# 1-3. Run creation, notice creation, created outcome
# --------------------------------------------------------------------- #


def test_manual_run_creates_run(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    source = make_source()
    run = svc.run_regulatory_source_ingestion(
        db_session,
        source.id,
        client=_client([_raw_item()]),
        detect_matches=False,
        create_alerts=False,
    )
    assert isinstance(run, RegulatoryIngestionRun)
    assert run.source_id == source.id
    assert run.trigger == "manual"
    assert run.status == "succeeded"
    assert run.finished_at is not None


def test_successful_run_creates_notice_and_created_item(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    source = make_source()
    raw = _raw_item()
    run = svc.run_regulatory_source_ingestion(
        db_session,
        source.id,
        client=_client([raw]),
        detect_matches=False,
        create_alerts=False,
    )
    notices = list(
        db_session.scalars(
            select(RegulatoryNotice).where(
                RegulatoryNotice.source_id == source.id
            )
        ).all()
    )
    assert len(notices) == 1
    assert notices[0].external_ref == raw["document_number"]
    # source_url folded into payload (B deferred the column).
    assert notices[0].payload.get("source_url") == raw["url"]

    db_session.refresh(run)
    items = run.items
    assert len(items) == 1
    assert items[0].outcome == "created"
    assert items[0].notice_id == notices[0].id
    assert items[0].content_hash == notices[0].content_hash


# --------------------------------------------------------------------- #
# 4-5. Re-run dedupes; counters correct
# --------------------------------------------------------------------- #


def test_rerun_dedupes_without_duplicating_notices(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    source = make_source()
    raw = _raw_item()

    first = svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_client([raw]),
        detect_matches=False, create_alerts=False,
    )
    assert first.items_seen == 1
    assert first.items_created == 1
    assert first.items_deduped == 0
    assert first.items_failed == 0

    second = svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_client([raw]),
        detect_matches=False, create_alerts=False,
    )
    assert second.items_seen == 1
    assert second.items_created == 0
    assert second.items_deduped == 1
    assert second.items_failed == 0
    assert second.status == "succeeded"

    notice_count = db_session.scalar(
        select(func.count())
        .select_from(RegulatoryNotice)
        .where(RegulatoryNotice.source_id == source.id)
    )
    assert notice_count == 1


def test_counters_with_mixed_batch(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    source = make_source()
    good_a = _raw_item()
    good_b = _raw_item()
    bad = _raw_item(document_type="totally_unknown_type")  # parser rejects

    run = svc.run_regulatory_source_ingestion(
        db_session,
        source.id,
        client=_client([good_a, good_b, bad]),
        detect_matches=False,
        create_alerts=False,
    )
    assert run.items_seen == 3
    assert run.items_created == 2
    assert run.items_deduped == 0
    assert run.items_failed == 1
    assert run.status == "partial"
    assert run.error_summary is not None


# --------------------------------------------------------------------- #
# 6-7. Source bookkeeping timestamps
# --------------------------------------------------------------------- #


def test_last_attempted_at_always_updates(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    source = make_source()
    assert source.last_attempted_at is None
    # A run with no resolvable client still records an attempt + failed run.
    run = svc.run_regulatory_source_ingestion(db_session, source.id)
    db_session.refresh(source)
    assert source.last_attempted_at is not None
    assert run.status == "failed"
    assert source.last_succeeded_at is None


def test_last_succeeded_at_only_on_success(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    source = make_source()

    # Failure path: no success timestamp.
    bad = _raw_item(document_type="totally_unknown_type")
    svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_client([bad]),
        detect_matches=False, create_alerts=False,
    )
    db_session.refresh(source)
    assert source.last_succeeded_at is None
    assert source.last_attempted_at is not None

    # Success path: success timestamp set.
    svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_client([_raw_item()]),
        detect_matches=False, create_alerts=False,
    )
    db_session.refresh(source)
    assert source.last_succeeded_at is not None


# --------------------------------------------------------------------- #
# 8-9. Failure handling
# --------------------------------------------------------------------- #


def test_all_items_fail_marks_run_failed(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    source = make_source()
    bad = _raw_item(document_type="totally_unknown_type")
    run = svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_client([bad]),
        detect_matches=False, create_alerts=False,
    )
    assert run.status == "failed"
    assert run.items_failed == 1
    db_session.refresh(run)
    assert run.items[0].outcome == "failed"
    assert run.items[0].error_code == "parse_error"
    assert run.items[0].notice_id is None


def test_fetch_failure_marks_run_failed_with_redacted_summary(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    source = make_source()
    secret_blob = "SENSITIVE-TOKEN-abcdef0123456789"

    class _ExplodingClient:
        def fetch(self) -> list[dict[str, Any]]:
            raise RuntimeError(f"boom with {secret_blob}")

    run = svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_ExplodingClient(),
    )
    assert run.status == "failed"
    assert run.finished_at is not None
    assert run.items_seen == 0
    assert run.error_summary is not None
    # The error summary is bounded; here the message is short, but the redactor
    # records type + message without raw payloads.
    assert "RuntimeError" in run.error_summary
    db_session.refresh(source)
    assert source.last_succeeded_at is None


# --------------------------------------------------------------------- #
# 10-11. Matches + alerts flow through the EXISTING pipeline
# --------------------------------------------------------------------- #


def test_detect_matches_creates_matches(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
    make_catalog: Callable[..., ProductVariant],
) -> None:
    make_catalog()
    source = make_source()
    run = svc.run_regulatory_source_ingestion(
        db_session,
        source.id,
        client=_client([_raw_item()]),
        detect_matches=True,
        create_alerts=False,
    )
    assert run.matches_created > 0
    assert run.alerts_created == 0


def test_create_alerts_creates_alerts(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
    make_catalog: Callable[..., ProductVariant],
) -> None:
    make_catalog()
    source = make_source()
    run = svc.run_regulatory_source_ingestion(
        db_session,
        source.id,
        client=_client([_raw_item()]),
        detect_matches=True,
        create_alerts=True,
    )
    assert run.matches_created > 0
    assert run.alerts_created > 0
    alert_count = db_session.scalar(
        select(func.count()).select_from(ComplianceAlert)
    )
    assert alert_count == run.alerts_created


def test_rerun_does_not_inflate_match_alert_counts(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
    make_catalog: Callable[..., ProductVariant],
) -> None:
    make_catalog()
    source = make_source()
    raw = _raw_item()
    svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_client([raw])
    )
    second = svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_client([raw])
    )
    # Deduped re-run: matcher/alerts are idempotent, deltas are zero.
    assert second.items_deduped == 1
    assert second.matches_created == 0
    assert second.alerts_created == 0


# --------------------------------------------------------------------- #
# 12-16. Ingestion mutates nothing outside notices/matches/alerts
# --------------------------------------------------------------------- #


def test_ingestion_does_not_touch_product_inventory_or_audit(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
    make_catalog: Callable[..., ProductVariant],
) -> None:
    variant = make_catalog()
    product = db_session.get(Product, variant.product_id)
    before_status = product.compliance_status
    before_allowed = product.allowed_for_sale

    # Give the product an inventory row to confirm inventory is untouched.
    store = Store(name="Test Store", code=f"st-{uuid.uuid4().hex[:8]}")
    db_session.add(store)
    db_session.commit()
    item = InventoryItem(
        store_id=store.id,
        variant_id=variant.id,
        quantity_on_hand=5,
    )
    db_session.add(item)
    db_session.commit()
    inv_before = item.quantity_on_hand

    dec_before = db_session.scalar(
        select(func.count()).select_from(RegulatoryDecisionAuditLog)
    )
    op_before = db_session.scalar(
        select(func.count()).select_from(OperationalAuditLog)
    )

    source = make_source()
    svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_client([_raw_item()])
    )

    db_session.refresh(product)
    db_session.refresh(item)
    assert product.compliance_status == before_status
    assert product.allowed_for_sale == before_allowed
    assert item.quantity_on_hand == inv_before

    dec_after = db_session.scalar(
        select(func.count()).select_from(RegulatoryDecisionAuditLog)
    )
    op_after = db_session.scalar(
        select(func.count()).select_from(OperationalAuditLog)
    )
    assert dec_after == dec_before
    assert op_after == op_before


# --------------------------------------------------------------------- #
# 17. Static guard — no forbidden lifecycle/compliance/audit symbols
# --------------------------------------------------------------------- #


def test_orchestrator_source_has_no_forbidden_symbols() -> None:
    source_code = pathlib.Path(svc.__file__).read_text(encoding="utf-8")
    for term in (
        "set_product_compliance",
        "acknowledge_compliance_alert",
        "dismiss_compliance_alert",
        "resolve_compliance_alert",
        "RegulatoryDecisionAuditLog",
        "OperationalAuditLog",
    ):
        assert term not in source_code, f"forbidden symbol present: {term}"


# --------------------------------------------------------------------- #
# Inactive / missing source rejection (controlled errors, no run created)
# --------------------------------------------------------------------- #


def test_inactive_source_rejected_without_run(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    from fastapi import HTTPException

    source = make_source(is_active=False)
    with pytest.raises(HTTPException) as exc_info:
        svc.run_regulatory_source_ingestion(
            db_session, source.id, client=_client([_raw_item()])
        )
    assert exc_info.value.status_code == 409
    run_count = db_session.scalar(
        select(func.count())
        .select_from(RegulatoryIngestionRun)
        .where(RegulatoryIngestionRun.source_id == source.id)
    )
    assert run_count == 0


def test_missing_source_raises_404(db_session: Session) -> None:
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        svc.run_regulatory_source_ingestion(
            db_session, uuid.uuid4(), client=_client([_raw_item()])
        )
    assert exc_info.value.status_code == 404


# --------------------------------------------------------------------- #
# F2.27.7.D — single-in-flight guard + stale-run reconciliation
# --------------------------------------------------------------------- #


def _running_run(
    db_session: Session, source: RegulatorySource, *, age_minutes: int
) -> RegulatoryIngestionRun:
    run = RegulatoryIngestionRun(
        source_id=source.id,
        trigger="manual",
        status="running",
        started_at=datetime.now(UTC) - timedelta(minutes=age_minutes),
    )
    db_session.add(run)
    db_session.commit()
    db_session.refresh(run)
    return run


def test_existing_running_run_blocks_new_run(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    from fastapi import HTTPException

    source = make_source()
    _running_run(db_session, source, age_minutes=1)
    with pytest.raises(HTTPException) as exc_info:
        svc.run_regulatory_source_ingestion(
            db_session, source.id, client=_client([_raw_item()])
        )
    assert exc_info.value.status_code == 409
    # No second running row was created.
    count = db_session.scalar(
        select(func.count())
        .select_from(RegulatoryIngestionRun)
        .where(RegulatoryIngestionRun.source_id == source.id)
    )
    assert count == 1


def test_completed_run_does_not_block_new_run(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    source = make_source()
    first = svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_client([_raw_item()]),
        detect_matches=False, create_alerts=False,
    )
    assert first.status == "succeeded"
    second = svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_client([_raw_item()]),
        detect_matches=False, create_alerts=False,
    )
    assert second.status == "succeeded"
    assert second.id != first.id


def test_fresh_running_run_still_blocks(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    from fastapi import HTTPException

    source = make_source()
    _running_run(db_session, source, age_minutes=5)  # within threshold
    with pytest.raises(HTTPException) as exc_info:
        svc.run_regulatory_source_ingestion(
            db_session, source.id, client=_client([_raw_item()])
        )
    assert exc_info.value.status_code == 409


def test_stale_running_run_reconciled_then_new_run_proceeds(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    source = make_source()
    stale = _running_run(db_session, source, age_minutes=120)  # past threshold
    stale_id = stale.id

    run = svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_client([_raw_item()]),
        detect_matches=False, create_alerts=False,
    )
    assert run.status == "succeeded"

    reconciled = db_session.get(RegulatoryIngestionRun, stale_id)
    assert reconciled.status == "failed"
    assert reconciled.finished_at is not None
    assert "stale" in (reconciled.error_summary or "").lower()


# --------------------------------------------------------------------- #
# F2.27.7.D — cursor advancement (only on full success)
# --------------------------------------------------------------------- #


def test_successful_run_advances_cursor(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    source = make_source()
    raw = _raw_item()
    run = svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_client([raw]),
        detect_matches=False, create_alerts=False,
    )
    assert run.status == "succeeded"
    db_session.refresh(source)
    cursor = source.cursor
    assert cursor is not None
    assert cursor["last_successful_run_id"] == str(run.id)
    assert "last_finished_at" in cursor
    assert cursor["last_item_external_ref"] == raw["document_number"]
    assert cursor["last_published_at"].startswith("2024-09-15")


def test_empty_successful_run_records_minimal_cursor(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    source = make_source()
    run = svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_client([]),
        detect_matches=False, create_alerts=False,
    )
    assert run.status == "succeeded"
    db_session.refresh(source)
    assert source.cursor is not None
    assert source.cursor["last_successful_run_id"] == str(run.id)
    assert "last_item_external_ref" not in source.cursor


def test_partial_run_does_not_advance_cursor(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    source = make_source()
    good = _raw_item()
    bad = _raw_item(document_type="totally_unknown_type")
    run = svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_client([good, bad]),
        detect_matches=False, create_alerts=False,
    )
    assert run.status == "partial"
    db_session.refresh(source)
    assert source.cursor is None


def test_failed_run_does_not_advance_cursor(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    source = make_source()
    bad = _raw_item(document_type="totally_unknown_type")
    run = svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_client([bad]),
        detect_matches=False, create_alerts=False,
    )
    assert run.status == "failed"
    db_session.refresh(source)
    assert source.cursor is None


# --------------------------------------------------------------------- #
# F2.27.7.D — error redaction hardening
# --------------------------------------------------------------------- #


def test_redact_truncates_long_message_and_keeps_type() -> None:
    long_message = "x" * 5000 + "TRAILING_SECRET_zzz"
    out = svc._redact(ValueError(long_message))
    assert out.startswith("ValueError:")
    assert len(out) <= svc._ERROR_TEXT_LIMIT
    assert "TRAILING_SECRET_zzz" not in out


def test_fetch_failure_summary_bounded_and_drops_trailing_secret(
    db_session: Session, make_source: Callable[..., RegulatorySource]
) -> None:
    source = make_source()
    secret = "APIKEY-LEAKME-9999"

    class _BoomClient:
        def fetch(self) -> list[dict[str, Any]]:
            raise RuntimeError("boom " + ("y" * 1000) + secret)

    run = svc.run_regulatory_source_ingestion(
        db_session, source.id, client=_BoomClient()
    )
    assert run.status == "failed"
    assert run.error_summary is not None
    assert len(run.error_summary) <= svc._ERROR_SUMMARY_LIMIT
    assert secret not in run.error_summary
