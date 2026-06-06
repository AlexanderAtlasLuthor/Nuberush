"""Pydantic v2 schemas for the Regulatory Intelligence Foundation (F2.26.5.A).

These schemas freeze the wire contract for the backend-first regulatory
compliance domain — sources, imported notices/snapshots, best-effort product
matches, human-reviewable compliance alerts, and the append-only decision
audit trail. This subphase ships the data model only: NO API route consumes
these yet, and no ingestion / matching / resolution service exists.

Design rules baked in (mirroring `app.schemas.products` and
`app.schemas.audit`):

- The constrained domain/state enums (`RegulatorySourceKind`,
  `RegulatoryNoticeType`, `RegulatoryMatchStrategy`,
  `ComplianceAlertSeverity`, `ComplianceAlertStatus`,
  `ComplianceRecommendedAction`) are the SAME objects the ORM uses — they are
  re-exported from `app.db.models`, exactly as `app.schemas.store_applications`
  re-exports `StoreApplicationStatus`. Using them as field types gives
  automatic 422 on unknown values at the (future) route layer.

- `RegulatoryDecisionAction` is defined HERE, not in the models: the decision
  audit `action` column is a `varchar` discriminator (no PG enum), matching
  every other append-only audit table in the repo. The closed verb set is a
  validation concern, so it lives with the schemas that enforce it.

- Create/request schemas set `extra="forbid"` and validate required
  non-empty strings (a stray field or a blank required string is a client
  bug we surface as 422). Read schemas use `from_attributes=True` and do NOT
  set `extra="forbid"`, following the repo convention (`ProductRead`,
  `UserRead`, `AuditEventRead`): extra ORM attributes are silently dropped
  during hydration, which is correct for read-only projections.

- `confidence` is a `Decimal` bounded 0.00–1.00, mirroring the DB CHECK and
  NUMERIC(3, 2) column.

- `payload` / `matched_fields` / `before` / `after` / `metadata` are free-form
  JSON objects (`dict[str, Any]`); the service layer that produces them owns
  their internal shape.
"""

from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from typing import Any
from uuid import UUID

from pydantic import AliasChoices
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator

# Re-export the ORM enums so callers import the regulatory enum surface from
# one place. These are the SAME objects bound to the PostgreSQL enum columns.
from app.db.models import ComplianceAlertSeverity
from app.db.models import ComplianceAlertStatus
from app.db.models import ComplianceRecommendedAction
from app.db.models import RegulatoryMatchStrategy
from app.db.models import RegulatoryNoticeType
from app.db.models import RegulatorySourceKind


__all__ = [
    "ComplianceAlertSeverity",
    "ComplianceAlertStatus",
    "ComplianceRecommendedAction",
    "RegulatoryMatchStrategy",
    "RegulatoryNoticeType",
    "RegulatorySourceKind",
    "RegulatoryDecisionAction",
    "RegulatorySourceCreate",
    "RegulatorySourceRead",
    "RegulatorySourceListResponse",
    "RegulatoryNoticeCreate",
    "RegulatoryNoticeIngestRequest",
    "RegulatoryNoticeRead",
    "RegulatoryNoticeListResponse",
    "RegulatoryProductMatchCreate",
    "RegulatoryProductMatchRead",
    "RegulatoryProductMatchListResponse",
    "ComplianceAlertRead",
    "ComplianceAlertListResponse",
    "ComplianceAlertResolutionAction",
    "ComplianceAlertActionRequest",
    "ComplianceAlertResolveRequest",
    "RegulatoryDecisionAuditLogRead",
    "RegulatoryDecisionAuditLogListResponse",
]


class RegulatoryDecisionAction(str, enum.Enum):
    """Closed verb set for a regulatory decision audit row.

    The DB column is a plain `varchar` (no PG enum), so this enum is the
    authoritative validation surface for the decision taxonomy — extending it
    never requires a migration.
    """

    alert_acknowledged = "alert_acknowledged"
    alert_dismissed = "alert_dismissed"
    alert_resolved_hold = "alert_resolved_hold"
    alert_resolved_ban = "alert_resolved_ban"
    alert_resolved_no_action = "alert_resolved_no_action"


# Confidence mirrors the DB: NUMERIC(3, 2) bounded to [0, 1] by a CHECK.
Confidence = Annotated[
    Decimal,
    Field(ge=0, le=1, max_digits=3, decimal_places=2),
]


def _strip_required(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty")
    return stripped


def _strip_optional(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty when provided")
    return stripped


# --------------------------------------------------------------------- #
# Regulatory source
# --------------------------------------------------------------------- #


class RegulatorySourceCreate(BaseModel):
    """Payload to register a regulatory source.

    `last_synced_at` is intentionally absent — it is bookkeeping owned by a
    future ingestion service, never client-supplied.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=150)
    kind: RegulatorySourceKind
    reference_url: str | None = Field(default=None, max_length=500)
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("reference_url")
    @classmethod
    def _strip_reference_url(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class RegulatorySourceRead(BaseModel):
    """Response shape for a regulatory source."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    kind: RegulatorySourceKind
    reference_url: str | None
    is_active: bool
    last_synced_at: datetime | None
    created_at: datetime
    updated_at: datetime


class RegulatorySourceListResponse(BaseModel):
    """Paginated envelope for regulatory sources."""

    items: list[RegulatorySourceRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


# --------------------------------------------------------------------- #
# Regulatory notice
# --------------------------------------------------------------------- #


class RegulatoryNoticeCreate(BaseModel):
    """Payload to import a regulatory notice/snapshot.

    `content_hash` is supplied by the importer and backs the
    `(source_id, content_hash)` dedupe uniqueness at the DB layer.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    external_ref: str | None = Field(default=None, max_length=255)
    title: str = Field(min_length=1, max_length=300)
    notice_type: RegulatoryNoticeType
    published_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
    content_hash: str = Field(min_length=1, max_length=64)

    @field_validator("title", "content_hash")
    @classmethod
    def _strip_required_fields(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("external_ref")
    @classmethod
    def _strip_external_ref(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class RegulatoryNoticeIngestRequest(BaseModel):
    """Payload to manually ingest a regulatory notice (F2.26.5.B).

    Unlike `RegulatoryNoticeCreate`, this request carries NO `content_hash`:
    the ingestion service computes a stable, order-insensitive hash from the
    notice fields + payload and uses it for `(source_id, content_hash)`
    dedupe. Re-ingesting the same semantic content is idempotent — it returns
    the existing notice rather than creating a duplicate.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    external_ref: str | None = Field(default=None, max_length=255)
    title: str = Field(min_length=1, max_length=300)
    notice_type: RegulatoryNoticeType
    published_at: datetime | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("title")
    @classmethod
    def _strip_title(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("external_ref")
    @classmethod
    def _strip_external_ref(cls, value: str | None) -> str | None:
        return _strip_optional(value)


class RegulatoryNoticeRead(BaseModel):
    """Response shape for a regulatory notice (append-only: no updated_at)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    external_ref: str | None
    title: str
    notice_type: RegulatoryNoticeType
    published_at: datetime | None
    payload: dict[str, Any]
    content_hash: str
    created_at: datetime


class RegulatoryNoticeListResponse(BaseModel):
    """Paginated envelope for regulatory notices."""

    items: list[RegulatoryNoticeRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


# --------------------------------------------------------------------- #
# Regulatory product match
# --------------------------------------------------------------------- #


class RegulatoryProductMatchCreate(BaseModel):
    """Payload to record a best-effort notice↔product match candidate."""

    model_config = ConfigDict(extra="forbid")

    notice_id: UUID
    product_id: UUID
    variant_id: UUID | None = None
    match_strategy: RegulatoryMatchStrategy
    confidence: Confidence
    matched_fields: dict[str, Any] = Field(default_factory=dict)


class RegulatoryProductMatchRead(BaseModel):
    """Response shape for a regulatory product match (append-only)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    notice_id: UUID
    product_id: UUID
    variant_id: UUID | None
    match_strategy: RegulatoryMatchStrategy
    confidence: Confidence
    matched_fields: dict[str, Any]
    created_at: datetime


class RegulatoryProductMatchListResponse(BaseModel):
    """Paginated envelope for regulatory product matches."""

    items: list[RegulatoryProductMatchRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


# --------------------------------------------------------------------- #
# Compliance alert
# --------------------------------------------------------------------- #


class ComplianceAlertRead(BaseModel):
    """Response shape for a human-reviewable compliance alert.

    Advisory only: `recommended_action` is a suggestion, never an applied
    mutation. `product_id` / `match_id` are nullable (notice-level alerts and
    non-match-generated alerts respectively); the `resolved_*` fields are set
    together only once an admin closes the alert.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    notice_id: UUID
    product_id: UUID | None
    match_id: UUID | None
    severity: ComplianceAlertSeverity
    status: ComplianceAlertStatus
    recommended_action: ComplianceRecommendedAction
    resolution_note: str | None
    resolved_by_user_id: UUID | None
    resolved_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ComplianceAlertListResponse(BaseModel):
    """Paginated envelope for compliance alerts."""

    items: list[ComplianceAlertRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class ComplianceAlertResolutionAction(str, enum.Enum):
    """The terminal `resolve` actions an admin may take on a compliance alert.

    `no_action` closes the alert as reviewed-but-no-change. `hold` and `ban`
    additionally apply a real compliance change to the product — exclusively
    through the existing `set_product_compliance()` service (never a direct
    Product write). `dismiss` is a separate lifecycle verb, not a resolution,
    so it is intentionally absent here.
    """

    no_action = "no_action"
    hold = "hold"
    ban = "ban"


class ComplianceAlertActionRequest(BaseModel):
    """Payload for the non-resolving lifecycle verbs (acknowledge / dismiss).

    `reason` is required and non-empty: it is the human justification recorded
    on the `regulatory_decision_audit_logs` row (and, for dismiss, also stored
    as the alert's `resolution_note`). The acting admin is threaded separately
    by the (future) route layer, not carried in this body.
    """

    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=2000)

    @field_validator("reason")
    @classmethod
    def _strip_reason(cls, value: str) -> str:
        return _strip_required(value)


class ComplianceAlertResolveRequest(BaseModel):
    """Payload for resolving an alert (no_action / hold / ban).

    `resolution_note` is required and non-empty: it is stored on the alert and
    folded into both the regulatory decision audit reason and — for hold/ban —
    the `set_product_compliance()` reason so the product compliance trail
    carries regulatory provenance.
    """

    model_config = ConfigDict(extra="forbid")

    action: ComplianceAlertResolutionAction
    resolution_note: str = Field(min_length=1, max_length=2000)

    @field_validator("resolution_note")
    @classmethod
    def _strip_resolution_note(cls, value: str) -> str:
        return _strip_required(value)


# --------------------------------------------------------------------- #
# Regulatory decision audit log
# --------------------------------------------------------------------- #


class RegulatoryDecisionAuditLogRead(BaseModel):
    """Response shape for an append-only regulatory decision audit row.

    `action` is validated against the closed `RegulatoryDecisionAction` set.
    The `metadata` field hydrates from the ORM attribute `event_metadata`
    (the column is named `metadata`; the attribute is renamed to avoid the
    reserved `Base.metadata`) — `AliasChoices` accepts either key so the
    schema validates from both the ORM object and a plain dict.
    """

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: UUID
    alert_id: UUID
    notice_id: UUID
    product_id: UUID | None
    actor_user_id: UUID
    action: RegulatoryDecisionAction
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = Field(
        default=None,
        validation_alias=AliasChoices("metadata", "event_metadata"),
        serialization_alias="metadata",
    )
    reason: str
    created_at: datetime


class RegulatoryDecisionAuditLogListResponse(BaseModel):
    """Paginated envelope for regulatory decision audit logs."""

    items: list[RegulatoryDecisionAuditLogRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
