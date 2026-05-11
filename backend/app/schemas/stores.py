"""Pydantic v2 schemas for the stores module (F2.14).

These schemas are the API contract for store profile reads and the
partial update flow that powers Store Settings.

Design rules baked in:

- StoreRead is the canonical response shape. It mirrors every column
  of `app.db.models.Store` and hydrates from ORM rows via
  `from_attributes=True`.

- StoreUpdate is a strict partial-update payload for
  PATCH /stores/{store_id}. It exposes ONLY the fields F2.14 made
  editable (`name`, `timezone`). `code` and `is_active` are kept
  read-only on purpose: `code` is a unique external identifier that
  other systems can reference, and `is_active` is a lifecycle decision
  owned by admin tooling, not store-level settings.

- `extra="forbid"` rejects any unknown key, including read-only
  columns from `StoreRead` (`id`, `code`, `is_active`, `created_at`,
  `updated_at`). This stops callers from escalating scope by sending
  fields the route would otherwise silently drop.

- All editable string fields are trimmed on input and required to be
  non-empty after trim. Length bounds mirror the DB VARCHAR limits so
  a request that would later fail at the CHECK / VARCHAR layer
  surfaces as a clean 422 instead of an IntegrityError.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field
from pydantic import field_validator


def _strip_optional_required(value: str | None) -> str | None:
    """Trim a value if provided and require it to be non-empty.

    Returns None when the caller did not supply the field — partial
    updates leave such fields untouched. Raises ValueError so Pydantic
    surfaces a clean 422 to the route layer.
    """
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty when provided")
    return stripped


def _strip_required(value: str) -> str:
    """Trim an always-required string and reject empty/whitespace-only."""
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty")
    return stripped


class StoreRead(BaseModel):
    """Response shape for endpoints returning a store profile.

    Mirrors every column of `app.db.models.Store`. Extending the
    surface (address, contact info, business hours, preferences) is
    deliberately deferred and would require a migration first.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    code: str
    is_active: bool
    timezone: str
    created_at: datetime
    updated_at: datetime


class StoreCreate(BaseModel):
    """Admin-only payload for POST /stores (F2.17.1).

    Creates an active store. `is_active` is omitted on purpose — new
    stores are active by default at the DB layer, and lifecycle is
    owned by dedicated `deactivate` / `reactivate` endpoints rather
    than the create payload.

    `code` is exposed here (unlike StoreUpdate) because callers MUST
    supply it at creation. After creation it becomes immutable: a
    unique external identifier that other systems can reference.
    StoreUpdate intentionally does not expose it.

    `extra="forbid"` rejects any field outside (`name`, `code`,
    `timezone`), including read-only columns from StoreRead (`id`,
    `is_active`, `created_at`, `updated_at`) and fields that would
    require a model migration to back (`contact_email`,
    `contact_phone`, `address`, `preferences`, `business_hours`,
    `status`).
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=150)
    code: str = Field(min_length=1, max_length=50)
    timezone: str = Field(
        default="America/New_York", min_length=1, max_length=50
    )

    @field_validator("name", "code", "timezone")
    @classmethod
    def _strip(cls, value: str) -> str:
        return _strip_required(value)


class StoreUpdate(BaseModel):
    """Partial update for the store-settings flow.

    Only `name` and `timezone` are editable. Both are optional so a
    caller may patch one field at a time. Length bounds mirror the
    DB columns (`name` VARCHAR(150), `timezone` VARCHAR(50)).
    """

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=150)
    timezone: str | None = Field(default=None, min_length=1, max_length=50)

    @field_validator("name", "timezone")
    @classmethod
    def _strip_when_present(cls, value: str | None) -> str | None:
        return _strip_optional_required(value)


class StoreListResponse(BaseModel):
    """Paginated response for GET /stores (F2.17.1).

    Mirrors the shape of `UserListResponse` and
    `AuditEventListResponse`: `items` carries the page rows, `total`
    is the pre-pagination count so callers can render totals without
    re-querying.
    """

    items: list[StoreRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)
