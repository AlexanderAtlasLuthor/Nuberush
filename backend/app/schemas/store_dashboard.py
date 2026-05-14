"""Pydantic v2 schemas for the store-scoped dashboard surfaces.

Wire contracts for the seven `GET /stores/{store_id}/...` endpoints
that back the store operations dashboard:

  GET /stores/{store_id}/dashboard
  GET /stores/{store_id}/dashboard/kpis
  GET /stores/{store_id}/orders/summary
  GET /stores/{store_id}/inventory/summary
  GET /stores/{store_id}/products/summary
  GET /stores/{store_id}/activity
  GET /stores/{store_id}/alerts

Design rules (mirrored from `app.schemas.admin_dashboard` /
`app.schemas.admin_operations`):

- No persistence. Every value is computed on request from existing
  tables (`Store`, `InventoryItem`, `InventoryLog`, `Order`,
  `OrderAuditLog`, `Product`, `ProductVariant`).

- Aggregate-only payloads: counts, dense histograms, bounded recent
  tails. Never the full list of underlying rows — list endpoints
  already exist for that (inventory, orders, products, audit).

- `orders.by_status` is a dense `Mapping[OrderStatus, int]`. The
  service guarantees every `OrderStatus` member is present (zeros for
  empty buckets), so the frontend never has to handle a missing key.

- Owned wrappers use `ConfigDict(extra="forbid")` so a future field
  addition surfaces as a 500 rather than a silent drop. Leaf schemas
  re-used from other modules (`OrderRead`, `AuditEventRead`) keep
  their existing policies.

- `recent_*` tails are bounded by the service, not by Pydantic. The
  bound is a service-layer invariant, not a query parameter.
"""

from __future__ import annotations

import enum
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.db.models import OrderStatus
from app.schemas.audit import AuditEventRead
from app.schemas.orders import OrderRead


# --------------------------------------------------------------------- #
# Section payloads
# --------------------------------------------------------------------- #


class StoreOrdersSummary(BaseModel):
    """Order KPIs scoped to one store.

    - `open_count`: orders in `{pending, accepted, preparing, ready,
      out_for_delivery}` for this store.
    - `by_status`: dense histogram across every `OrderStatus` member.
    - `recent`: bounded tail (5), ordered `created_at DESC`.
    """

    model_config = ConfigDict(extra="forbid")

    open_count: int = Field(ge=0)
    by_status: dict[OrderStatus, int]
    recent: list[OrderRead]


class StoreInventorySummary(BaseModel):
    """Inventory KPIs scoped to one store.

    - `total_items`: count of `InventoryItem` rows for this store.
    - `low_stock_count`: rows where
      `quantity_on_hand - quantity_reserved <= reorder_threshold`.
    - `total_on_hand` / `total_reserved`: sum of those columns across
      the store's inventory items.
    """

    model_config = ConfigDict(extra="forbid")

    total_items: int = Field(ge=0)
    low_stock_count: int = Field(ge=0)
    total_on_hand: int = Field(ge=0)
    total_reserved: int = Field(ge=0)


class StoreProductsSummary(BaseModel):
    """Product KPIs scoped to one store.

    `Product` is global (no `store_id` column), so the "in store" count
    is the number of DISTINCT products that have at least one
    `InventoryItem` row for this store. `blocked_count` is the subset
    of those products that are blocked from sale by the canonical
    predicate (`allowed_for_sale = false OR compliance_status IN
    (banned, restricted)`).
    """

    model_config = ConfigDict(extra="forbid")

    in_store_count: int = Field(ge=0)
    blocked_count: int = Field(ge=0)


class StoreDashboardKpis(BaseModel):
    """Headline KPI bundle.

    Numbers only — no recent tails. The dashboard endpoint wraps this
    alongside the bounded recent surfaces in `StoreDashboardSummary`.
    """

    model_config = ConfigDict(extra="forbid")

    orders_open: int = Field(ge=0)
    orders_by_status: dict[OrderStatus, int]
    inventory_total_items: int = Field(ge=0)
    inventory_low_stock: int = Field(ge=0)
    products_in_store: int = Field(ge=0)
    products_blocked: int = Field(ge=0)


class StoreDashboardSummary(BaseModel):
    """Top-level response for `GET /stores/{store_id}/dashboard`."""

    model_config = ConfigDict(extra="forbid")

    store_id: UUID
    kpis: StoreDashboardKpis
    orders: StoreOrdersSummary
    inventory: StoreInventorySummary
    products: StoreProductsSummary
    recent_activity: list[AuditEventRead]


# --------------------------------------------------------------------- #
# Activity feed
# --------------------------------------------------------------------- #


class StoreActivityListResponse(BaseModel):
    """Paginated response envelope for the store activity feed.

    Re-uses `AuditEventRead` (the same projection backing the audit
    feed). The activity surface is the audit feed scoped to one store
    with no source / entity filters — the frontend can drill into the
    full audit page for filtering.
    """

    model_config = ConfigDict(extra="forbid")

    items: list[AuditEventRead]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


# --------------------------------------------------------------------- #
# Alerts
# --------------------------------------------------------------------- #


class StoreAlertCategory(str, enum.Enum):
    """Locked store-alert category set.

    Subset of the admin operations alerts that make sense at a single
    store boundary. `compliance_blocker` and `inactive_store` are
    admin-only because a store can't act on its own deactivation, and
    `Product` is global.
    """

    low_stock = "low_stock"
    aging_order = "aging_order"
    no_inventory = "no_inventory"


class StoreAlertSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class StoreAlertEntityType(str, enum.Enum):
    store = "store"
    inventory_item = "inventory_item"
    order = "order"


class StoreAlert(BaseModel):
    """Single normalized alert row scoped to one store.

    `id` is a deterministic string so the same operational condition
    yields the same id across requests without persistence:

      low_stock     → "low_stock:<inventory_item_id>"
      aging_order   → "aging_order:<order_id>:<aging_minutes>"
      no_inventory  → "no_inventory:<store_id>"
    """

    model_config = ConfigDict(extra="forbid", from_attributes=False)

    id: str = Field(min_length=1)
    category: StoreAlertCategory
    severity: StoreAlertSeverity
    store_id: UUID
    entity_type: StoreAlertEntityType
    entity_id: UUID
    summary: str = Field(min_length=1)
    created_at: datetime


class StoreAlertsListResponse(BaseModel):
    """Paginated response envelope for store alerts."""

    model_config = ConfigDict(extra="forbid")

    items: list[StoreAlert]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)
