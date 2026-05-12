"""Service layer for the admin operations alerts feed (F2.19.2).

Computes a list of operational alerts on every request from existing
tables (`Store`, `User`, `InventoryItem`, `Order`, `Product`). No
persistence, no migrations, no model changes, no Alert table, no
acknowledge / dismiss / resolve state.

Five locked categories (F2.19.0 §3.2.2):

  - low_stock           — `InventoryItem` low-stock predicate
  - aging_order         — open `Order` rows older than aging_minutes
  - compliance_blocker  — `Product` blocked from sale by compliance
  - inactive_store      — `Store.is_active = false`
  - store_no_inventory  — `Store` with zero `InventoryItem` rows

Severity rules per category are locked by F2.19.0 §3.2.7. The
deterministic ordering applied AFTER filtering and BEFORE pagination
is `(severity DESC, created_at DESC, category ASC, entity_id ASC)`
(F2.19.0 §3.2.8); deterministic alert ids follow F2.19.0 §3.2.9.

RBAC: admin-only. Non-admin actors → 403 at the service boundary so
direct callers (admin scripts) match the route contract. Service is
read-only end-to-end — no `db.add`, `db.delete`, or `db.commit`.
"""

from __future__ import annotations

from datetime import UTC
from datetime import datetime
from typing import Callable
from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import InventoryItem
from app.db.models import Order
from app.db.models import OrderStatus
from app.db.models import Product
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.admin_operations import AdminOperationsAlert
from app.schemas.admin_operations import AdminOperationsAlertCategory
from app.schemas.admin_operations import AdminOperationsAlertEntityType
from app.schemas.admin_operations import AdminOperationsAlertSeverity
from app.schemas.admin_operations import AdminOperationsAlertsListResponse


# --------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------- #


# Pagination + threshold bounds. Mirrors the values the route encodes
# via `Query(ge=..., le=...)` so direct callers (admin scripts) get
# the same contract.
_LIMIT_MIN = 1
_LIMIT_MAX = 200
_OFFSET_MIN = 0
_AGING_MINUTES_MIN = 1


# Open order status set (F2.19.0 §3.2.6 aging_order). Same set the
# dashboard `open_count` is computed from — the two surfaces share
# the operational definition of "open".
_OPEN_ORDER_STATUSES: frozenset[OrderStatus] = frozenset(
    {
        OrderStatus.pending,
        OrderStatus.accepted,
        OrderStatus.preparing,
        OrderStatus.ready,
        OrderStatus.out_for_delivery,
    }
)


# Compliance blocking statuses (F2.19.0 §3.2.7 compliance_blocker).
# Banned implies allowed_for_sale=false by DB CHECK constraint; the
# medium tier captures `restricted` (which the constraint allows to
# still be `allowed_for_sale=true`).
_BLOCKING_COMPLIANCE_STATUSES: frozenset[ComplianceStatus] = frozenset(
    {ComplianceStatus.banned, ComplianceStatus.restricted}
)


# DESC priority for the deterministic ordering (F2.19.0 §3.2.8). high
# is the most urgent, sorted to the top.
_SEVERITY_PRIORITY: dict[AdminOperationsAlertSeverity, int] = {
    AdminOperationsAlertSeverity.high: 3,
    AdminOperationsAlertSeverity.medium: 2,
    AdminOperationsAlertSeverity.low: 1,
}


# --------------------------------------------------------------------- #
# RBAC + input validation
# --------------------------------------------------------------------- #


def _assert_admin_caller(actor: User) -> None:
    """Service-level RBAC gate.

    Symmetric with `app.services.admin_dashboard._assert_admin_caller`
    and the inventory / orders / audit admin services. Defense in
    depth: the route already enforces `require_admin`, but a direct
    service caller (admin script, batch job) is also gated.
    """
    if actor.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )


def _validate_query_bounds(
    *, limit: int, offset: int, aging_minutes: int
) -> None:
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
    if aging_minutes < _AGING_MINUTES_MIN:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                f"aging_minutes must be >= {_AGING_MINUTES_MIN}."
            ),
        )


# --------------------------------------------------------------------- #
# Category generators
# --------------------------------------------------------------------- #


def _compute_low_stock(db: Session) -> list[AdminOperationsAlert]:
    """One alert per `InventoryItem` row that satisfies the
    low-stock predicate (F2.19.0 §3.2.6).

    Predicate: `quantity_on_hand - quantity_reserved <= reorder_threshold`.

    Severity (F2.19.0 §3.2.7):
      - high   if available_quantity <= 0
      - medium if available_quantity <= reorder_threshold (and > 0)

    `created_at` is sourced from `InventoryItem.updated_at` — the
    most recent operational signal on the row. The contract permits
    falling back to `created_at` if `updated_at` is absent; the
    model has `updated_at`, so this branch is what we use.

    Deterministic id: `low_stock:<inventory_item_id>`.
    """
    stmt = select(InventoryItem).where(
        InventoryItem.quantity_on_hand - InventoryItem.quantity_reserved
        <= InventoryItem.reorder_threshold
    )
    rows = list(db.scalars(stmt).all())
    alerts: list[AdminOperationsAlert] = []
    for item in rows:
        available = item.quantity_on_hand - item.quantity_reserved
        if available <= 0:
            severity = AdminOperationsAlertSeverity.high
        else:
            severity = AdminOperationsAlertSeverity.medium
        summary = (
            f"Low stock: available {available} "
            f"<= reorder threshold {item.reorder_threshold}"
        )
        alerts.append(
            AdminOperationsAlert(
                id=f"low_stock:{item.id}",
                category=AdminOperationsAlertCategory.low_stock,
                severity=severity,
                store_id=item.store_id,
                entity_type=AdminOperationsAlertEntityType.inventory_item,
                entity_id=item.id,
                summary=summary,
                created_at=item.updated_at,
            )
        )
    return alerts


def _compute_aging_orders(
    db: Session, *, now: datetime, aging_minutes: int
) -> list[AdminOperationsAlert]:
    """One alert per open `Order` whose age >= `aging_minutes`.

    Open statuses are `{pending, accepted, preparing, ready,
    out_for_delivery}` (F2.19.0 §3.2.6).

    Severity (F2.19.0 §3.2.7):
      - high   if age_minutes >= aging_minutes * 2
      - medium if age_minutes >= aging_minutes

    Deterministic id: `aging_order:<order_id>:<aging_minutes>` —
    `aging_minutes` is part of the id because the alert identity
    depends on the threshold the caller applied (two callers with
    different thresholds see different ids for the same order).
    """
    stmt = select(Order).where(Order.status.in_(_OPEN_ORDER_STATUSES))
    rows = list(db.scalars(stmt).all())
    alerts: list[AdminOperationsAlert] = []
    for order in rows:
        age_seconds = (now - order.created_at).total_seconds()
        age_minutes = age_seconds / 60
        if age_minutes < aging_minutes:
            continue
        if age_minutes >= aging_minutes * 2:
            severity = AdminOperationsAlertSeverity.high
        else:
            severity = AdminOperationsAlertSeverity.medium
        summary = (
            f"Aging order ({order.status.value}): "
            f"{int(age_minutes)}m old, threshold {aging_minutes}m"
        )
        alerts.append(
            AdminOperationsAlert(
                id=f"aging_order:{order.id}:{aging_minutes}",
                category=AdminOperationsAlertCategory.aging_order,
                severity=severity,
                store_id=order.store_id,
                entity_type=AdminOperationsAlertEntityType.order,
                entity_id=order.id,
                summary=summary,
                created_at=order.created_at,
            )
        )
    return alerts


def _compute_compliance_blockers(
    db: Session,
) -> list[AdminOperationsAlert]:
    """One alert per `Product` blocked from sale (F2.19.0 §3.2.6).

    Predicate: `allowed_for_sale = false
                OR compliance_status IN (banned, restricted)`.

    Severity (F2.19.0 §3.2.7):
      - high   if compliance_status == banned OR allowed_for_sale == false
      - medium if compliance_status == restricted (and not high)

    `Product` has no `store_id` column in the current model, so the
    alert's `store_id` is `None`. This is consistent with the
    F2.19.0 contract: `compliance_blocker` is described as global,
    and the `store_id` filter on the endpoint is filter-only — it
    will exclude these alerts when a `store_id` is provided.

    Deterministic id: `compliance_blocker:<product_id>`.
    """
    stmt = select(Product).where(
        or_(
            Product.allowed_for_sale.is_(False),
            Product.compliance_status.in_(_BLOCKING_COMPLIANCE_STATUSES),
        )
    )
    rows = list(db.scalars(stmt).all())
    alerts: list[AdminOperationsAlert] = []
    for product in rows:
        if (
            product.compliance_status == ComplianceStatus.banned
            or product.allowed_for_sale is False
        ):
            severity = AdminOperationsAlertSeverity.high
        else:
            # By construction the only remaining case is restricted +
            # allowed_for_sale=True.
            severity = AdminOperationsAlertSeverity.medium
        summary = (
            f"Compliance blocker: status={product.compliance_status.value}, "
            f"allowed_for_sale={product.allowed_for_sale}"
        )
        alerts.append(
            AdminOperationsAlert(
                id=f"compliance_blocker:{product.id}",
                category=AdminOperationsAlertCategory.compliance_blocker,
                severity=severity,
                store_id=None,
                entity_type=AdminOperationsAlertEntityType.product,
                entity_id=product.id,
                summary=summary,
                created_at=product.updated_at,
            )
        )
    return alerts


def _compute_inactive_stores(
    db: Session,
) -> list[AdminOperationsAlert]:
    """One alert per `Store` row with `is_active = false` (F2.19.0
    §3.2.6).

    Severity is always `medium` (F2.19.0 §3.2.7). Deterministic id:
    `inactive_store:<store_id>`.
    """
    stmt = select(Store).where(Store.is_active.is_(False))
    rows = list(db.scalars(stmt).all())
    return [
        AdminOperationsAlert(
            id=f"inactive_store:{store.id}",
            category=AdminOperationsAlertCategory.inactive_store,
            severity=AdminOperationsAlertSeverity.medium,
            store_id=store.id,
            entity_type=AdminOperationsAlertEntityType.store,
            entity_id=store.id,
            summary=f"Store '{store.name}' is inactive.",
            created_at=store.updated_at,
        )
        for store in rows
    ]


def _compute_no_inventory_stores(
    db: Session,
) -> list[AdminOperationsAlert]:
    """One alert per `Store` row that has zero `InventoryItem` rows.

    Implemented via a NOT EXISTS subquery (semantically equivalent
    to the LEFT OUTER JOIN ... WHERE InventoryItem.id IS NULL pattern
    described in F2.19.0 §3.2.6).

    Severity is always `medium` (F2.19.0 §3.2.7). Deterministic id:
    `store_no_inventory:<store_id>`.
    """
    has_inventory_subquery = (
        select(InventoryItem.id)
        .where(InventoryItem.store_id == Store.id)
        .exists()
    )
    stmt = select(Store).where(~has_inventory_subquery)
    rows = list(db.scalars(stmt).all())
    return [
        AdminOperationsAlert(
            id=f"store_no_inventory:{store.id}",
            category=AdminOperationsAlertCategory.store_no_inventory,
            severity=AdminOperationsAlertSeverity.medium,
            store_id=store.id,
            entity_type=AdminOperationsAlertEntityType.store,
            entity_id=store.id,
            summary=f"Store '{store.name}' has no inventory.",
            created_at=store.updated_at,
        )
        for store in rows
    ]


# Dispatch table: category → generator. Keeps the public entry point
# small and makes the `category=` filter optimization trivial (skip
# generators we know cannot contribute).
_CATEGORY_GENERATORS: dict[
    AdminOperationsAlertCategory,
    Callable[..., list[AdminOperationsAlert]],
] = {
    AdminOperationsAlertCategory.low_stock: _compute_low_stock,
    AdminOperationsAlertCategory.aging_order: _compute_aging_orders,
    AdminOperationsAlertCategory.compliance_blocker: (
        _compute_compliance_blockers
    ),
    AdminOperationsAlertCategory.inactive_store: _compute_inactive_stores,
    AdminOperationsAlertCategory.store_no_inventory: (
        _compute_no_inventory_stores
    ),
}


# --------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------- #


def list_admin_operations_alerts(
    db: Session,
    *,
    actor: User,
    limit: int = 50,
    offset: int = 0,
    category: AdminOperationsAlertCategory | None = None,
    severity: AdminOperationsAlertSeverity | None = None,
    store_id: UUID | None = None,
    aging_minutes: int = 1440,
) -> AdminOperationsAlertsListResponse:
    """Compute and return the filtered, sorted, paginated alert page.

    Pipeline (locked by F2.19.0 §3.2):

      1. RBAC gate (admin-only).
      2. Validate pagination + aging_minutes bounds.
      3. Anchor `now` once for this request so every alert sees the
         same clock (deterministic across the call's lifetime).
      4. Run each category generator (or only the requested one when
         `category=` is set).
      5. Apply `severity` and `store_id` filters.
      6. Compute `total` against the filtered set.
      7. Sort deterministically: severity DESC, created_at DESC,
         category ASC, entity_id ASC.
      8. Slice `[offset:offset+limit]`.

    Read-only. No writes anywhere in the pipeline.
    """
    _assert_admin_caller(actor)
    _validate_query_bounds(
        limit=limit, offset=offset, aging_minutes=aging_minutes
    )

    now = datetime.now(UTC)

    candidates: list[AdminOperationsAlert] = []
    for cat, generator in _CATEGORY_GENERATORS.items():
        if category is not None and cat != category:
            continue
        if cat == AdminOperationsAlertCategory.aging_order:
            candidates.extend(
                generator(db, now=now, aging_minutes=aging_minutes)
            )
        else:
            candidates.extend(generator(db))

    if severity is not None:
        candidates = [a for a in candidates if a.severity == severity]

    if store_id is not None:
        # Alerts with store_id=None (today: compliance_blocker) are
        # excluded by a store_id filter — explicitly required by the
        # F2.19.0 contract.
        candidates = [a for a in candidates if a.store_id == store_id]

    total = len(candidates)

    # Stable cascade sort. Python's sort is stable, so applying the
    # secondary keys first and the primary key last preserves the
    # secondary order within primary-key ties.
    candidates.sort(
        key=lambda a: (a.category.value, str(a.entity_id))
    )
    candidates.sort(key=lambda a: a.created_at, reverse=True)
    candidates.sort(
        key=lambda a: _SEVERITY_PRIORITY[a.severity], reverse=True
    )

    page = candidates[offset : offset + limit]

    return AdminOperationsAlertsListResponse(
        items=page,
        total=total,
        limit=limit,
        offset=offset,
    )
