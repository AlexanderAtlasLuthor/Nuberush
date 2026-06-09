"""DB-level model + constraint tests for the ingestion ledger (F2.27.7.B).

Exercises the persisted ingestion observability model against the real
(migrated) Postgres test database:
  - a run inserts and links to its source (and to an optional actor);
  - an item inserts, links to its run, and may reference a notice;
  - the `trigger` / `status` / `outcome` CHECK constraints reject bad values;
  - run counters default to 0 and timestamps populate;
  - the non-secret source bookkeeping columns round-trip;
  - the item table has NO raw-payload/body/secret column;
  - deleting a run cascades to its items;
  - the read schemas hydrate from the ORM rows.

Style mirrors tests/test_regulatory_models.py (local make_* helpers over the
transactional db_session, IntegrityError for DB constraints). This subphase
ships storage only: no orchestrator, route, scheduler, or writer is involved,
and nothing here mutates a product, an alert, or a compliance decision.
"""
from __future__ import annotations

import uuid
from datetime import UTC
from datetime import datetime
from typing import Callable

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import RegulatoryIngestionItem
from app.db.models import RegulatoryIngestionRun
from app.db.models import RegulatoryNotice
from app.db.models import RegulatoryNoticeType
from app.db.models import RegulatorySource
from app.db.models import RegulatorySourceKind
from app.db.models import User
from app.db.models import UserRole
from app.schemas.regulatory_ingestion import RegulatoryIngestionItemOutcome
from app.schemas.regulatory_ingestion import RegulatoryIngestionItemRead
from app.schemas.regulatory_ingestion import (
    RegulatoryIngestionRunDetailResponse,
)
from app.schemas.regulatory_ingestion import RegulatoryIngestionRunRead
from app.schemas.regulatory_ingestion import RegulatoryIngestionRunStatus
from app.schemas.regulatory_ingestion import RegulatoryIngestionTrigger
from tests.helpers.auth import make_user as central_make_user


# --------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------- #


@pytest.fixture
def make_source(db_session: Session) -> Callable[..., RegulatorySource]:
    def _create(**over) -> RegulatorySource:
        source = RegulatorySource(
            name=over.get("name", f"src-{uuid.uuid4().hex[:10]}"),
            kind=over.get("kind", RegulatorySourceKind.fda_enforcement),
        )
        db_session.add(source)
        db_session.commit()
        db_session.refresh(source)
        return source

    return _create


@pytest.fixture
def make_notice(db_session: Session) -> Callable[..., RegulatoryNotice]:
    def _create(source: RegulatorySource, **over) -> RegulatoryNotice:
        notice = RegulatoryNotice(
            source_id=source.id,
            title=over.get("title", "Sample notice"),
            notice_type=over.get(
                "notice_type", RegulatoryNoticeType.enforcement_notice
            ),
            payload=over.get("payload", {"products": []}),
            content_hash=over.get("content_hash", uuid.uuid4().hex),
        )
        db_session.add(notice)
        db_session.commit()
        db_session.refresh(notice)
        return notice

    return _create


@pytest.fixture
def make_run(db_session: Session) -> Callable[..., RegulatoryIngestionRun]:
    def _create(source: RegulatorySource, **over) -> RegulatoryIngestionRun:
        run = RegulatoryIngestionRun(
            source_id=source.id,
            trigger=over.get("trigger", "manual"),
            status=over.get("status", "running"),
            started_at=over.get("started_at", datetime.now(UTC)),
            **{
                key: over[key]
                for key in (
                    "finished_at",
                    "items_seen",
                    "items_created",
                    "items_deduped",
                    "items_failed",
                    "matches_created",
                    "alerts_created",
                    "error_summary",
                    "actor_user_id",
                )
                if key in over
            },
        )
        db_session.add(run)
        db_session.commit()
        db_session.refresh(run)
        return run

    return _create


@pytest.fixture
def admin(db_session: Session) -> User:
    return central_make_user(db_session, role=UserRole.admin)


# --------------------------------------------------------------------- #
# 1. Run links to source (+ optional actor)
# --------------------------------------------------------------------- #


def test_create_run_linked_to_source(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
    make_run: Callable[..., RegulatoryIngestionRun],
) -> None:
    source = make_source()
    run = make_run(source)

    assert run.id is not None
    assert run.source_id == source.id
    assert run.source is source
    db_session.refresh(source)
    assert run in source.ingestion_runs


def test_run_actor_relationship_and_nullable(
    make_source: Callable[..., RegulatorySource],
    make_run: Callable[..., RegulatoryIngestionRun],
    admin: User,
) -> None:
    source = make_source()
    with_actor = make_run(source, actor_user_id=admin.id)
    without_actor = make_run(source)

    assert with_actor.actor_user_id == admin.id
    assert with_actor.actor_user is admin
    # A scheduled/system run has no human actor.
    assert without_actor.actor_user_id is None
    assert without_actor.actor_user is None


# --------------------------------------------------------------------- #
# 2 + 3. Item links to run, and optionally to a notice
# --------------------------------------------------------------------- #


def test_create_item_linked_to_run(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
    make_run: Callable[..., RegulatoryIngestionRun],
) -> None:
    source = make_source()
    run = make_run(source)
    item = RegulatoryIngestionItem(
        run_id=run.id,
        external_ref="FDA-X-1",
        content_hash=uuid.uuid4().hex,
        outcome="created",
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    assert item.run_id == run.id
    assert item.run is run
    db_session.refresh(run)
    assert item in run.items
    # notice_id is optional and unset here.
    assert item.notice_id is None


def test_item_links_to_notice(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
    make_notice: Callable[..., RegulatoryNotice],
    make_run: Callable[..., RegulatoryIngestionRun],
) -> None:
    source = make_source()
    notice = make_notice(source)
    run = make_run(source)
    item = RegulatoryIngestionItem(
        run_id=run.id,
        external_ref="FDA-X-2",
        content_hash=notice.content_hash,
        outcome="deduped",
        notice_id=notice.id,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)

    assert item.notice_id == notice.id
    assert item.notice is notice


# --------------------------------------------------------------------- #
# 4. Valid trigger / status / outcome values persist
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("trigger", ["manual", "scheduled"])
@pytest.mark.parametrize(
    "status", ["running", "succeeded", "failed", "partial"]
)
def test_valid_trigger_and_status_persist(
    make_source: Callable[..., RegulatorySource],
    make_run: Callable[..., RegulatoryIngestionRun],
    trigger: str,
    status: str,
) -> None:
    source = make_source()
    run = make_run(source, trigger=trigger, status=status)
    assert run.trigger == trigger
    assert run.status == status


@pytest.mark.parametrize("outcome", ["created", "deduped", "failed"])
def test_valid_outcome_persists(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
    make_run: Callable[..., RegulatoryIngestionRun],
    outcome: str,
) -> None:
    source = make_source()
    run = make_run(source)
    item = RegulatoryIngestionItem(run_id=run.id, outcome=outcome)
    db_session.add(item)
    db_session.commit()
    db_session.refresh(item)
    assert item.outcome == outcome


# --------------------------------------------------------------------- #
# 5. Invalid values rejected by the CHECK constraints
# --------------------------------------------------------------------- #


def test_invalid_trigger_rejected(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
) -> None:
    source = make_source()
    db_session.add(
        RegulatoryIngestionRun(
            source_id=source.id,
            trigger="webhook",  # not in ('manual','scheduled')
            status="running",
            started_at=datetime.now(UTC),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_invalid_status_rejected(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
) -> None:
    source = make_source()
    db_session.add(
        RegulatoryIngestionRun(
            source_id=source.id,
            trigger="manual",
            status="done",  # not a valid status
            started_at=datetime.now(UTC),
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_negative_counter_rejected(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
) -> None:
    source = make_source()
    db_session.add(
        RegulatoryIngestionRun(
            source_id=source.id,
            trigger="manual",
            status="running",
            started_at=datetime.now(UTC),
            items_seen=-1,
        )
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_invalid_outcome_rejected(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
    make_run: Callable[..., RegulatoryIngestionRun],
) -> None:
    source = make_source()
    run = make_run(source)
    db_session.add(
        RegulatoryIngestionItem(run_id=run.id, outcome="skipped")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


# --------------------------------------------------------------------- #
# 6 + 7. Source fetch_config / cursor / timestamps round-trip
# --------------------------------------------------------------------- #


def test_source_fetch_config_and_cursor_roundtrip(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
) -> None:
    source = make_source()
    source.fetch_config = {"endpoint": "/enforcement", "parser_key": "fda"}
    source.cursor = {"last_external_ref": "FDA-2024-N-1234-0001"}
    db_session.commit()
    db_session.refresh(source)

    assert source.fetch_config == {
        "endpoint": "/enforcement",
        "parser_key": "fda",
    }
    assert source.cursor == {"last_external_ref": "FDA-2024-N-1234-0001"}


def test_source_attempt_and_success_timestamps_roundtrip(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
) -> None:
    source = make_source()
    # Defaults are NULL until an ingestion run sets them.
    assert source.last_attempted_at is None
    assert source.last_succeeded_at is None

    attempted = datetime(2026, 6, 8, 12, 0, tzinfo=UTC)
    succeeded = datetime(2026, 6, 8, 12, 5, tzinfo=UTC)
    source.last_attempted_at = attempted
    source.last_succeeded_at = succeeded
    db_session.commit()
    db_session.refresh(source)

    assert source.last_attempted_at == attempted
    assert source.last_succeeded_at == succeeded


# --------------------------------------------------------------------- #
# 8 + 9. Counter defaults + timestamps
# --------------------------------------------------------------------- #


def test_run_counters_default_to_zero(
    make_source: Callable[..., RegulatorySource],
    make_run: Callable[..., RegulatoryIngestionRun],
) -> None:
    source = make_source()
    run = make_run(source)  # no counters passed -> server defaults apply
    assert run.items_seen == 0
    assert run.items_created == 0
    assert run.items_deduped == 0
    assert run.items_failed == 0
    assert run.matches_created == 0
    assert run.alerts_created == 0
    assert run.finished_at is None
    assert run.error_summary is None


def test_run_timestamps_populate_and_update(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
    make_run: Callable[..., RegulatoryIngestionRun],
) -> None:
    source = make_source()
    run = make_run(source)
    assert isinstance(run.created_at, datetime)
    assert isinstance(run.updated_at, datetime)

    # Closing the run out persists a terminal status + finished_at.
    run.status = "succeeded"
    run.finished_at = datetime.now(UTC)
    run.items_seen = 3
    run.items_created = 2
    run.items_deduped = 1
    db_session.commit()
    db_session.refresh(run)
    assert run.status == "succeeded"
    assert run.finished_at is not None
    assert run.items_seen == 3


# --------------------------------------------------------------------- #
# 10. No raw payload / body / secret columns on the item
# --------------------------------------------------------------------- #


def test_item_has_no_raw_payload_or_secret_columns() -> None:
    columns = set(RegulatoryIngestionItem.__table__.columns.keys())
    forbidden = {
        "raw_payload",
        "payload",
        "raw_body",
        "body",
        "raw",
        "secret",
        "api_key",
        "token",
        "authorization",
        "auth_header",
        "credentials",
    }
    assert columns.isdisjoint(forbidden)
    # Expected, security-safe columns only.
    assert columns == {
        "id",
        "run_id",
        "external_ref",
        "content_hash",
        "outcome",
        "notice_id",
        "error_code",
        "error_message",
        "created_at",
    }


# --------------------------------------------------------------------- #
# 11. Additive only — existing regulatory shape unchanged
# --------------------------------------------------------------------- #


def test_source_additions_are_nullable_and_notice_unchanged() -> None:
    source_cols = RegulatorySource.__table__.columns
    for name in (
        "fetch_config",
        "cursor",
        "last_attempted_at",
        "last_succeeded_at",
    ):
        assert source_cols[name].nullable is True

    # source_url was intentionally deferred this subphase: the existing notice
    # read contract is untouched.
    assert "source_url" not in RegulatoryNotice.__table__.columns


# --------------------------------------------------------------------- #
# Cascade + schema hydration
# --------------------------------------------------------------------- #


def test_deleting_run_cascades_to_items(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
    make_run: Callable[..., RegulatoryIngestionRun],
) -> None:
    source = make_source()
    run = make_run(source)
    item = RegulatoryIngestionItem(run_id=run.id, outcome="created")
    db_session.add(item)
    db_session.commit()
    item_id = item.id

    db_session.delete(run)
    db_session.commit()

    assert (
        db_session.scalar(
            select(RegulatoryIngestionItem).where(
                RegulatoryIngestionItem.id == item_id
            )
        )
        is None
    )


def test_read_schemas_hydrate_from_orm(
    db_session: Session,
    make_source: Callable[..., RegulatorySource],
    make_notice: Callable[..., RegulatoryNotice],
    make_run: Callable[..., RegulatoryIngestionRun],
) -> None:
    source = make_source()
    notice = make_notice(source)
    run = make_run(
        source, trigger="manual", status="succeeded", items_created=1
    )
    item = RegulatoryIngestionItem(
        run_id=run.id,
        external_ref="FDA-X-3",
        content_hash=notice.content_hash,
        outcome="created",
        notice_id=notice.id,
    )
    db_session.add(item)
    db_session.commit()
    db_session.refresh(run)
    db_session.refresh(item)

    run_read = RegulatoryIngestionRunRead.model_validate(run)
    assert run_read.trigger is RegulatoryIngestionTrigger.manual
    assert run_read.status is RegulatoryIngestionRunStatus.succeeded
    assert run_read.items_created == 1

    item_read = RegulatoryIngestionItemRead.model_validate(item)
    assert item_read.outcome is RegulatoryIngestionItemOutcome.created
    assert item_read.notice_id == notice.id

    detail = RegulatoryIngestionRunDetailResponse(
        run=run_read, items=[item_read]
    )
    assert detail.run.id == run.id
    assert detail.items[0].id == item.id
