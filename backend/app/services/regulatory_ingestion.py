"""Regulatory source ingestion orchestrator (F2.27.7.C).

A THIN acquisition layer that drives the existing, human-gated regulatory
pipeline from an external/in-memory source — it adds no parallel pipeline and
makes no compliance decision. The flow for one manual run is:

    source client -> raw items
      -> parser -> ParsedNotice
        -> ingest_regulatory_notice        (existing; idempotent persistence)
        -> detect_regulatory_product_matches (existing; advisory matches)
        -> create_compliance_alerts_from_matches (existing; advisory alerts)
      -> regulatory_ingestion_items (per-item outcome ledger)
    -> regulatory_ingestion_runs (run header with rolled-up counters)
      -> admin review (unchanged admin lifecycle surface)

What this module deliberately NEVER does (the human-gated boundary):
  - it does not apply any product compliance change, and touches no Product
    sellability/compliance column;
  - it does not run any alert lifecycle transition (acknowledge / dismiss /
    resolve);
  - it writes NO regulatory decision audit row and NO operational audit row;
  - it implements no automatic hold / ban / block;
  - it performs no real network I/O here and needs no credentials — the source
    client is injected (tests) or resolved by `resolve_source_client` (a real
    HTTP client is a later concern, intentionally absent in this subphase).

Created-vs-deduped is derived by pre-checking `(source_id, content_hash)` with
the SAME `compute_regulatory_notice_content_hash` the persistence service uses,
then delegating to the idempotent `ingest_regulatory_notice`. Match/alert
counters are DELTAS (count after the idempotent call minus count before) so a
re-run never inflates them.

Source URL: F2.27.7.B deferred a `regulatory_notices.source_url` column, so a
parsed `source_url` is folded into `payload["source_url"]` (no new migration,
no change to the notice read contract).
"""

from __future__ import annotations

import logging
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_regulatory_settings
from app.db.models import ComplianceAlert
from app.db.models import RegulatoryIngestionItem
from app.db.models import RegulatoryIngestionRun
from app.db.models import RegulatoryNotice
from app.db.models import RegulatoryProductMatch
from app.db.models import RegulatorySource
from app.db.models import RegulatorySourceKind
from app.schemas.regulatory import RegulatoryNoticeIngestRequest
from app.schemas.regulatory_ingestion import RegulatoryIngestionItemRead
from app.schemas.regulatory_ingestion import (
    RegulatoryIngestionRunDetailResponse,
)
from app.schemas.regulatory_ingestion import RegulatoryIngestionRunListResponse
from app.schemas.regulatory_ingestion import RegulatoryIngestionRunRead
from app.services.regulatory import compute_regulatory_notice_content_hash
from app.services.regulatory import create_compliance_alerts_from_matches
from app.services.regulatory import detect_regulatory_product_matches
from app.services.regulatory import get_regulatory_source
from app.services.regulatory import ingest_regulatory_notice
from app.services.regulatory_sources import FdaRegulatorySourceClient
from app.services.regulatory_sources import FdaRegulatorySourceParser
from app.services.regulatory_sources import ParsedNotice
from app.services.regulatory_sources import RegulatorySourceClient
from app.services.regulatory_sources import RegulatorySourceParseError
from app.services.regulatory_sources import RegulatorySourceParser


logger = logging.getLogger(__name__)

_MAX_LIST_LIMIT = 100
_ERROR_TEXT_LIMIT = 480
_ERROR_SUMMARY_LIMIT = 500

# A run still `running` longer than this (e.g. after a process crash mid-run)
# is reconciled to `failed` at the next manual trigger for the same source.
# Manual-trigger-only — there is NO scheduler/background sweeper.
_STALE_RUN_THRESHOLD_MINUTES = 60

# FDA-backed source kinds parse with the F2.27.7.A FDA parser.
_FDA_SOURCE_KINDS = frozenset(
    {
        RegulatorySourceKind.fda_pmta,
        RegulatorySourceKind.fda_enforcement,
        RegulatorySourceKind.fda_advisory,
    }
)


class RegulatorySourceIngestionError(Exception):
    """A controlled ingestion-setup failure (e.g. no client/parser resolvable).

    Caught by the orchestrator and recorded as a failed run; never carries a
    raw payload, secret, or credential in its message.
    """


def _now() -> datetime:
    return datetime.now(UTC)


def _redact(exc: Exception, *, limit: int = _ERROR_TEXT_LIMIT) -> str:
    """Short, payload-free description of a failure for the ledger.

    Records the exception type plus a truncated message. The exceptions raised
    in this flow (parse / persist) do not embed raw payloads or secrets, and
    truncation bounds anything unexpected.
    """
    message = str(exc).strip()
    text = f"{type(exc).__name__}: {message}" if message else type(exc).__name__
    if len(text) > limit:
        text = text[: limit - 1] + "…"
    return text


def resolve_source_client(source: RegulatorySource) -> RegulatorySourceClient:
    """Resolve the real HTTP client used to fetch raw items for a source.

    The fetch URL comes from the source's non-secret `fetch_config["url"]` or,
    failing that, the `FDA_REGULATORY_BASE_URL` setting. With NEITHER set the
    source is not fetch-configured and this raises a controlled configuration
    error — the orchestrator records that as a failed run rather than guessing.
    The optional API key and the timeout / max-items caps come from settings;
    the key is never persisted to the DB. Tests never reach this path with a
    URL configured (they inject a client), so no real network occurs offline.
    """
    settings = get_regulatory_settings()
    fetch_config = source.fetch_config or {}
    configured_url = fetch_config.get("url")
    url = (
        configured_url
        if isinstance(configured_url, str) and configured_url.strip()
        else settings.fda_regulatory_base_url
    ).strip()
    if not url:
        raise RegulatorySourceIngestionError(
            "No ingestion URL is configured for this source."
        )
    return FdaRegulatorySourceClient(
        url=url,
        api_key=settings.fda_regulatory_api_key or None,
        timeout=settings.fda_regulatory_timeout_seconds,
        max_items=settings.fda_regulatory_max_items_per_run,
    )


def _mark_stale_runs(db: Session, source_id: UUID) -> int:
    """Mark `running` runs older than the threshold as `failed` (no commit).

    Reconciles runs orphaned by a crashed process so a stale `running` row can
    never permanently block a source. Mutates in-session only; the caller
    commits as part of the locked check-and-create critical section.
    """
    threshold = _now() - timedelta(minutes=_STALE_RUN_THRESHOLD_MINUTES)
    stale = list(
        db.scalars(
            select(RegulatoryIngestionRun).where(
                RegulatoryIngestionRun.source_id == source_id,
                RegulatoryIngestionRun.status == "running",
                RegulatoryIngestionRun.started_at < threshold,
            )
        ).all()
    )
    for run in stale:
        run.status = "failed"
        run.finished_at = _now()
        run.error_summary = (
            "Run reconciled as stale: still running past the "
            f"{_STALE_RUN_THRESHOLD_MINUTES}-minute threshold."
        )
    return len(stale)


def _has_active_run(db: Session, source_id: UUID) -> bool:
    """Whether a (non-stale) `running` run already exists for the source."""
    return (
        db.scalar(
            select(RegulatoryIngestionRun.id).where(
                RegulatoryIngestionRun.source_id == source_id,
                RegulatoryIngestionRun.status == "running",
            )
        )
        is not None
    )


def resolve_source_parser(source: RegulatorySource) -> RegulatorySourceParser:
    """Resolve the parser for a source by its kind (FDA in this subphase)."""
    if source.kind in _FDA_SOURCE_KINDS:
        return FdaRegulatorySourceParser()
    raise RegulatorySourceIngestionError(
        f"No parser is available for source kind '{source.kind.value}'."
    )


def _best_effort_external_ref(raw: Any) -> str | None:
    """A label for a failed (unparseable) item — never the raw body."""
    if not isinstance(raw, dict):
        return None
    for key in ("document_number", "external_ref", "id"):
        value = raw.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()[:255]
    return None


def _notice_payload(parsed: ParsedNotice) -> dict[str, Any]:
    """Parsed payload with `source_url` folded in (B deferred the column)."""
    payload = dict(parsed.payload)
    if parsed.source_url and "source_url" not in payload:
        payload["source_url"] = parsed.source_url
    return payload


def _count_matches(db: Session, notice_id: UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(RegulatoryProductMatch)
            .where(RegulatoryProductMatch.notice_id == notice_id)
        )
        or 0
    )


def _count_alerts(db: Session, notice_id: UUID) -> int:
    return (
        db.scalar(
            select(func.count())
            .select_from(ComplianceAlert)
            .where(ComplianceAlert.notice_id == notice_id)
        )
        or 0
    )


def _notice_exists(db: Session, source_id: UUID, content_hash: str) -> bool:
    return (
        db.scalar(
            select(RegulatoryNotice.id).where(
                RegulatoryNotice.source_id == source_id,
                RegulatoryNotice.content_hash == content_hash,
            )
        )
        is not None
    )


def run_regulatory_source_ingestion(
    db: Session,
    source_id: UUID,
    actor_user_id: UUID | None = None,
    *,
    detect_matches: bool = True,
    create_alerts: bool = True,
    client: RegulatorySourceClient | None = None,
    parser: RegulatorySourceParser | None = None,
) -> RegulatoryIngestionRun:
    """Run one manual ingestion of a regulatory source, recording the ledger.

    Loads the source (404 if missing, 409 if inactive), opens a `running`
    ingestion run, fetches + parses raw items through the injected/resolved
    client + parser, and for each item delegates to the existing idempotent
    pipeline (`ingest_regulatory_notice` then, optionally,
    `detect_regulatory_product_matches` and
    `create_compliance_alerts_from_matches`). Each item's outcome
    (`created` / `deduped` / `failed`) is recorded; run counters and the
    terminal status (`succeeded` / `partial` / `failed`) are derived from those
    outcomes. The source's `last_attempted_at` is always stamped, and
    `last_succeeded_at` only on a fully successful run. Returns the persisted
    run (its `items` are loadable via the relationship).

    Never mutates a product, runs an alert lifecycle transition, or writes a
    decision/operational audit row.
    """
    # Pre-run validation: a missing/inactive source is rejected before any run
    # row is created (404 / 409), matching the repo's request-level errors.
    source = get_regulatory_source(db, source_id)
    if not source.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Regulatory source is inactive.",
        )

    # Reconcile stale `running` runs (e.g. orphaned by a crash) first, as an
    # independent committed maintenance step so the marks survive even if the
    # guard below then blocks this trigger.
    if _mark_stale_runs(db, source_id):
        db.commit()

    # Single-in-flight guard. Lock the source row so two concurrent triggers
    # serialize here; then reject if a (now non-stale) run is still in progress
    # — BEFORE a second run row is created. The lock is held across this
    # check-and-create until the run-creation commit below releases it.
    db.execute(
        select(RegulatorySource.id)
        .where(RegulatorySource.id == source_id)
        .with_for_update()
    )
    if _has_active_run(db, source_id):
        db.rollback()  # release the row lock; no run created
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An ingestion run is already in progress for this source.",
        )

    started_at = _now()
    run = RegulatoryIngestionRun(
        source_id=source_id,
        trigger="manual",
        status="running",
        started_at=started_at,
        actor_user_id=actor_user_id,
    )
    db.add(run)
    # Every trigger is an attempt, recorded even if the fetch then fails.
    source.last_attempted_at = started_at
    db.commit()
    db.refresh(run)
    run_id = run.id
    logger.info(
        "regulatory ingestion run %s started (source=%s, trigger=manual)",
        run_id,
        source_id,
    )

    items_seen = 0
    items_created = 0
    items_deduped = 0
    items_failed = 0
    matches_created = 0
    alerts_created = 0
    had_pipeline_error = False
    fetch_error: str | None = None
    # Cursor high-water marks, advanced only on a fully successful run.
    last_external_ref: str | None = None
    max_published_at: datetime | None = None

    # ----- Fetch + resolve (a failure here is a failed run, no items) ----- #
    try:
        active_client = client if client is not None else resolve_source_client(
            source
        )
        active_parser = (
            parser if parser is not None else resolve_source_parser(source)
        )
        raw_items = active_client.fetch()
    except Exception as exc:  # any client/resolve failure -> recorded failed run
        fetch_error = _redact(exc)
        raw_items = None
        logger.warning(
            "regulatory ingestion run %s fetch failed (source=%s): %s",
            run_id,
            source_id,
            fetch_error,
        )

    if raw_items is not None:
        for raw in raw_items:
            items_seen += 1
            try:
                parsed = active_parser.parse(raw)
                payload = _notice_payload(parsed)
                content_hash = compute_regulatory_notice_content_hash(
                    notice_type=parsed.notice_type,
                    title=parsed.title,
                    external_ref=parsed.external_ref,
                    published_at=parsed.published_at,
                    payload=payload,
                )
                existed = _notice_exists(db, source_id, content_hash)
                read = ingest_regulatory_notice(
                    db,
                    RegulatoryNoticeIngestRequest(
                        source_id=source_id,
                        external_ref=parsed.external_ref,
                        title=parsed.title,
                        notice_type=parsed.notice_type,
                        published_at=parsed.published_at,
                        payload=payload,
                    ),
                )
            except Exception as exc:
                # One bad item never aborts the run: record it failed and move
                # on. _redact keeps any raw detail out of the ledger.
                db.rollback()
                items_failed += 1
                code = (
                    "parse_error"
                    if isinstance(exc, RegulatorySourceParseError)
                    else "persist_error"
                )
                db.add(
                    RegulatoryIngestionItem(
                        run_id=run_id,
                        external_ref=_best_effort_external_ref(raw),
                        content_hash=None,
                        outcome="failed",
                        error_code=code,
                        error_message=_redact(exc),
                    )
                )
                db.commit()
                continue

            outcome = "deduped" if existed else "created"
            if existed:
                items_deduped += 1
            else:
                items_created += 1

            # Durably record the notice outcome BEFORE the advisory pipeline,
            # so a later match/alert hiccup never loses the item.
            db.add(
                RegulatoryIngestionItem(
                    run_id=run_id,
                    external_ref=parsed.external_ref,
                    content_hash=content_hash,
                    outcome=outcome,
                    notice_id=read.id,
                )
            )
            db.commit()

            # Track cursor high-water marks from successfully ingested items.
            if parsed.external_ref:
                last_external_ref = parsed.external_ref
            if parsed.published_at is not None and (
                max_published_at is None
                or parsed.published_at > max_published_at
            ):
                max_published_at = parsed.published_at

            # Advisory, idempotent pipeline. Count only newly-created rows.
            if detect_matches:
                try:
                    before_matches = _count_matches(db, read.id)
                    matches = detect_regulatory_product_matches(db, read.id)
                    matches_created += max(0, len(matches) - before_matches)
                    if create_alerts:
                        before_alerts = _count_alerts(db, read.id)
                        alerts = create_compliance_alerts_from_matches(
                            db, read.id
                        )
                        alerts_created += max(
                            0, len(alerts) - before_alerts
                        )
                except Exception:
                    # Advisory match/alert generation is best-effort; a failure
                    # here downgrades the run but never loses the notice/item.
                    db.rollback()
                    had_pipeline_error = True

    # ----- Close out the run + source bookkeeping ----- #
    any_success = (items_created + items_deduped) > 0
    any_failure = items_failed > 0 or had_pipeline_error

    if fetch_error is not None:
        run_status = "failed"
    elif items_seen == 0:
        run_status = "succeeded"
    elif items_failed == items_seen:
        run_status = "failed"
    elif any_success and any_failure:
        run_status = "partial"
    elif any_failure:
        run_status = "failed"
    else:
        run_status = "succeeded"

    if fetch_error is not None:
        error_summary: str | None = fetch_error
    elif run_status in ("failed", "partial"):
        error_summary = (
            f"{items_failed} of {items_seen} item(s) failed during ingestion."
        )
        if had_pipeline_error:
            error_summary += " Match/alert generation errored for an item."
    else:
        error_summary = None
    if error_summary is not None and len(error_summary) > _ERROR_SUMMARY_LIMIT:
        error_summary = error_summary[: _ERROR_SUMMARY_LIMIT - 1] + "…"

    finished_at = _now()
    run = db.get(RegulatoryIngestionRun, run_id)
    run.status = run_status
    run.finished_at = finished_at
    run.items_seen = items_seen
    run.items_created = items_created
    run.items_deduped = items_deduped
    run.items_failed = items_failed
    run.matches_created = matches_created
    run.alerts_created = alerts_created
    run.error_summary = error_summary

    source = db.get(RegulatorySource, source_id)
    if run_status == "succeeded":
        # Advance the cursor ONLY on a fully successful run. Values are
        # JSON-serializable and non-secret; an empty successful run still
        # records the run id + finish time.
        source.last_succeeded_at = finished_at
        cursor: dict[str, Any] = {
            "last_successful_run_id": str(run_id),
            "last_finished_at": finished_at.isoformat(),
        }
        if last_external_ref is not None:
            cursor["last_item_external_ref"] = last_external_ref
        if max_published_at is not None:
            cursor["last_published_at"] = max_published_at.isoformat()
        source.cursor = cursor

    db.commit()
    db.refresh(run)
    logger.info(
        "regulatory ingestion run %s finished status=%s "
        "seen=%d created=%d deduped=%d failed=%d matches=%d alerts=%d",
        run_id,
        run_status,
        items_seen,
        items_created,
        items_deduped,
        items_failed,
        matches_created,
        alerts_created,
    )
    return run


# --------------------------------------------------------------------- #
# Read helpers backing the admin ingestion API
# --------------------------------------------------------------------- #


def _assert_list_pagination(limit: int, offset: int) -> None:
    if limit < 1 or limit > _MAX_LIST_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"limit must be between 1 and {_MAX_LIST_LIMIT}.",
        )
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="offset must be greater than or equal to 0.",
        )


def build_run_detail(run: RegulatoryIngestionRun) -> (
    RegulatoryIngestionRunDetailResponse
):
    """Project a run ORM row (+ its items, newest first) onto the detail wire."""
    ordered_items = sorted(
        run.items, key=lambda i: (i.created_at, i.id), reverse=True
    )
    return RegulatoryIngestionRunDetailResponse(
        run=RegulatoryIngestionRunRead.model_validate(run),
        items=[
            RegulatoryIngestionItemRead.model_validate(item)
            for item in ordered_items
        ],
    )


def list_regulatory_ingestion_runs(
    db: Session,
    *,
    source_id: UUID,
    limit: int = 25,
    offset: int = 0,
) -> RegulatoryIngestionRunListResponse:
    """Paginated list of a source's ingestion runs, newest first.

    Validates the source exists (404). `total` is computed before pagination.
    Read-only.
    """
    _assert_list_pagination(limit, offset)
    get_regulatory_source(db, source_id)

    stmt = (
        select(RegulatoryIngestionRun)
        .where(RegulatoryIngestionRun.source_id == source_id)
        .order_by(
            RegulatoryIngestionRun.created_at.desc(),
            RegulatoryIngestionRun.id.asc(),
        )
        .limit(limit)
        .offset(offset)
    )
    count_stmt = (
        select(func.count())
        .select_from(RegulatoryIngestionRun)
        .where(RegulatoryIngestionRun.source_id == source_id)
    )

    rows = list(db.scalars(stmt).all())
    total = db.scalar(count_stmt) or 0
    return RegulatoryIngestionRunListResponse(
        items=[RegulatoryIngestionRunRead.model_validate(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


def get_regulatory_ingestion_run_detail(
    db: Session, run_id: UUID
) -> RegulatoryIngestionRunDetailResponse:
    """Fetch one ingestion run + its item outcomes (404 if missing)."""
    run = db.get(RegulatoryIngestionRun, run_id)
    if run is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Regulatory ingestion run not found.",
        )
    return build_run_detail(run)
