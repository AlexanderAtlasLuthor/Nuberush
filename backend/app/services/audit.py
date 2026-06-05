"""Service layer for the unified audit feed (F2.16.2 + F2.17.4).

Two public entry points share the same normalizers, filters, merge,
sort, and pagination machinery:

  - `list_store_audit`  (F2.16.2) — store-scoped feed, role matrix
    `admin/owner/manager/staff` with `require_store_member` semantics.
  - `list_admin_audit`  (F2.17.4) — admin-only global or single-store
    feed, with `store_id` optional.

Both aggregate the same three append-only log tables — `inventory_logs`,
`order_audit_logs`, and `product_compliance_audit_logs` — into the
normalized `AuditEventRead` shape locked in F2.16.1. No new tables, no
migrations, no model changes. No new `AuditSource` enum values.

The compliance source has no `store_id` column; this module owns the
join that maps a product's compliance history to one or more stores:

  ProductComplianceAuditLog.product_id
    -> ProductVariant.product_id
    -> InventoryItem.variant_id
    -> InventoryItem.store_id

In the store-scoped path the join is filtered by the requested store
and yields exactly one event per audit row for that store. In the
global path the join is unfiltered and produces one event per
(log, store_id) pair — a compliance change fans out across every store
that currently carries the product. A Python-side dedupe by
`(log.id, store_id)` collapses duplicates from a product having
multiple variants/items in the same store.

RBAC:

  list_store_audit (F2.16.2):
    - admin: any active store; 404 if missing; 400 if inactive.
    - owner / manager / staff: own active store only; cross-store and
      unknown-store collapse to 403 to avoid existence-probe leaks;
      400 if their own store is inactive.
    - driver: 403 (role gate; never sees the audit surface).
    - anonymous: not reachable here — `current_user` injection runs in
      the route.

  list_admin_audit (F2.17.4):
    - admin only; everyone else → 403.
    - When `store_id` is provided, the store must exist; unknown → 404.
      Inactive stores are still readable (audit history of a
      deactivated store remains available to admin), so the 400
      response from `_assert_audit_access` is intentionally NOT
      mirrored here.

Pagination guards run at the service boundary so routes can stay
thin: limit must be 1..200, offset must be >= 0. Out-of-range values
raise 422 — same status code routes encode via `Query(ge=..., le=...)`,
so direct callers (admin scripts, batch jobs) get the same contract.
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
from app.db.models import OperationalAuditLog
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


def _assert_admin_caller(actor: User) -> None:
    """RBAC gate for the global / admin audit feed (F2.17.4).

    Symmetric with `app.services.users._assert_admin_caller` and
    `app.services.stores._assert_admin_caller`. Kept local to the
    module instead of inventing a shared helper because each service
    owns its own RBAC source of truth.
    """
    if actor.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
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
    store_id: UUID | None,
    action: str | None,
    actor_id: UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[AuditEventRead]:
    """Normalize `inventory_logs` rows into `AuditEventRead`.

    `store_id=None` means "no store filter" (admin global path).
    `store_id` set to a UUID scopes the query to one store, matching
    the F2.16.2 store-scoped behavior.
    """
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

    stmt = select(InventoryLog)
    if store_id is not None:
        stmt = stmt.where(InventoryLog.store_id == store_id)
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
    store_id: UUID | None,
    action: str | None,
    actor_id: UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[AuditEventRead]:
    """Normalize `order_audit_logs` rows into `AuditEventRead`.

    `store_id=None` means "no store filter" (admin global path).
    """
    stmt = select(OrderAuditLog)
    if store_id is not None:
        stmt = stmt.where(OrderAuditLog.store_id == store_id)
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
    store_id: UUID | None,
    action: str | None,
    actor_id: UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
) -> list[AuditEventRead]:
    """Compliance events resolved via the catalog→inventory join path.

    `Product` has no `store_id`; a compliance audit row is relevant to
    a store only when that store currently carries inventory for at
    least one variant of the product.

    When `store_id` is a concrete UUID (F2.16.2 store-scoped path):
      - The join is filtered to that store.
      - Each emitted event carries `store_id == requested`.
      - A product with multiple variants/items in that store yields
        ONE event per audit log row.

    When `store_id is None` (F2.17.4 admin global path):
      - The join is unfiltered.
      - Each audit row fans out to one event per store that carries
        the product.
      - Dedupe is by `(log.id, store_id)` so a product with multiple
        variants/items in the SAME store still yields one event for
        that store.

    The tuple select `(ProductComplianceAuditLog, InventoryItem.store_id)`
    is used in both paths so the emitted event's `store_id` always
    reflects the actual carrying store (equal to the requested one in
    the scoped path; varying across rows in the global path).
    """
    if action is not None and action != _COMPLIANCE_ACTION:
        return []

    stmt = (
        select(ProductComplianceAuditLog, InventoryItem.store_id)
        .join(
            ProductVariant,
            ProductVariant.product_id == ProductComplianceAuditLog.product_id,
        )
        .join(
            InventoryItem,
            InventoryItem.variant_id == ProductVariant.id,
        )
    )
    if store_id is not None:
        stmt = stmt.where(InventoryItem.store_id == store_id)
    if actor_id is not None:
        stmt = stmt.where(
            ProductComplianceAuditLog.changed_by_user_id == actor_id
        )
    if date_from is not None:
        stmt = stmt.where(ProductComplianceAuditLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(ProductComplianceAuditLog.created_at <= date_to)

    rows = list(db.execute(stmt).all())

    # Dedupe by (log.id, event_store_id). The join enumerates one row
    # per matching inventory item, so a product with N variants and/or
    # M items per variant in the same store produces N*M raw rows for
    # one audit event — collapse them here. We avoid SQL DISTINCT
    # because the multi-column select makes its semantics less obvious
    # than a tight Python pass.
    seen: set[tuple[UUID, UUID]] = set()
    events: list[AuditEventRead] = []
    for log, event_store_id in rows:
        key = (log.id, event_store_id)
        if key in seen:
            continue
        seen.add(key)
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
                store_id=event_store_id,
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
# Operational source normalizer (F2.26.2.C)
# --------------------------------------------------------------------- #


# Stable action → summary map. Summaries are constant strings only — no
# names, emails, store names, or any PII is ever interpolated (the row's
# before/after already carry the allow-listed detail, surfaced via
# metadata). Mirrors the literal style of `_inventory_summary` etc. but
# is a pure lookup so it cannot leak.
_OPERATIONAL_SUMMARY: dict[str, str] = {
    "user_created": "User created",
    "user_updated": "User updated",
    "user_role_changed": "User role changed",
    "user_store_assigned": "User assigned to store",
    "user_store_removed": "User removed from store",
    "user_activated": "User activated",
    "user_deactivated": "User deactivated",
    "store_created": "Store created",
    "store_updated": "Store updated",
    "store_activated": "Store activated",
    "store_deactivated": "Store deactivated",
}


# operational `target_type` (a varchar on the row) → the feed entity type.
# Rows whose target_type is not in this map are skipped by the normalizer
# rather than raising, so one unrecognized row can never break the feed.
_OPERATIONAL_TARGET_ENTITY: dict[str, AuditEntityType] = {
    "user": AuditEntityType.user,
    "store": AuditEntityType.store,
}


def _operational_summary(log: OperationalAuditLog) -> str:
    """Stable, PII-free summary for an operational event.

    Falls back to a humanized action (e.g. `user_frobnicated` →
    `User frobnicated`) so the value is always non-empty even if an
    action lands here without a mapped summary — `AuditEventRead`
    rejects an empty summary, so a useful fallback beats a 500.
    """
    mapped = _OPERATIONAL_SUMMARY.get(log.action)
    if mapped is not None:
        return mapped
    humanized = log.action.replace("_", " ").strip()
    return humanized.capitalize() if humanized else log.action


def _entity_type_to_target_type(entity_type: AuditEntityType) -> str | None:
    """Reverse-map a requested entity_type to an operational target_type
    string, or None when the entity_type is not one operational emits."""
    for target_type, mapped in _OPERATIONAL_TARGET_ENTITY.items():
        if mapped == entity_type:
            return target_type
    return None


def _query_operational_events(
    db: Session,
    *,
    store_id: UUID | None,
    action: str | None,
    actor_id: UUID | None,
    date_from: datetime | None,
    date_to: datetime | None,
    entity_type: AuditEntityType | None = None,
) -> list[AuditEventRead]:
    """Normalize `operational_audit_logs` rows into `AuditEventRead`.

    `store_id=None` means "no store filter" (admin global path). A
    concrete `store_id` filters `OperationalAuditLog.store_id == store_id`
    — because `NULL == <uuid>` is false in SQL, this naturally EXCLUDES
    global (NULL-store) events and other stores' events, which is exactly
    the store-feed visibility rule (a store user never sees global
    operational events).

    `entity_type` is honored at the ROW level: this source spans both
    `user` and `store` targets, so an `entity_type` filter must keep only
    the matching `target_type` rows (the source-level gate in
    `_source_applies` cannot split a multi-entity source). An
    `entity_type` that operational does not emit (e.g. `order`) yields an
    empty list.

    Rows whose `target_type` is unrecognized are skipped — one bad row
    never breaks the whole feed.
    """
    if entity_type is not None:
        target_type_filter = _entity_type_to_target_type(entity_type)
        if target_type_filter is None:
            # Requested entity is not one operational emits → no rows.
            return []
    else:
        target_type_filter = None

    stmt = select(OperationalAuditLog)
    if store_id is not None:
        stmt = stmt.where(OperationalAuditLog.store_id == store_id)
    if target_type_filter is not None:
        stmt = stmt.where(
            OperationalAuditLog.target_type == target_type_filter
        )
    if action is not None:
        stmt = stmt.where(OperationalAuditLog.action == action)
    if actor_id is not None:
        stmt = stmt.where(OperationalAuditLog.actor_user_id == actor_id)
    if date_from is not None:
        stmt = stmt.where(OperationalAuditLog.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(OperationalAuditLog.created_at <= date_to)

    rows = list(db.scalars(stmt).all())
    events: list[AuditEventRead] = []
    for log in rows:
        mapped_entity = _OPERATIONAL_TARGET_ENTITY.get(log.target_type)
        if mapped_entity is None:
            # Unknown target_type — skip defensively rather than raise.
            continue
        # Build metadata without mutating the row's stored dict. before/
        # after are already allow-listed + redacted by the writer, so they
        # are safe to surface; they are included even when None so the UI
        # can distinguish "no snapshot" from "absent key".
        metadata: dict[str, Any] = {
            **(log.event_metadata or {}),
            "before": log.before,
            "after": log.after,
        }
        events.append(
            AuditEventRead(
                id=log.id,
                source=AuditSource.operational,
                store_id=log.store_id,
                actor_id=log.actor_user_id,
                action=log.action,
                entity_type=mapped_entity,
                entity_id=log.target_id,
                summary=_operational_summary(log),
                metadata=metadata,
                created_at=log.created_at,
            )
        )
    return events


# --------------------------------------------------------------------- #
# Source-applicability gate
# --------------------------------------------------------------------- #


# Which entity types each source may emit. Most sources map to exactly
# one entity type, but `operational` spans two (`user` and `store`) — the
# first multi-entity source (F2.26.2.B). Modeling every binding as a SET
# keeps the gate uniform: an `entity_type` filter is honored by set
# membership rather than scalar equality. If both `source` and
# `entity_type` are set and the entity is not in the source's set, that
# source contributes zero rows — applying that rule centrally is cleaner
# than threading two flags into each query helper.
#
# Note (F2.26.2.B): `operational` is listed here so the gate admits it,
# but its normalizer (`_query_operational_events`) is NOT wired yet — so
# a `source=operational` query still yields an empty page until
# F2.26.2.C/D. The binding change is intentionally decoupled from the
# query wiring.
_SOURCE_ENTITY_BINDING: dict[AuditSource, frozenset[AuditEntityType]] = {
    AuditSource.inventory: frozenset({AuditEntityType.inventory_item}),
    AuditSource.order: frozenset({AuditEntityType.order}),
    AuditSource.product_compliance: frozenset({AuditEntityType.product}),
    AuditSource.operational: frozenset(
        {AuditEntityType.user, AuditEntityType.store}
    ),
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
        and entity_type not in _SOURCE_ENTITY_BINDING[candidate]
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

    if _source_applies(
        AuditSource.operational, source=source, entity_type=entity_type
    ):
        # Store-scoped: a concrete `store_id` filters
        # `OperationalAuditLog.store_id == store_id`, which (since
        # `NULL == uuid` is false) naturally excludes global (NULL-store)
        # events and other stores' events. `entity_type` is threaded so a
        # user/store entity filter narrows at the row level (this source
        # spans both). See F2.26.2.C/D.
        events.extend(
            _query_operational_events(
                db,
                store_id=store_id,
                action=action,
                actor_id=actor_id,
                date_from=date_from,
                date_to=date_to,
                entity_type=entity_type,
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


def list_admin_audit(
    db: Session,
    *,
    actor: User,
    store_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    source: AuditSource | None = None,
    entity_type: AuditEntityType | None = None,
    action: str | None = None,
    actor_id: UUID | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> AuditEventListResponse:
    """Return the global / admin audit feed (F2.17.4).

    Admin-only entry point. Reuses the same source normalizers and
    merge/sort/paginate pipeline as `list_store_audit`. The only
    structural differences are:

      - RBAC: `_assert_admin_caller` (admin only; everyone else 403).
        Non-admins do NOT reach `_assert_audit_access`, so the
        store-scoped 400/403/404 contract from `list_store_audit` does
        not apply here.

      - Store scope: `store_id` is optional.
          * If provided, the store must exist (404 if not). Inactive
            stores are explicitly allowed — admin can read the audit
            history of a deactivated store.
          * If omitted, all three sources contribute events from every
            store. Compliance fans out one event per (audit row,
            carrying store) pair; dedupe is by `(log.id, store_id)`.

    Pipeline:
      1. Authorize: admin only.
      2. Validate pagination bounds (1..200 limit, offset >= 0).
      3. If `store_id` is provided, confirm existence.
      4. Query each applicable source with `store_id` passed through.
      5. Merge + stable-sort by (`created_at` DESC, `source` ASC,
         `id` ASC).
      6. `total` = pre-pagination count; slice `[offset:offset+limit]`.
    """
    _assert_admin_caller(actor)
    _validate_pagination(limit, offset)

    if store_id is not None:
        store = db.scalar(select(Store).where(Store.id == store_id))
        if store is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Store not found.",
            )
        # Intentionally no 400 on inactive — admin global audit must
        # be able to inspect deactivated stores. Mirrors the F2.17.0
        # contract for `GET /admin/audit`.

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

    if _source_applies(
        AuditSource.operational, source=source, entity_type=entity_type
    ):
        # Admin global (`store_id is None`): no store filter → returns
        # global (NULL-store) operational events AND store-scoped events
        # from every store. Admin store-filtered (`store_id` concrete):
        # `store_id == store_id` filters to that store and excludes NULL
        # globals (consistent with how the other sources scope when a
        # store is given). `entity_type` narrows at the row level.
        events.extend(
            _query_operational_events(
                db,
                store_id=store_id,
                action=action,
                actor_id=actor_id,
                date_from=date_from,
                date_to=date_to,
                entity_type=entity_type,
            )
        )

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
