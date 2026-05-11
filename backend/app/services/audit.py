"""Service layer for the unified store audit feed (F2.16.2).

`list_store_audit` is the only public entry point. It aggregates three
existing append-only log tables — `inventory_logs`, `order_audit_logs`,
and `product_compliance_audit_logs` — into the normalized
`AuditEventRead` shape locked in F2.16.1, applies a uniform set of
filters, merges them, sorts with a 3-key stable order, and paginates
after the merge.

No new tables, no migrations, no model changes. The compliance source
has no `store_id` column; this module owns the join that scopes a
product's compliance history to a requested store:

  ProductComplianceAuditLog.product_id
    -> ProductVariant.product_id
    -> InventoryItem.variant_id
    -> InventoryItem.store_id == requested store_id

A product carried by multiple variants/items in the same store still
yields ONE compliance event per audit row (DISTINCT on the audit log
id, plus a defensive Python-side dedupe).

RBAC / tenancy is enforced here at the service layer even though
routes do not exist yet (F2.16.3 owns the route). The rules mirror
`require_store_member` exactly so behavior stays uniform when the
route is added on top:

  - admin: any active store; 404 if missing; 400 if inactive.
  - owner / manager / staff: own active store only; cross-store and
    unknown-store collapse to 403 to avoid existence-probe leaks;
    400 if their own store is inactive.
  - driver: 403 (role gate; never sees the audit surface).
  - anonymous: not reachable here — `current_user` injection runs in
    the route, so this layer only ever sees an authenticated `User`.

Pagination guards run at the service boundary so the route can stay
thin: limit must be 1..200, offset must be >= 0. Out-of-range values
raise 422 — same status code the route's `Query(ge=..., le=...)` will
raise, so a future direct caller (admin script, batch job) gets the
same contract.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import InventoryItem
from app.db.models import InventoryLog
from app.db.models import InventoryMovementType
from app.db.models import OrderAuditLog
from app.db.models import ProductComplianceAuditLog
from app.db.models import ProductVariant
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.audit import AuditEntityType
from app.schemas.audit import AuditEventListResponse
from app.schemas.audit import AuditEventRead
from app.schemas.audit import AuditSource


# --------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------- #


# Roles allowed to read the audit feed. Driver is operational-only and
# never sees this surface; staff and above (including admin) may read.
_AUDIT_READER_ROLES: frozenset[UserRole] = frozenset(
    {
        UserRole.admin,
        UserRole.owner,
        UserRole.manager,
        UserRole.staff,
    }
)

# Pagination bounds. Mirror the values the future route will encode
# via `Query(ge=..., le=...)`. Keeping them here guarantees the same
# contract for direct callers (e.g. an internal admin script).
_LIMIT_MIN = 1
_LIMIT_MAX = 200
_OFFSET_MIN = 0

# The only `action` value compliance rows ever emit. Centralised so
# the filter logic and the normalizer agree.
_COMPLIANCE_ACTION = "compliance_changed"


# --------------------------------------------------------------------- #
# RBAC / tenancy
# --------------------------------------------------------------------- #


def _assert_audit_access(
    db: Session, *, store_id: UUID, actor: User
) -> Store:
    """Service-layer twin of `require_store_member` for the audit feed.

    See module docstring for the full matrix. Returns the resolved
    `Store` row so the caller can avoid a second lookup, mirroring
    `assert_active_store_for_assignment`.
    """
    if actor.role not in _AUDIT_READER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this resource.",
        )

    if actor.role == UserRole.admin:
        store = db.scalar(select(Store).where(Store.id == store_id))
        if store is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Store not found.",
            )
        if not store.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Store is inactive.",
            )
        return store

    if actor.store_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is not bound to a store.",
        )

    # Existence-probe collapse: cross-store and unknown-store look
    # identical to a non-admin caller.
    if actor.store_id != store_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this store.",
        )

    store = db.scalar(select(Store).where(Store.id == store_id))
    if store is None:
        # FK ON DELETE SET NULL on User.store_id means a non-admin's
        # store usually exists, but cover the race window explicitly.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Store not found.",
        )
    if not store.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Store is inactive.",
        )
    return store


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


# --------------------------------------------------------------------- #
# Source normalizers
# --------------------------------------------------------------------- #


def _inventory_summary(log: InventoryLog) -> str:
    sign = "+" if log.quantity_delta >= 0 else ""
    return (
        f"Inventory {log.movement_type.value}: "
        f"{sign}{log.quantity_delta} units (after {log.quantity_after})"
    )


def _order_summary(log: OrderAuditLog) -> str:
    prev = log.previous_status.value if log.previous_status else "—"
    return f"Order {log.action}: {prev} → {log.new_status.value}"


def _compliance_summary(log: ProductComplianceAuditLog) -> str:
    return (
        f"Compliance: "
        f"{log.previous_compliance_status.value}/"
        f"{log.previous_allowed_for_sale} → "
        f"{log.new_compliance_status.value}/"
        f"{log.new_allowed_for_sale}"
    )


def _coerce_uuid_str(value: UUID | None) -> str | None:
    """UUIDs inside `metadata: dict[str, Any]` are not auto-stringified
    on JSON dump in every Pydantic v2 release; pre-stringify them so
    the wire shape is always JSON-safe regardless of serializer
    version."""
    return str(value) if value is not None else None


def _query_inventory_events(
    db: Session,
    *,
    store_id: UUID,
    action: str | None,
    actor_id: UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[AuditEventRead]:
    if action is not None:
        # `InventoryLog.movement_type` is a Postgres enum column;
        # comparing it against a string that isn't a valid enum
        # member raises InvalidTextRepresentation at the DB layer.
        # Short-circuit to "no rows" when the requested action isn't
        # a valid movement type, instead of crashing the whole feed
        # because a foreign-source action ("order_canceled",
        # "compliance_changed") was used as the action filter.
        try:
            movement_filter = InventoryMovementType(action)
        except ValueError:
            return []
    else:
        movement_filter = None

    stmt = select(InventoryLog).where(InventoryLog.store_id == store_id)
    if movement_filter is not None:
        stmt = stmt.where(InventoryLog.movement_type == movement_filter)
    if actor_id is not None:
        stmt = stmt.where(InventoryLog.performed_by_user_id == actor_id)
    if date_from is not None:
        stmt = stmt.where(InventoryLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(InventoryLog.created_at <= date_to)

    rows = list(db.scalars(stmt).all())
    events: list[AuditEventRead] = []
    for log in rows:
        metadata: dict[str, Any] = {
            "variant_id": _coerce_uuid_str(log.variant_id),
            "quantity_delta": log.quantity_delta,
            "quantity_after": log.quantity_after,
            "reason": log.reason,
            "reference_type": log.reference_type,
            "reference_id": _coerce_uuid_str(log.reference_id),
        }
        events.append(
            AuditEventRead(
                id=log.id,
                source=AuditSource.inventory,
                store_id=log.store_id,
                actor_id=log.performed_by_user_id,
                action=log.movement_type.value,
                entity_type=AuditEntityType.inventory_item,
                entity_id=log.inventory_item_id,
                summary=_inventory_summary(log),
                metadata=metadata,
                created_at=log.created_at,
            )
        )
    return events


def _query_order_events(
    db: Session,
    *,
    store_id: UUID,
    action: str | None,
    actor_id: UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[AuditEventRead]:
    stmt = select(OrderAuditLog).where(OrderAuditLog.store_id == store_id)
    if action is not None:
        stmt = stmt.where(OrderAuditLog.action == action)
    if actor_id is not None:
        stmt = stmt.where(OrderAuditLog.performed_by_user_id == actor_id)
    if date_from is not None:
        stmt = stmt.where(OrderAuditLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(OrderAuditLog.created_at <= date_to)

    rows = list(db.scalars(stmt).all())
    events: list[AuditEventRead] = []
    for log in rows:
        metadata: dict[str, Any] = {
            "previous_status": (
                log.previous_status.value
                if log.previous_status is not None
                else None
            ),
            "new_status": log.new_status.value,
            "reason": log.reason,
        }
        events.append(
            AuditEventRead(
                id=log.id,
                source=AuditSource.order,
                store_id=log.store_id,
                actor_id=log.performed_by_user_id,
                action=log.action,
                entity_type=AuditEntityType.order,
                entity_id=log.order_id,
                summary=_order_summary(log),
                metadata=metadata,
                created_at=log.created_at,
            )
        )
    return events


def _query_compliance_events(
    db: Session,
    *,
    store_id: UUID,
    action: str | None,
    actor_id: UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[AuditEventRead]:
    """Compliance events scoped via the catalog→inventory join path.

    `Product` has no `store_id`; a compliance audit row is relevant to
    a store only when that store currently carries inventory for at
    least one variant of the product. The DISTINCT clause + Python-side
    dedupe collapse duplicates that arise from a product having
    multiple variants/items in the same store (one row in the join
    output per matching item, but we want one event per audit log id).
    """
    if action is not None and action != _COMPLIANCE_ACTION:
        return []

    stmt = (
        select(ProductComplianceAuditLog)
        .join(
            ProductVariant,
            ProductVariant.product_id == ProductComplianceAuditLog.product_id,
        )
        .join(
            InventoryItem,
            InventoryItem.variant_id == ProductVariant.id,
        )
        .where(InventoryItem.store_id == store_id)
        .distinct()
    )
    if actor_id is not None:
        stmt = stmt.where(
            ProductComplianceAuditLog.changed_by_user_id == actor_id
        )
    if date_from is not None:
        stmt = stmt.where(ProductComplianceAuditLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(ProductComplianceAuditLog.created_at <= date_to)

    rows = list(db.scalars(stmt).all())

    # Defense-in-depth dedupe by audit log id — covers any join shape
    # that DISTINCT did not collapse (e.g. if SQLAlchemy ever surfaces
    # the join's row carrier with extra identity columns).
    seen: set[UUID] = set()
    deduped: list[ProductComplianceAuditLog] = []
    for log in rows:
        if log.id in seen:
            continue
        seen.add(log.id)
        deduped.append(log)

    events: list[AuditEventRead] = []
    for log in deduped:
        metadata: dict[str, Any] = {
            "previous_compliance_status": (
                log.previous_compliance_status.value
            ),
            "new_compliance_status": log.new_compliance_status.value,
            "previous_allowed_for_sale": log.previous_allowed_for_sale,
            "new_allowed_for_sale": log.new_allowed_for_sale,
            "reason": log.reason,
        }
        events.append(
            AuditEventRead(
                id=log.id,
                source=AuditSource.product_compliance,
                # The requested store_id is the audit scope, not the
                # log's own (which has no store_id column). Compliance
                # events fan out across stores that carry the product.
                store_id=store_id,
                actor_id=log.changed_by_user_id,
                action=_COMPLIANCE_ACTION,
                entity_type=AuditEntityType.product,
                entity_id=log.product_id,
                summary=_compliance_summary(log),
                metadata=metadata,
                created_at=log.created_at,
            )
        )
    return events


# --------------------------------------------------------------------- #
# Source-applicability gate
# --------------------------------------------------------------------- #


# Each source emits events for exactly one entity_type. If both
# `source` and `entity_type` are set and they disagree with the
# binding here, the source must contribute zero rows — applying that
# rule centrally is cleaner than threading two flags into each
# query helper.
_SOURCE_ENTITY_BINDING: dict[AuditSource, AuditEntityType] = {
    AuditSource.inventory: AuditEntityType.inventory_item,
    AuditSource.order: AuditEntityType.order,
    AuditSource.product_compliance: AuditEntityType.product,
}


def _source_applies(
    candidate: AuditSource,
    *,
    source: AuditSource | None,
    entity_type: AuditEntityType | None,
) -> bool:
    if source is not None and source != candidate:
        return False
    if (
        entity_type is not None
        and entity_type != _SOURCE_ENTITY_BINDING[candidate]
    ):
        return False
    return True


# --------------------------------------------------------------------- #
# Public entry point
# --------------------------------------------------------------------- #


def list_store_audit(
    db: Session,
    *,
    store_id: UUID,
    actor: User,
    limit: int = 50,
    offset: int = 0,
    source: AuditSource | None = None,
    entity_type: AuditEntityType | None = None,
    action: str | None = None,
    actor_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AuditEventListResponse:
    """Return the unified, store-scoped audit feed.

    Pipeline:
      1. Validate pagination bounds.
      2. Authorize the caller for the requested store.
      3. Query each applicable source with its own filters.
      4. Normalize every row to `AuditEventRead`.
      5. Merge, then stable-sort by
         (`created_at` DESC, `source` ASC, `id` ASC).
      6. `total` = pre-pagination count.
      7. Slice `[offset:offset+limit]` after the merge.
    """
    _validate_pagination(limit, offset)
    _assert_audit_access(db, store_id=store_id, actor=actor)

    events: list[AuditEventRead] = []

    if _source_applies(
        AuditSource.inventory, source=source, entity_type=entity_type
    ):
        events.extend(
            _query_inventory_events(
                db,
                store_id=store_id,
                action=action,
                actor_id=actor_id,
                date_from=date_from,
                date_to=date_to,
            )
        )

    if _source_applies(
        AuditSource.order, source=source, entity_type=entity_type
    ):
        events.extend(
            _query_order_events(
                db,
                store_id=store_id,
                action=action,
                actor_id=actor_id,
                date_from=date_from,
                date_to=date_to,
            )
        )

    if _source_applies(
        AuditSource.product_compliance,
        source=source,
        entity_type=entity_type,
    ):
        events.extend(
            _query_compliance_events(
                db,
                store_id=store_id,
                action=action,
                actor_id=actor_id,
                date_from=date_from,
                date_to=date_to,
            )
        )

    # Stable 3-key sort via two passes. Python's sort is stable, so
    # ascending (source, id) is preserved within each created_at
    # bucket after the second pass flips to created_at DESC.
    events.sort(key=lambda e: (e.source.value, str(e.id)))
    events.sort(key=lambda e: e.created_at, reverse=True)

    total = len(events)
    page_items = events[offset : offset + limit]

    return AuditEventListResponse(
        items=page_items,
        total=total,
        limit=limit,
        offset=offset,
    )
