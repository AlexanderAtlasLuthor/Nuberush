"""Pydantic v2 schemas for the admin operations alerts feed (F2.19.2).

Wire contract for `GET /admin/operations/alerts`: a paginated,
filterable, **computed-on-request** list of operational issues —
low stock, aging orders, compliance blockers, inactive stores,
stores with no inventory.

Design rules (locked by F2.19.0 §3.2):

- No persistence. Alerts are derived from existing tables on every
  request. There is no `Alert` model, no `alerts` table, no
  acknowledge / dismiss / resolve state.

- `id` is a **deterministic** string with a category-prefixed shape
  so the same operational condition always yields the same id across
  requests (without persistence). The format per category is:

    low_stock           → "low_stock:<inventory_item_id>"
    aging_order         → "aging_order:<order_id>:<aging_minutes>"
    compliance_blocker  → "compliance_blocker:<product_id>"
    inactive_store      → "inactive_store:<store_id>"
    store_no_inventory  → "store_no_inventory:<store_id>"

  The `aging_minutes` suffix on `aging_order` is intentional: the
  alert identity depends on the threshold the caller applied, so
  two callers using different `aging_minutes` see different ids for
  the same order.

- `category`, `severity`, and `entity_type` are string enums (same
  style as `OrderStatus`, `AuditSource`, etc.). FastAPI translates
  unknown values to 422 at the query-param surface.

- `store_id` is nullable. `compliance_blocker` alerts are global
  because `Product` has no `store_id` column in the current model;
  every other category carries a concrete store id.

- Owned wrapper schemas use `ConfigDict(extra="forbid")` to match
  the dashboard schemas' policy (F2.19.1) — a future field addition
  surfaces as a 500 rather than a silent drop.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field


class AdminOperationsAlertCategory(str, enum.Enum):
    """Locked alert category set (F2.19.0 §3.2.2).

    Five categories cover the operational surfaces this phase
    exposes; adding a new category requires a contract update.
    """

    low_stock = "low_stock"
    aging_order = "aging_order"
    compliance_blocker = "compliance_blocker"
    inactive_store = "inactive_store"
    store_no_inventory = "store_no_inventory"


class AdminOperationsAlertSeverity(str, enum.Enum):
    """Locked severity set (F2.19.0 §3.2.3).

    Three discrete levels. The DESC priority `high > medium > low`
    is the first key of the deterministic ordering applied in the
    service layer.
    """

    low = "low"
    medium = "medium"
    high = "high"


class AdminOperationsAlertEntityType(str, enum.Enum):
    """Business entity the alert targets.

    Distinct from `category` because two different categories can
    target the same entity type — `inactive_store` and
    `store_no_inventory` both point at `store`. The entity is the
    "what the operator should click into"; the category is the
    "why."
    """

    store = "store"
    inventory_item = "inventory_item"
    order = "order"
    product = "product"


class AdminOperationsAlert(BaseModel):
    """Single normalized alert row.

    Populated by `app.services.admin_operations.list_admin_operations_alerts`
    from one of the five category generators. The `id` is a
    deterministic string (see module docstring); the `entity_id` is
    the underlying table's row id.
    """

    model_config = ConfigDict(extra="forbid", from_attributes=False)

    id: str = Field(min_length=1)
    category: AdminOperationsAlertCategory
    severity: AdminOperationsAlertSeverity
    store_id: UUID | None
    entity_type: AdminOperationsAlertEntityType
    entity_id: UUID
    summary: str = Field(min_length=1)
    created_at: datetime


class AdminOperationsAlertsListResponse(BaseModel):
    """Paginated response envelope.

    `total` reflects the full filtered count BEFORE pagination is
    applied; `limit` and `offset` echo the request so callers can
    render pagination controls without re-deriving them. Mirrors
    `AuditEventListResponse` / `OrderListResponse` /
    `InventoryItemListResponse`.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[AdminOperationsAlert]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)
