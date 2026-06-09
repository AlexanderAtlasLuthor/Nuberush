"""Pydantic v2 read schemas for the regulatory ingestion ledger (F2.27.7.B).

These freeze the wire contract for the ingestion observability surface — the
runs and per-item outcomes recorded by the future orchestrator (F2.27.7.C).
This subphase ships the schemas only: NO route consumes them yet.

Design rules mirror `app.schemas.regulatory`:

- `trigger` / `status` / `outcome` are closed value sets defined HERE as str
  enums, not in the ORM: the DB columns are `varchar` discriminators guarded
  by CHECK constraints (no PG enum), so the closed sets are a validation
  concern that lives with the schemas — exactly like `RegulatoryDecisionAction`.
- Read schemas use `from_attributes=True` and do NOT set `extra="forbid"`,
  following the repo convention for read-only projections (extra ORM attributes
  are silently dropped). The varchar columns hydrate into these enums.
- List/detail envelopes match the paginated shape used across the regulatory
  schemas (`items` / `total` / `limit` / `offset`).
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


__all__ = [
    "RegulatoryIngestionTrigger",
    "RegulatoryIngestionRunStatus",
    "RegulatoryIngestionItemOutcome",
    "RegulatoryIngestionTriggerRequest",
    "RegulatoryIngestionItemRead",
    "RegulatoryIngestionRunRead",
    "RegulatoryIngestionRunListResponse",
    "RegulatoryIngestionRunDetailResponse",
]


class RegulatoryIngestionTrigger(str, enum.Enum):
    """How an ingestion run was started.

    Only `manual` is produced in F2.27.7; `scheduled` is future-ready for a
    later scheduler slice (no scheduler exists yet).
    """

    manual = "manual"
    scheduled = "scheduled"


class RegulatoryIngestionRunStatus(str, enum.Enum):
    """Lifecycle of an ingestion run.

    `running` while in flight; one of `succeeded` / `failed` / `partial` once
    finished. No status here implies any product/alert mutation — the ledger
    is observability only.
    """

    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    partial = "partial"


class RegulatoryIngestionItemOutcome(str, enum.Enum):
    """What one source item became during a run.

    `created` → a new notice was persisted; `deduped` → an existing
    `(source_id, content_hash)` was reused; `failed` → a parse/persist error.
    """

    created = "created"
    deduped = "deduped"
    failed = "failed"


class RegulatoryIngestionTriggerRequest(BaseModel):
    """Body for the admin manual-ingest trigger (F2.27.7.C).

    Both flags default True so the common case runs the full advisory pipeline
    (ingest → detect matches → create alerts). Setting `create_alerts=True`
    with `detect_matches=False` is a no-op for alerts: alerts are generated from
    matches, so disabling matching disables alert creation too. `extra="forbid"`
    surfaces a stray field as 422.
    """

    model_config = ConfigDict(extra="forbid")

    detect_matches: bool = True
    create_alerts: bool = True


class RegulatoryIngestionItemRead(BaseModel):
    """Response shape for one per-item ingestion outcome (append-only).

    Carries no raw payload/body, secret, or auth header — only the stable
    `external_ref`, the `content_hash`, the `outcome`, an optional `notice_id`
    (set for created/deduped), and a short machine `error_code` + human
    `error_message`.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    run_id: UUID
    external_ref: str | None
    content_hash: str | None
    outcome: RegulatoryIngestionItemOutcome
    notice_id: UUID | None
    error_code: str | None
    error_message: str | None
    created_at: datetime


class RegulatoryIngestionRunRead(BaseModel):
    """Response shape for one ingestion run (the ledger header).

    `actor_user_id` is nullable: a `scheduled` run has no human actor. The
    counters are rolled-up totals for the run; `finished_at` / `error_summary`
    are populated once the run reaches a terminal status.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    trigger: RegulatoryIngestionTrigger
    status: RegulatoryIngestionRunStatus
    started_at: datetime
    finished_at: datetime | None
    items_seen: int
    items_created: int
    items_deduped: int
    items_failed: int
    matches_created: int
    alerts_created: int
    error_summary: str | None
    actor_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class RegulatoryIngestionRunListResponse(BaseModel):
    """Paginated envelope for ingestion runs."""

    items: list[RegulatoryIngestionRunRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class RegulatoryIngestionRunDetailResponse(BaseModel):
    """A single run plus its per-item outcomes (the run detail view)."""

    run: RegulatoryIngestionRunRead
    items: list[RegulatoryIngestionItemRead]
