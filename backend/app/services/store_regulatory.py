"""Store-scoped, read-only projection over compliance alerts (F2.27.6).

The Store Panel regulatory surface. A store user sees ONLY the alerts whose
product is carried in that store's inventory, and only a store-safe subset of
each alert's fields (no resolution metadata, no decision trail, no match
internals). The tenancy boundary is, end to end:

    Store -> InventoryItem -> ProductVariant -> Product -> ComplianceAlert

Duplicate prevention: a store typically carries several variants of the same
product, so naively joining inventory -> alerts would fan out one alert into N
rows. We instead resolve the store's products to a DISTINCT set of product ids
in a subquery and filter `ComplianceAlert.product_id IN (...)`. The IN() is a
membership test, never a join, so each alert appears exactly once and the count
matches the page.

Strictly read-only: only SELECTs. This module never calls an admin lifecycle
function (acknowledge / dismiss / resolve / set_product_compliance), never
writes an audit row, and never mutates a Product or InventoryItem.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceAlert
from app.db.models import ComplianceAlertSeverity
from app.db.models import ComplianceAlertStatus
from app.db.models import ComplianceRecommendedAction
from app.db.models import InventoryItem
from app.db.models import Product
from app.db.models import ProductVariant
from app.db.models import RegulatoryNotice
from app.schemas.regulatory import StoreComplianceAlertListResponse
from app.schemas.regulatory import StoreComplianceAlertRead


_MAX_LIST_LIMIT = 100


def _assert_list_pagination(limit: int, offset: int) -> None:
    """Defence-in-depth pagination bounds (the route also constrains these)."""
    if limit < 1 or limit > _MAX_LIST_LIMIT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"limit must be between 1 and {_MAX_LIST_LIMIT}.",
        )
    if offset < 0:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="offset must be >= 0.",
        )


def _store_product_ids_subquery(store_id: UUID):
    """DISTINCT product ids carried in ``store_id``'s inventory.

    Walks Store -> InventoryItem -> ProductVariant -> Product. DISTINCT so a
    store carrying several variants of one product yields that product id
    exactly once; the `IN()` filter on top then cannot fan a single alert out
    into duplicate rows.
    """
    return (
        select(ProductVariant.product_id)
        .join(InventoryItem, InventoryItem.variant_id == ProductVariant.id)
        .where(InventoryItem.store_id == store_id)
        .distinct()
    )


def _store_alert_filters(
    store_id: UUID,
    *,
    status_filter: ComplianceAlertStatus | None,
    severity: ComplianceAlertSeverity | None,
    recommended_action: ComplianceRecommendedAction | None,
    product_id: UUID | None,
) -> list:
    """Shared predicates for the store list + detail queries.

    The first two predicates ARE the tenancy boundary and are never optional:
    a store user only sees product-scoped alerts (`product_id IS NOT NULL`)
    whose product lives in their inventory. `product_id` passed by the caller
    narrows WITHIN that boundary — an id outside the store's inventory simply
    matches nothing (empty result, never a 403).
    """
    filters = [
        ComplianceAlert.product_id.is_not(None),
        ComplianceAlert.product_id.in_(_store_product_ids_subquery(store_id)),
    ]
    if product_id is not None:
        filters.append(ComplianceAlert.product_id == product_id)
    if status_filter is not None:
        filters.append(ComplianceAlert.status == status_filter)
    if severity is not None:
        filters.append(ComplianceAlert.severity == severity)
    if recommended_action is not None:
        filters.append(
            ComplianceAlert.recommended_action == recommended_action
        )
    return filters


def _to_store_alert_read(
    alert: ComplianceAlert,
    notice_title: str | None,
    notice_type,
    notice_published_at,
    product_name: str | None,
) -> StoreComplianceAlertRead:
    """Project an alert row + joined context onto the store-safe schema."""
    return StoreComplianceAlertRead(
        id=alert.id,
        notice_id=alert.notice_id,
        product_id=alert.product_id,
        severity=alert.severity,
        status=alert.status,
        recommended_action=alert.recommended_action,
        created_at=alert.created_at,
        updated_at=alert.updated_at,
        notice_title=notice_title,
        notice_type=notice_type,
        notice_published_at=notice_published_at,
        product_name=product_name,
    )


def _base_select():
    """SELECT alert + store-safe joined context (notice title/type/date, name).

    Inner joins to `RegulatoryNotice` (every alert has a notice) and to
    `Product` (the tenancy filter already requires a non-null product), so the
    joins add context without changing row cardinality.
    """
    return (
        select(
            ComplianceAlert,
            RegulatoryNotice.title,
            RegulatoryNotice.notice_type,
            RegulatoryNotice.published_at,
            Product.name,
        )
        .join(
            RegulatoryNotice,
            RegulatoryNotice.id == ComplianceAlert.notice_id,
        )
        .join(Product, Product.id == ComplianceAlert.product_id)
    )


def list_store_regulatory_alerts(
    db: Session,
    *,
    store_id: UUID,
    limit: int = 25,
    offset: int = 0,
    status_filter: ComplianceAlertStatus | None = None,
    severity: ComplianceAlertSeverity | None = None,
    recommended_action: ComplianceRecommendedAction | None = None,
    product_id: UUID | None = None,
) -> StoreComplianceAlertListResponse:
    """Paginated, store-scoped list of compliance alerts, newest first.

    Only alerts whose product is in ``store_id``'s inventory are returned;
    product-less (notice-level) alerts are excluded. `total` honours the same
    filters and the same store boundary as the page, and the DISTINCT product
    subquery guarantees no duplicate rows / inflated count. Read-only.
    """
    _assert_list_pagination(limit, offset)

    filters = _store_alert_filters(
        store_id,
        status_filter=status_filter,
        severity=severity,
        recommended_action=recommended_action,
        product_id=product_id,
    )

    stmt = _base_select()
    count_stmt = select(func.count()).select_from(ComplianceAlert)
    for f in filters:
        stmt = stmt.where(f)
        count_stmt = count_stmt.where(f)

    stmt = (
        stmt.order_by(
            ComplianceAlert.created_at.desc(), ComplianceAlert.id.asc()
        )
        .limit(limit)
        .offset(offset)
    )

    rows = db.execute(stmt).all()
    total = db.scalar(count_stmt) or 0

    items = [
        _to_store_alert_read(
            alert, notice_title, notice_type, published_at, product_name
        )
        for (alert, notice_title, notice_type, published_at, product_name) in rows
    ]

    return StoreComplianceAlertListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


def get_store_regulatory_alert_detail(
    db: Session,
    *,
    store_id: UUID,
    alert_id: UUID,
) -> StoreComplianceAlertRead | None:
    """Fetch one store-scoped alert, or ``None`` if outside the boundary.

    Applies EXACTLY the same store inventory boundary as the list endpoint: an
    alert that exists globally but whose product is not carried by this store
    (or which has no product at all) returns ``None`` so the route can answer
    404 — a store user can never confirm the existence of an out-of-scope
    alert. Read-only.
    """
    stmt = _base_select().where(
        ComplianceAlert.id == alert_id,
        ComplianceAlert.product_id.is_not(None),
        ComplianceAlert.product_id.in_(_store_product_ids_subquery(store_id)),
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    alert, notice_title, notice_type, published_at, product_name = row
    return _to_store_alert_read(
        alert, notice_title, notice_type, published_at, product_name
    )
