"""Pydantic v2 schemas for the admin dashboard aggregator (F2.19.1).

Wire contract for `GET /admin/dashboard`: a single aggregate response
that bundles store / user / inventory / order / compliance KPIs with
two bounded recent tails (recent orders, recent audit events).

All sub-sections are computed server-side from existing tables — no
new persistence, no migrations, no model changes. The schemas here are
response-only wrappers; the canonical projections for nested rows
(`OrderRead`, `AuditEventRead`) are reused from their owning modules
so the dashboard never diverges from those contracts.

Design rules:

- Six aggregate sections (one per KPI cluster) compose
  `AdminDashboardSummary`. Each is a separate `BaseModel` so callers
  can refer to a single section in isolation when needed (typing,
  mocks, etc.).

- `orders.by_status` is a `Mapping[OrderStatus, int]`. The service
  layer guarantees the dict contains every `OrderStatus` member
  (zeros for statuses with no rows), so the contract surface is
  predictable for the frontend.

- `orders.recent` and `recent_audit` are bounded to 5 by the service.
  The Pydantic schema doesn't enforce that bound — it would be a lie
  to enforce it here and not at the source — but the field types
  match the canonical read schemas exactly.

- All sub-models forbid extra attributes (`extra="forbid"`) so a
  miswired service or a future addition surfaces as a 500 rather
  than a silent field drop. The audit `AuditEventRead` schema does
  NOT forbid extras (it's a read projection over heterogeneous
  sources), so we keep that policy at the leaf and only forbid
  extras on the dashboard-owned wrappers.
"""

from __future__ import annotations

from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import Field

from app.db.models import OrderStatus
from app.schemas.audit import AuditEventRead
from app.schemas.orders import OrderRead


class AdminDashboardStoresSummary(BaseModel):
    """Store population counts (from `Store.is_active`)."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    active: int = Field(ge=0)
    inactive: int = Field(ge=0)


class AdminDashboardUsersSummary(BaseModel):
    """User population counts (from `User.is_active`)."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    active: int = Field(ge=0)


class AdminDashboardInventorySummary(BaseModel):
    """Inventory KPIs derived from the low-stock predicate.

    Predicate: `quantity_on_hand - quantity_reserved <= reorder_threshold`.
    """

    model_config = ConfigDict(extra="forbid")

    low_stock_count: int = Field(ge=0)


class AdminDashboardOrdersSummary(BaseModel):
    """Order KPIs: open count, full status histogram, recent tail.

    - `open_count`: orders in `{pending, accepted, preparing, ready,
      out_for_delivery}`.
    - `by_status`: every `OrderStatus` member with its count (zeros
      included for empty buckets).
    - `recent`: bounded to 5, ordered by `created_at DESC`.
    """

    model_config = ConfigDict(extra="forbid")

    open_count: int = Field(ge=0)
    by_status: dict[OrderStatus, int]
    recent: list[OrderRead]


class AdminDashboardComplianceSummary(BaseModel):
    """Compliance KPI: products currently blocked from sale.

    A product counts as blocked when `allowed_for_sale = false` OR
    `compliance_status` is in the blocking set (`banned`, `restricted`).
    """

    model_config = ConfigDict(extra="forbid")

    blocked_count: int = Field(ge=0)


class AdminDashboardProductsSummary(BaseModel):
    """Catalog-curation KPI: store-proposed products awaiting review.

    Independent from compliance: a row counts here as long as
    `approval_status = 'pending'`, regardless of its compliance state.
    """

    model_config = ConfigDict(extra="forbid")

    pending_approvals_count: int = Field(ge=0)


class AdminDashboardRegulatorySummary(BaseModel):
    """Regulatory KPI: high-level global counts over `compliance_alerts`.

    A flattened, dashboard-friendly projection of the canonical
    `ComplianceAlertAggregate` (F2.27.5), computed server-side with NO
    filters (the dashboard reports the whole universe of alerts):

    - `total_alerts`:           every compliance alert, all statuses.
    - `open_count`:             alerts in status `open`.
    - `high_or_critical_count`: alerts with severity `high` OR `critical`.
    - `hold_or_ban_count`:      alerts recommending `hold` OR `ban`.

    Each value is derived from the same dense-by-enum aggregate the
    `/admin/regulatory/aggregate` endpoint exposes, so the dashboard tile and
    the regulatory page never drift. Read-only; never reproduces the alert
    lifecycle predicates client-side.
    """

    model_config = ConfigDict(extra="forbid")

    total_alerts: int = Field(ge=0)
    open_count: int = Field(ge=0)
    high_or_critical_count: int = Field(ge=0)
    hold_or_ban_count: int = Field(ge=0)


class AdminDashboardSummary(BaseModel):
    """Top-level response for `GET /admin/dashboard`.

    Bundles every KPI section plus the bounded recent audit tail.
    Read-only, admin-only, computed-on-request. No persistence layer
    backs this shape; the service layer derives every value from
    existing tables on every call.
    """

    model_config = ConfigDict(extra="forbid")

    stores: AdminDashboardStoresSummary
    users: AdminDashboardUsersSummary
    inventory: AdminDashboardInventorySummary
    orders: AdminDashboardOrdersSummary
    compliance: AdminDashboardComplianceSummary
    products: AdminDashboardProductsSummary
    regulatory: AdminDashboardRegulatorySummary
    recent_audit: list[AuditEventRead]
