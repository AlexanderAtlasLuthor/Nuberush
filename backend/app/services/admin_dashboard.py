"""Service layer for the admin dashboard aggregator (F2.19.1).

Computes a single `AdminDashboardSummary` from existing tables on
every call. No persistence, no migrations, no model changes — every
field comes from a real query against `Store`, `User`, `InventoryItem`,
`Order`, `Product`, plus the existing global audit feed.

RBAC: admin-only. Non-admin actors → 403 at the service boundary so
direct callers (admin scripts, batch jobs) get the same contract as
the HTTP route. Mirrors the `_assert_admin_caller` style already used
by `app.services.audit`, `app.services.orders.list_admin_orders`, and
`app.services.inventory.list_admin_inventory`.

Read-only contract: no `db.add`, no `db.delete`, no `db.commit`. The
function executes only SELECTs and returns a Pydantic response model.

Bounded tails: recent orders and recent audit are both capped at 5 by
this module. The cap is a service-layer invariant, not a query
parameter; the F2.19.0 contract requires that those tails be bounded
regardless of caller input.

Sources (locked by F2.19.0 §3.1.2):

  - stores.{total,active,inactive}: `Store.is_active`
  - users.{total,active}:           `User.is_active`
  - inventory.low_stock_count:       `quantity_on_hand
                                     - quantity_reserved
                                     <= reorder_threshold`
  - orders.by_status:                group-by on `Order.status`,
                                     dense histogram across every
                                     `OrderStatus` member
  - orders.open_count:               sum over
                                     `{pending, accepted, preparing,
                                       ready, out_for_delivery}`
  - orders.recent:                   `Order.created_at DESC,
                                       Order.id ASC`, limit 5
  - compliance.blocked_count:        `Product.allowed_for_sale = False
                                     OR Product.compliance_status IN
                                       (banned, restricted)`
  - recent_audit:                    existing global audit feed (same
                                     source as `GET /admin/audit`),
                                     limit 5
"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import case
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import Order
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductApprovalStatus
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.admin_dashboard import AdminDashboardComplianceSummary
from app.schemas.admin_dashboard import AdminDashboardInventorySummary
from app.schemas.admin_dashboard import AdminDashboardOrdersSummary
from app.schemas.admin_dashboard import AdminDashboardProductsSummary
from app.schemas.admin_dashboard import AdminDashboardStoresSummary
from app.schemas.admin_dashboard import AdminDashboardSummary
from app.schemas.admin_dashboard import AdminDashboardUsersSummary
from app.schemas.orders import OrderRead
from app.services.audit import list_admin_audit
from app.services.orders import _order_read_load_options


# Bounded tails (F2.19.0 §3.1.2). These are service-owned invariants,
# not caller-tunable knobs.
_RECENT_ORDERS_LIMIT = 5
_RECENT_AUDIT_LIMIT = 5


# Locked "open" status set (F2.19.0 §3.1.2). Matches the same set used
# by the operations alerts contract (§3.2.6 `aging_order`) so the two
# surfaces never drift.
_OPEN_ORDER_STATUSES: frozenset[OrderStatus] = frozenset(
    {
        OrderStatus.pending,
        OrderStatus.accepted,
        OrderStatus.preparing,
        OrderStatus.ready,
        OrderStatus.out_for_delivery,
    }
)


# Locked "blocked from sale" compliance set (F2.19.0 §3.1.2).
_BLOCKING_COMPLIANCE_STATUSES: frozenset[ComplianceStatus] = frozenset(
    {ComplianceStatus.banned, ComplianceStatus.restricted}
)


def _assert_admin_caller(actor: User) -> None:
    """RBAC gate for the admin dashboard.

    Symmetric with `app.services.audit._assert_admin_caller` and
    `list_admin_orders`/`list_admin_inventory`. Local to this module
    by convention — each admin service owns its own RBAC source of
    truth so a future split is mechanical.
    """
    if actor.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )


def _stores_summary(db: Session) -> AdminDashboardStoresSummary:
    """One SQL round-trip for `(total, active, inactive)`.

    Uses conditional aggregates so the three counts come from one
    scan instead of three. Avoids loading any `Store` rows into the
    Python process — the dashboard only needs the cardinalities.
    """
    active_expr = func.coalesce(
        func.sum(case((Store.is_active.is_(True), 1), else_=0)),
        0,
    )
    inactive_expr = func.coalesce(
        func.sum(case((Store.is_active.is_(False), 1), else_=0)),
        0,
    )
    stmt = select(
        func.count(Store.id),
        active_expr,
        inactive_expr,
    )
    total, active, inactive = db.execute(stmt).one()
    return AdminDashboardStoresSummary(
        total=int(total or 0),
        active=int(active or 0),
        inactive=int(inactive or 0),
    )


def _users_summary(db: Session) -> AdminDashboardUsersSummary:
    """One SQL round-trip for `(total, active)`."""
    active_expr = func.coalesce(
        func.sum(case((User.is_active.is_(True), 1), else_=0)),
        0,
    )
    stmt = select(func.count(User.id), active_expr)
    total, active = db.execute(stmt).one()
    return AdminDashboardUsersSummary(
        total=int(total or 0),
        active=int(active or 0),
    )


def _inventory_summary(db: Session) -> AdminDashboardInventorySummary:
    """Low-stock count via the canonical predicate.

    Same expression as the store-scoped `list_inventory_for_store`
    low-stock filter and the operations alerts `low_stock` category,
    so a row that counts here is the same row that would surface as
    an alert later.
    """
    stmt = select(func.count()).select_from(InventoryItem).where(
        InventoryItem.quantity_on_hand - InventoryItem.quantity_reserved
        <= InventoryItem.reorder_threshold
    )
    count = int(db.scalar(stmt) or 0)
    return AdminDashboardInventorySummary(low_stock_count=count)


def _orders_summary(db: Session) -> AdminDashboardOrdersSummary:
    """Group-by histogram + open count + bounded recent tail.

    The histogram is densified to include every `OrderStatus` member
    so the wire shape is predictable (frontend never has to handle a
    missing key). `open_count` is derived from the histogram so the
    two values are guaranteed to agree.

    `recent` is eager-loaded (items → variant → product) via the
    same `_order_read_load_options()` used by `list_admin_orders`,
    keeping serialization free of N+1 lazy reads.
    """
    histogram_stmt = (
        select(Order.status, func.count(Order.id))
        .group_by(Order.status)
    )
    counts_by_status: dict[OrderStatus, int] = {
        status_member: 0 for status_member in OrderStatus
    }
    for row_status, row_count in db.execute(histogram_stmt).all():
        counts_by_status[row_status] = int(row_count)

    open_count = sum(
        counts_by_status[s] for s in _OPEN_ORDER_STATUSES
    )

    recent_stmt = (
        select(Order)
        .options(_order_read_load_options())
        .order_by(Order.created_at.desc(), Order.id.asc())
        .limit(_RECENT_ORDERS_LIMIT)
    )
    recent_rows = list(db.scalars(recent_stmt).all())
    recent_reads = [OrderRead.model_validate(row) for row in recent_rows]

    return AdminDashboardOrdersSummary(
        open_count=open_count,
        by_status=counts_by_status,
        recent=recent_reads,
    )


def _products_summary(db: Session) -> AdminDashboardProductsSummary:
    """Count of store-proposed products awaiting admin review.

    A product counts here when `approval_status = 'pending'`. Rejected
    rows are NOT included (they have already been reviewed). This KPI
    is orthogonal to the compliance one: a pending product can have
    any compliance state — admin sets the final compliance at approval
    time.
    """
    stmt = (
        select(func.count())
        .select_from(Product)
        .where(Product.approval_status == ProductApprovalStatus.pending)
    )
    count = int(db.scalar(stmt) or 0)
    return AdminDashboardProductsSummary(pending_approvals_count=count)


def _compliance_summary(db: Session) -> AdminDashboardComplianceSummary:
    """Count of products blocked from sale.

    Predicate (F2.19.0 §3.1.2):
      `allowed_for_sale = False
       OR compliance_status IN (banned, restricted)`

    Note: the DB CHECK constraint `ck_products_banned_implies_not_allowed_for_sale`
    means every banned product already satisfies `allowed_for_sale = false`,
    so the OR is functionally `allowed_for_sale = false OR
    compliance_status = restricted`. We keep the explicit form for
    clarity and resilience if the constraint is ever relaxed.
    """
    stmt = select(func.count()).select_from(Product).where(
        or_(
            Product.allowed_for_sale.is_(False),
            Product.compliance_status.in_(_BLOCKING_COMPLIANCE_STATUSES),
        )
    )
    count = int(db.scalar(stmt) or 0)
    return AdminDashboardComplianceSummary(blocked_count=count)


def get_admin_dashboard_summary(
    db: Session,
    *,
    actor: User,
) -> AdminDashboardSummary:
    """Build the full dashboard summary for an admin caller.

    Pipeline:
      1. RBAC gate (admin only; 403 otherwise).
      2. Each KPI section is computed independently against the DB.
      3. `recent_audit` is delegated to the existing
         `list_admin_audit` service (limit 5, no other filters) so
         the dashboard never duplicates audit aggregation logic and
         automatically inherits its sort and dedupe semantics.

    Read-only end-to-end. No commits, no writes, no fake fallback
    values. If a section's query genuinely returns zero rows, the
    response reflects that zero.
    """
    _assert_admin_caller(actor)

    stores = _stores_summary(db)
    users = _users_summary(db)
    inventory = _inventory_summary(db)
    orders = _orders_summary(db)
    compliance = _compliance_summary(db)
    products = _products_summary(db)

    audit_response = list_admin_audit(
        db,
        actor=actor,
        limit=_RECENT_AUDIT_LIMIT,
        offset=0,
    )

    return AdminDashboardSummary(
        stores=stores,
        users=users,
        inventory=inventory,
        orders=orders,
        compliance=compliance,
        products=products,
        recent_audit=audit_response.items,
    )
