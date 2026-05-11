"""Pydantic v2 schemas for the unified store audit feed (F2.16.1).

These schemas freeze the wire contract for the upcoming store-scoped
audit feed endpoint (`GET /stores/{store_id}/audit`, landing in
F2.16.3). They define a single normalized event shape that the
aggregator service (F2.16.2) will produce from three existing log
tables — `inventory_logs`, `order_audit_logs`, and
`product_compliance_audit_logs` — without any migration or model
change.

Design rules baked in:

- `AuditSource` and `AuditEntityType` are string enums (same style as
  `UserRole`, `ComplianceStatus`, `InventoryStatus`, `OrderStatus` in
  `app.db.models`). Using enums lets the route layer accept them as
  query params with automatic 422 on unknown values.

- `AuditEventRead` is a normalized response shape, not an ORM mapping.
  Rows do not exist on disk in this form; the service layer projects
  inventory/order/compliance log rows into it. `from_attributes=True`
  is still enabled so a service that builds light-weight namespace
  carriers (or, later, a SQLAlchemy mapped view) can hydrate without a
  manual `.model_validate(dict(...))` indirection.

- `action` and `summary` are trimmed and required non-empty. Both
  fields are derived server-side; an empty string here would mean the
  aggregator produced a useless row, which is a bug to surface
  immediately rather than ship to the UI.

- `metadata` defaults to `{}` because the three sources have different
  shapes — an order transition row has `previous_status`/`new_status`
  while an inventory row has `quantity_delta`/`quantity_after`. The
  aggregator may also pass an empty dict for an event whose
  source-specific fields are uninteresting; making the field required
  would force callers to fabricate empties anyway.

- Read schemas in this repo do NOT set `extra="forbid"` (see
  `InventoryLogRead`, `OrderAuditLogRead`, `StoreRead`, `UserRead`).
  Audit responses follow the same convention: extra ORM attributes on
  the source object are silently dropped during `from_attributes`
  hydration, which is the right behavior for read-only projections.

- `AuditEventListResponse` mirrors `UserListResponse` /
  `InventoryItemListResponse`: bare list + total/limit/offset bounds.
  Filters and query params live with the route schema in F2.16.3, not
  here.

This module deliberately does NOT resolve the
`product_compliance_audit_logs`-to-store_id join. The compliance table
has no `store_id` column; the aggregator service (F2.16.2) owns the
join contract and is the only place that knows how a compliance row
maps to a requested store_id. Schemas merely accept the resolved
value.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator


class AuditSource(str, enum.Enum):
    """Source table that produced an audit event.

    Locked set — adding a new source means extending the aggregator
    service AND this enum in lockstep.
    """

    inventory = "inventory"
    order = "order"
    product_compliance = "product_compliance"


class AuditEntityType(str, enum.Enum):
    """Business entity the event targets.

    Distinct from `AuditSource` because the source identifies the
    underlying log table while the entity identifies what the operator
    is reasoning about. An inventory event targets an `inventory_item`;
    an order event targets an `order`; a compliance event targets a
    `product`.
    """

    inventory_item = "inventory_item"
    order = "order"
    product = "product"


def _strip_required(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty")
    return stripped


class AuditEventRead(BaseModel):
    """Unified projection of one audit row across all three sources.

    Populated by the aggregator service (F2.16.2). `store_id` and
    `actor_id` are nullable because:
      - admin/global queries may produce events whose `store_id` was
        resolved post-aggregation (today every event scopes to one
        store, but the contract allows future global rows);
      - `actor_id` is null for any log row whose `performed_by_user_id`
        / `changed_by_user_id` was unset at write time, or whose actor
        was later soft-deleted (the FK uses `ON DELETE SET NULL`).
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source: AuditSource
    store_id: UUID | None
    actor_id: UUID | None
    action: str = Field(min_length=1)
    entity_type: AuditEntityType
    entity_id: UUID
    summary: str = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @field_validator("action")
    @classmethod
    def _strip_action(cls, value: str) -> str:
        return _strip_required(value)

    @field_validator("summary")
    @classmethod
    def _strip_summary(cls, value: str) -> str:
        return _strip_required(value)


class AuditEventListResponse(BaseModel):
    """Paginated response envelope for the store audit feed.

    `total` reflects the full merged + filtered row count BEFORE
    pagination is applied — the slicing rule lives in the aggregator
    service. `limit` and `offset` echo the request so the UI can render
    pagination controls without re-deriving them.
    """

    items: list[AuditEventRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
