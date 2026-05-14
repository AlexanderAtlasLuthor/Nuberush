"""Service layer for the store-scoped dashboard surfaces.

Computes every value on request from existing tables — no persistence,
no migrations, no model changes. Mirrors the admin dashboard /
operations services (F2.19) in style, scoped to a single store.

Backing endpoints (HTTP layer):

  GET /stores/{store_id}/dashboard          → get_store_dashboard_summary
  GET /stores/{store_id}/dashboard/kpis     → get_store_dashboard_kpis
  GET /stores/{store_id}/orders/summary     → get_store_orders_summary
  GET /stores/{store_id}/inventory/summary  → get_store_inventory_summary
  GET /stores/{store_id}/products/summary   → get_store_products_summary
  GET /stores/{store_id}/activity           → list_store_activity
  GET /stores/{store_id}/alerts             → list_store_alerts

Conventions:

- Read-only end-to-end. No `db.add`, `db.delete`, `db.commit`.
- The route layer enforces tenancy via `require_store_member`. The
  service trusts that gate and does not re-derive it.
- Bounded tails (recent orders, recent activity) cap at 5 here. The
  cap is a service invariant, not a query parameter.
- "open" order status set and "blocked from sale" compliance set
  match the admin dashboard so the two surfaces never drift.
- "low stock" predicate matches `app.services.admin_dashboard` /
  `list_inventory_for_store`: row counts here iff it would surface
  via the existing low-stock filters.
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from datetime import timedelta
from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import and_
from sqlalchemy import case
from sqlalchemy import distinct
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import Order
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import Store
from app.schemas.audit import AuditEventListResponse
from app.schemas.audit import AuditEventRead
from app.schemas.orders import OrderRead
from app.schemas.store_dashboard import StoreAlert
from app.schemas.store_dashboard import StoreAlertCategory
from app.schemas.store_dashboard import StoreAlertEntityType
from app.schemas.store_dashboard import StoreAlertSeverity
from app.schemas.store_dashboard import StoreAlertsListResponse
from app.schemas.store_dashboard import StoreActivityListResponse
from app.schemas.store_dashboard import StoreDashboardKpis
from app.schemas.store_dashboard import StoreDashboardSummary
from app.schemas.store_dashboard import StoreInventorySummary
from app.schemas.store_dashboard import StoreOrdersSummary
from app.schemas.store_dashboard import StoreProductsSummary


# Service-owned invariants.
_RECENT_ORDERS_LIMIT = 5
_RECENT_ACTIVITY_LIMIT = 5

# Pagination bounds for list_store_activity / list_store_alerts.
# Mirror the Query(ge=, le=) the routes encode so direct callers
# (admin scripts, tests) get the same contract.
_LIMIT_MIN = 1
_LIMIT_MAX = 200
_OFFSET_MIN = 0
_AGING_MINUTES_MIN = 1
_AGING_MINUTES_DEFAULT = 60

_OPEN_ORDER_STATUSES: frozenset[OrderStatus] = frozenset(
    {
        OrderStatus.pending,
        OrderStatus.accepted,
        OrderStatus.preparing,
        OrderStatus.ready,
        OrderStatus.out_for_delivery,
    }
)

_BLOCKING_COMPLIANCE_STATUSES: frozenset[ComplianceStatus] = frozenset(
    {ComplianceStatus.banned, ComplianceStatus.restricted}
)

_SEVERITY_PRIORITY: dict[StoreAlertSeverity, int] = {
    StoreAlertSeverity.high: 3,
    StoreAlertSeverity.medium: 2,
    StoreAlertSeverity.low: 1,
}


# --------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------- #


def _validate_pagination(limit: int, offset: int) -> None:
    if limit < _LIMIT_MIN or limit > _LIMIT_MAX:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"limit must be between {_LIMIT_MIN} and {_LIMIT_MAX}."
            ),
        )
    if offset < _OFFSET_MIN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="offset must be >= 0.",
        )


def _validate_aging_minutes(aging_minutes: int) -> None:
    if aging_minutes < _AGING_MINUTES_MIN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"aging_minutes must be >= {_AGING_MINUTES_MIN}.",
        )


def _ensure_store_exists(db: Session, store_id: UUID) -> Store:
    """Defense in depth: the route's `require_store_member` already
    rejected unknown / inactive stores for non-admins, but the service
    is also called by tests and admin scripts. Surface a clean 404 if
    the store is missing rather than letting downstream queries return
    empty silently.
    """
    store = db.scalar(select(Store).where(Store.id == store_id))
    if store is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found.",
        )
    return store


# --------------------------------------------------------------------- #
# Section computations
# --------------------------------------------------------------------- #


def _orders_summary(db: Session, store_id: UUID) -> StoreOrdersSummary:
    """Dense `(status -> count)` + open total + bounded recent tail."""
    from app.services.orders import _order_read_load_options

    histogram_stmt = (
        select(Order.status, func.count(Order.id))
        .where(Order.store_id == store_id)
        .group_by(Order.status)
    )
    counts_by_status: dict[OrderStatus, int] = {
        s: 0 for s in OrderStatus
    }
    for row_status, row_count in db.execute(histogram_stmt).all():
        counts_by_status[row_status] = int(row_count)

    open_count = sum(counts_by_status[s] for s in _OPEN_ORDER_STATUSES)

    recent_stmt = (
        select(Order)
        .where(Order.store_id == store_id)
        .options(_order_read_load_options())
        .order_by(Order.created_at.desc(), Order.id.asc())
        .limit(_RECENT_ORDERS_LIMIT)
    )
    recent_rows = list(db.scalars(recent_stmt).all())
    recent_reads = [OrderRead.model_validate(row) for row in recent_rows]

    return StoreOrdersSummary(
        open_count=open_count,
        by_status=counts_by_status,
        recent=recent_reads,
    )


def _inventory_summary(
    db: Session, store_id: UUID
) -> StoreInventorySummary:
    """Cardinality + low-stock count + total on_hand / reserved."""
    low_stock_expr = case(
        (
            InventoryItem.quantity_on_hand
            - InventoryItem.quantity_reserved
            <= InventoryItem.reorder_threshold,
            1,
        ),
        else_=0,
    )
    stmt = (
        select(
            func.count(InventoryItem.id),
            func.coalesce(func.sum(low_stock_expr), 0),
            func.coalesce(func.sum(InventoryItem.quantity_on_hand), 0),
            func.coalesce(
                func.sum(InventoryItem.quantity_reserved), 0
            ),
        )
        .where(InventoryItem.store_id == store_id)
    )
    total_items, low_stock, on_hand, reserved = db.execute(stmt).one()
    return StoreInventorySummary(
        total_items=int(total_items or 0),
        low_stock_count=int(low_stock or 0),
        total_on_hand=int(on_hand or 0),
        total_reserved=int(reserved or 0),
    )


def _products_summary(
    db: Session, store_id: UUID
) -> StoreProductsSummary:
    """Products with inventory in this store + blocked subset.

    `Product` has no `store_id`, so we join through
    `ProductVariant` -> `InventoryItem`. A product counts as "in
    store" iff it has at least one inventory row for this store.
    `blocked_count` further filters by the canonical compliance
    predicate (matches `app.services.admin_dashboard._compliance_summary`).
    """
    in_store_stmt = (
        select(func.count(distinct(Product.id)))
        .select_from(Product)
        .join(ProductVariant, ProductVariant.product_id == Product.id)
        .join(
            InventoryItem,
            InventoryItem.variant_id == ProductVariant.id,
        )
        .where(InventoryItem.store_id == store_id)
    )
    in_store = int(db.scalar(in_store_stmt) or 0)

    blocked_predicate = or_(
        Product.allowed_for_sale.is_(False),
        Product.compliance_status.in_(_BLOCKING_COMPLIANCE_STATUSES),
    )
    blocked_stmt = (
        select(func.count(distinct(Product.id)))
        .select_from(Product)
        .join(ProductVariant, ProductVariant.product_id == Product.id)
        .join(
            InventoryItem,
            InventoryItem.variant_id == ProductVariant.id,
        )
        .where(
            and_(InventoryItem.store_id == store_id, blocked_predicate)
        )
    )
    blocked = int(db.scalar(blocked_stmt) or 0)

    return StoreProductsSummary(
        in_store_count=in_store,
        blocked_count=blocked,
    )


def _kpis_from_sections(
    orders: StoreOrdersSummary,
    inventory: StoreInventorySummary,
    products: StoreProductsSummary,
) -> StoreDashboardKpis:
    """Derive the KPI bundle from the already-computed sections so the
    two surfaces (dashboard + kpis) are guaranteed to agree.
    """
    return StoreDashboardKpis(
        orders_open=orders.open_count,
        orders_by_status=orders.by_status,
        inventory_total_items=inventory.total_items,
        inventory_low_stock=inventory.low_stock_count,
        products_in_store=products.in_store_count,
        products_blocked=products.blocked_count,
    )


# --------------------------------------------------------------------- #
# Activity feed (store-scoped inventory log normalization)
# --------------------------------------------------------------------- #


def _normalize_inventory_log(log: InventoryLog) -> AuditEventRead:
    """Project an `InventoryLog` row into the unified `AuditEventRead`
    shape. Same field mapping as `app.services.audit`.
    """
    return AuditEventRead(
        id=log.id,
        source="inventory",
        store_id=log.store_id,
        actor_id=log.performed_by_user_id,
        action=log.movement_type.value,
        entity_type="inventory_item",
        entity_id=log.inventory_item_id,
        summary=(
            f"Inventory {log.movement_type.value}: "
            f"delta {log.quantity_delta:+d}, after {log.quantity_after}"
        ),
        metadata={
            "quantity_delta": log.quantity_delta,
            "quantity_after": log.quantity_after,
            "reason": log.reason,
            "reference_type": log.reference_type,
            "reference_id": (
                str(log.reference_id) if log.reference_id else None
            ),
        },
        created_at=log.created_at,
    )


def list_store_activity(
    db: Session,
    *,
    store_id: UUID,
    limit: int = 50,
    offset: int = 0,
) -> StoreActivityListResponse:
    """Paginated store-scoped activity feed.

    Backed by `InventoryLog` for this store. Same projection shape as
    the unified audit feed (`AuditEventRead`) so the frontend can
    re-use its existing renderer. Sorted by `created_at DESC, id ASC`
    for deterministic pagination across identical timestamps.
    """
    _validate_pagination(limit, offset)
    _ensure_store_exists(db, store_id)

    count_stmt = (
        select(func.count())
        .select_from(InventoryLog)
        .where(InventoryLog.store_id == store_id)
    )
    total = int(db.scalar(count_stmt) or 0)

    rows_stmt = (
        select(InventoryLog)
        .where(InventoryLog.store_id == store_id)
        .order_by(InventoryLog.created_at.desc(), InventoryLog.id.asc())
        .limit(limit)
        .offset(offset)
    )
    rows = list(db.scalars(rows_stmt).all())
    items = [_normalize_inventory_log(row) for row in rows]

    return StoreActivityListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


# --------------------------------------------------------------------- #
# Alerts (computed-on-request, deterministic ids)
# --------------------------------------------------------------------- #


def _low_stock_severity(
    on_hand_minus_reserved: int, reorder_threshold: int
) -> StoreAlertSeverity:
    """Map a low-stock row to a severity bucket.

    - high   : effective stock <= 0 (fully depleted)
    - medium : effective stock <= 50% of threshold (or zero threshold)
    - low    : everything else inside the predicate
    """
    if on_hand_minus_reserved <= 0:
        return StoreAlertSeverity.high
    if reorder_threshold <= 0:
        return StoreAlertSeverity.medium
    if on_hand_minus_reserved * 2 <= reorder_threshold:
        return StoreAlertSeverity.medium
    return StoreAlertSeverity.low


def _query_low_stock_alerts(
    db: Session, store_id: UUID
) -> list[StoreAlert]:
    """Build `low_stock` alerts from the canonical predicate."""
    stmt = (
        select(InventoryItem)
        .where(
            and_(
                InventoryItem.store_id == store_id,
                InventoryItem.quantity_on_hand
                - InventoryItem.quantity_reserved
                <= InventoryItem.reorder_threshold,
            )
        )
    )
    rows = list(db.scalars(stmt).all())
    alerts: list[StoreAlert] = []
    for item in rows:
        effective = item.quantity_on_hand - item.quantity_reserved
        severity = _low_stock_severity(
            effective, item.reorder_threshold
        )
        alerts.append(
            StoreAlert(
                id=f"low_stock:{item.id}",
                category=StoreAlertCategory.low_stock,
                severity=severity,
                store_id=item.store_id,
                entity_type=StoreAlertEntityType.inventory_item,
                entity_id=item.id,
                summary=(
                    f"Low stock: {effective} effective on hand vs "
                    f"reorder threshold {item.reorder_threshold}."
                ),
                created_at=item.updated_at,
            )
        )
    return alerts


def _query_aging_order_alerts(
    db: Session,
    *,
    store_id: UUID,
    aging_minutes: int,
    now: datetime,
) -> list[StoreAlert]:
    """Build `aging_order` alerts for open orders older than the
    configured `aging_minutes` threshold.
    """
    cutoff = now - timedelta(minutes=aging_minutes)
    stmt = (
        select(Order)
        .where(
            and_(
                Order.store_id == store_id,
                Order.status.in_(_OPEN_ORDER_STATUSES),
                Order.created_at <= cutoff,
            )
        )
    )
    rows = list(db.scalars(stmt).all())
    alerts: list[StoreAlert] = []
    for order in rows:
        age = now - order.created_at
        # `Order.created_at` is timezone-aware; tolerate naive rows
        # defensively.
        age_minutes = int(age.total_seconds() // 60)
        if age_minutes >= aging_minutes * 4:
            severity = StoreAlertSeverity.high
        elif age_minutes >= aging_minutes * 2:
            severity = StoreAlertSeverity.medium
        else:
            severity = StoreAlertSeverity.low
        alerts.append(
            StoreAlert(
                id=f"aging_order:{order.id}:{aging_minutes}",
                category=StoreAlertCategory.aging_order,
                severity=severity,
                store_id=order.store_id,
                entity_type=StoreAlertEntityType.order,
                entity_id=order.id,
                summary=(
                    f"Order open for {age_minutes} min "
                    f"(threshold {aging_minutes} min, status "
                    f"{order.status.value})."
                ),
                created_at=order.created_at,
            )
        )
    return alerts


def _query_no_inventory_alert(
    db: Session, store: Store
) -> list[StoreAlert]:
    """Single-row category: this store has zero `InventoryItem` rows."""
    count_stmt = (
        select(func.count())
        .select_from(InventoryItem)
        .where(InventoryItem.store_id == store.id)
    )
    count = int(db.scalar(count_stmt) or 0)
    if count > 0:
        return []
    return [
        StoreAlert(
            id=f"no_inventory:{store.id}",
            category=StoreAlertCategory.no_inventory,
            severity=StoreAlertSeverity.medium,
            store_id=store.id,
            entity_type=StoreAlertEntityType.store,
            entity_id=store.id,
            summary="Store has no inventory items.",
            created_at=store.created_at,
        )
    ]


def list_store_alerts(
    db: Session,
    *,
    store_id: UUID,
    limit: int = 50,
    offset: int = 0,
    category: StoreAlertCategory | None = None,
    severity: StoreAlertSeverity | None = None,
    aging_minutes: int = _AGING_MINUTES_DEFAULT,
) -> StoreAlertsListResponse:
    """Paginated, filterable store alerts.

    Pipeline:
      1. Validate query bounds.
      2. Resolve the target store (404 if missing).
      3. Generate alerts for each requested category.
      4. Filter by severity if requested.
      5. Deterministic sort:
         (severity DESC, created_at DESC, category ASC, entity_id ASC).
      6. `total` = pre-pagination count, then slice.
    """
    _validate_pagination(limit, offset)
    _validate_aging_minutes(aging_minutes)
    store = _ensure_store_exists(db, store_id)

    now = datetime.now(UTC)
    alerts: list[StoreAlert] = []

    wants_low_stock = (
        category is None or category == StoreAlertCategory.low_stock
    )
    wants_aging_order = (
        category is None or category == StoreAlertCategory.aging_order
    )
    wants_no_inventory = (
        category is None
        or category == StoreAlertCategory.no_inventory
    )

    if wants_low_stock:
        alerts.extend(_query_low_stock_alerts(db, store_id))
    if wants_aging_order:
        alerts.extend(
            _query_aging_order_alerts(
                db,
                store_id=store_id,
                aging_minutes=aging_minutes,
                now=now,
            )
        )
    if wants_no_inventory:
        alerts.extend(_query_no_inventory_alert(db, store))

    if severity is not None:
        alerts = [a for a in alerts if a.severity == severity]

    # Deterministic sort. Python's sort is stable so applying the keys
    # in reverse precedence yields the documented composite order.
    alerts.sort(key=lambda a: (a.category.value, str(a.entity_id)))
    alerts.sort(key=lambda a: a.created_at, reverse=True)
    alerts.sort(
        key=lambda a: _SEVERITY_PRIORITY[a.severity], reverse=True
    )

    total = len(alerts)
    page = alerts[offset : offset + limit]
    return StoreAlertsListResponse(
        items=page,
        total=total,
        limit=limit,
        offset=offset,
    )


# --------------------------------------------------------------------- #
# Public summary entry points
# --------------------------------------------------------------------- #


def get_store_orders_summary(
    db: Session, *, store_id: UUID
) -> StoreOrdersSummary:
    _ensure_store_exists(db, store_id)
    return _orders_summary(db, store_id)


def get_store_inventory_summary(
    db: Session, *, store_id: UUID
) -> StoreInventorySummary:
    _ensure_store_exists(db, store_id)
    return _inventory_summary(db, store_id)


def get_store_products_summary(
    db: Session, *, store_id: UUID
) -> StoreProductsSummary:
    _ensure_store_exists(db, store_id)
    return _products_summary(db, store_id)


def get_store_dashboard_kpis(
    db: Session, *, store_id: UUID
) -> StoreDashboardKpis:
    _ensure_store_exists(db, store_id)
    orders = _orders_summary(db, store_id)
    inventory = _inventory_summary(db, store_id)
    products = _products_summary(db, store_id)
    return _kpis_from_sections(orders, inventory, products)


def get_store_dashboard_summary(
    db: Session, *, store_id: UUID
) -> StoreDashboardSummary:
    """Build the full store dashboard payload.

    Sections are computed independently; KPIs are derived from the
    section results so the two surfaces always agree. Recent activity
    re-uses `list_store_activity` truncated to the service-owned tail
    bound so the dashboard never duplicates audit-projection logic.
    """
    _ensure_store_exists(db, store_id)

    orders = _orders_summary(db, store_id)
    inventory = _inventory_summary(db, store_id)
    products = _products_summary(db, store_id)
    kpis = _kpis_from_sections(orders, inventory, products)

    activity = list_store_activity(
        db,
        store_id=store_id,
        limit=_RECENT_ACTIVITY_LIMIT,
        offset=0,
    )

    return StoreDashboardSummary(
        store_id=store_id,
        kpis=kpis,
        orders=orders,
        inventory=inventory,
        products=products,
        recent_activity=activity.items,
    )
