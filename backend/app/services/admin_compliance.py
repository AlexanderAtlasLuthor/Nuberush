"""Service layer for admin compliance oversight (F2.20.2).

Backs two endpoints:

  - `GET /admin/compliance`              → AdminComplianceSummary
  - `GET /admin/compliance/products`     → AdminComplianceProductsListResponse

Locked rules (F2.20.0 §6, §7, §8):

- Admin-only. Non-admin actors → 403 at the service boundary,
  matching `app.services.admin_dashboard` / `admin_operations` /
  `admin_products`.
- Read-only end-to-end. No `db.add`, `db.delete`, `db.commit`.
- Backend-computed: every count and every queue row is derived
  from `Product` and `ProductComplianceAuditLog` at request time.
  No persistence introduced.
- The shared compliance blocker predicate (F2.20.0 §8) is owned
  by `app.services.compliance_predicates`. This module imports
  it; the F2.19 dashboard / operations services still inline the
  equivalent rule and are not refactored here (F2.20.0 §13 keeps
  F2.19 service changes out of this subphase).
- No `store_id` semantics — Product is global (F2.20.0 §4).
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
from app.db.models import Product
from app.db.models import ProductComplianceAuditLog
from app.db.models import User
from app.db.models import UserRole
from app.schemas.admin_compliance import AdminComplianceProductCounts
from app.schemas.admin_compliance import AdminComplianceProductsListResponse
from app.schemas.admin_compliance import AdminComplianceQueueCounts
from app.schemas.admin_compliance import AdminComplianceReviewSummary
from app.schemas.admin_compliance import AdminComplianceSummary
from app.schemas.products import ProductComplianceAuditLogRead
from app.schemas.products import ProductRead
from app.services.compliance_predicates import (
    BLOCKING_COMPLIANCE_STATUSES,
)
from app.services.compliance_predicates import (
    product_compliance_blocker_predicate,
)


# Bounded recent-reviews tail (F2.20.0 §7). Service-owned invariant —
# not caller-tunable. Capped at 10 to match the dashboard-style
# bounded-tail policy from F2.19.
_RECENT_REVIEWS_LIMIT = 10


# --------------------------------------------------------------------- #
# RBAC + helpers
# --------------------------------------------------------------------- #


def _assert_admin_caller(actor: User) -> None:
    """Service-level RBAC gate.

    Symmetric with the other admin services so direct callers
    (admin scripts, batch jobs) match the HTTP route contract.
    """
    if actor.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )


def _normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


# --------------------------------------------------------------------- #
# Summary computation
# --------------------------------------------------------------------- #


def _compute_product_counts(db: Session) -> AdminComplianceProductCounts:
    """Compute every Product count in a single round-trip via
    conditional aggregates.

    Same shape the dashboard uses for stores / users (see
    `app.services.admin_dashboard._stores_summary`): one
    `func.coalesce(func.sum(case(...)))` per bucket so we avoid
    eight separate scans of `products`.

    `blocked` mirrors the shared predicate from
    `app.services.compliance_predicates` — kept in sync with the
    list endpoint by construction.
    """

    def _sum_when(cond) -> object:
        return func.coalesce(
            func.sum(case((cond, 1), else_=0)),
            0,
        )

    allowed_expr = _sum_when(
        Product.compliance_status == ComplianceStatus.allowed
    )
    restricted_expr = _sum_when(
        Product.compliance_status == ComplianceStatus.restricted
    )
    banned_expr = _sum_when(
        Product.compliance_status == ComplianceStatus.banned
    )
    blocked_expr = _sum_when(
        or_(
            Product.allowed_for_sale.is_(False),
            Product.compliance_status.in_(BLOCKING_COMPLIANCE_STATUSES),
        )
    )
    allowed_for_sale_expr = _sum_when(
        Product.allowed_for_sale.is_(True)
    )
    not_allowed_for_sale_expr = _sum_when(
        Product.allowed_for_sale.is_(False)
    )
    inactive_expr = _sum_when(Product.is_active.is_(False))

    stmt = select(
        func.count(Product.id),
        allowed_expr,
        restricted_expr,
        banned_expr,
        blocked_expr,
        allowed_for_sale_expr,
        not_allowed_for_sale_expr,
        inactive_expr,
    )
    (
        total,
        allowed,
        restricted,
        banned,
        blocked,
        allowed_for_sale,
        not_allowed_for_sale,
        inactive,
    ) = db.execute(stmt).one()

    return AdminComplianceProductCounts(
        total=int(total or 0),
        allowed=int(allowed or 0),
        restricted=int(restricted or 0),
        banned=int(banned or 0),
        blocked=int(blocked or 0),
        allowed_for_sale=int(allowed_for_sale or 0),
        not_allowed_for_sale=int(not_allowed_for_sale or 0),
        inactive=int(inactive or 0),
    )


def _compute_review_summary(
    db: Session,
) -> AdminComplianceReviewSummary:
    """Bounded recent compliance reviews ordered deterministically.

    Ordering: `created_at DESC, id DESC`. The trailing `id DESC`
    breaks ties so simultaneous reviews (same `created_at`) are
    returned in a stable order across calls.

    `recent_count` is the size of the returned `recent` list —
    not a lifetime audit count.
    """
    stmt = (
        select(ProductComplianceAuditLog)
        .order_by(
            ProductComplianceAuditLog.created_at.desc(),
            ProductComplianceAuditLog.id.desc(),
        )
        .limit(_RECENT_REVIEWS_LIMIT)
    )
    rows = list(db.scalars(stmt).all())
    recent = [
        ProductComplianceAuditLogRead.model_validate(row) for row in rows
    ]
    return AdminComplianceReviewSummary(
        recent_count=len(recent),
        recent=recent,
    )


def _compute_queue_counts(db: Session) -> AdminComplianceQueueCounts:
    """Compliance queue cardinalities in one round-trip.

    `total` is the blocker-predicate union; `banned`, `restricted`
    and `not_allowed_for_sale` are independent category counts and
    may overlap.
    """

    def _sum_when(cond) -> object:
        return func.coalesce(
            func.sum(case((cond, 1), else_=0)),
            0,
        )

    total_expr = _sum_when(
        or_(
            Product.allowed_for_sale.is_(False),
            Product.compliance_status.in_(BLOCKING_COMPLIANCE_STATUSES),
        )
    )
    banned_expr = _sum_when(
        Product.compliance_status == ComplianceStatus.banned
    )
    restricted_expr = _sum_when(
        Product.compliance_status == ComplianceStatus.restricted
    )
    not_allowed_for_sale_expr = _sum_when(
        Product.allowed_for_sale.is_(False)
    )

    stmt = select(
        total_expr,
        banned_expr,
        restricted_expr,
        not_allowed_for_sale_expr,
    )
    total, banned, restricted, not_allowed_for_sale = (
        db.execute(stmt).one()
    )

    return AdminComplianceQueueCounts(
        total=int(total or 0),
        banned=int(banned or 0),
        restricted=int(restricted or 0),
        not_allowed_for_sale=int(not_allowed_for_sale or 0),
    )


def get_admin_compliance_summary(
    db: Session,
    *,
    actor: User,
) -> AdminComplianceSummary:
    """Return the admin compliance summary.

    Pipeline (F2.20.0 §7):

      1. RBAC gate (admin only; 403 otherwise).
      2. Product counts (single aggregate round-trip).
      3. Bounded recent reviews tail.
      4. Queue counts (single aggregate round-trip).

    Read-only end-to-end.
    """
    _assert_admin_caller(actor)

    products = _compute_product_counts(db)
    reviews = _compute_review_summary(db)
    queue = _compute_queue_counts(db)

    return AdminComplianceSummary(
        products=products,
        reviews=reviews,
        queue=queue,
    )


# --------------------------------------------------------------------- #
# Compliance products list (queue)
# --------------------------------------------------------------------- #


def list_admin_compliance_products(
    db: Session,
    *,
    actor: User,
    limit: int = 50,
    offset: int = 0,
    q: str | None = None,
    compliance_status: ComplianceStatus | None = None,
    allowed_for_sale: bool | None = None,
    is_active: bool | None = None,
) -> AdminComplianceProductsListResponse:
    """Return the filtered, ordered, paginated compliance queue.

    Pipeline (F2.20.0 §7):

      1. RBAC gate (admin only; 403 otherwise).
      2. Default-queue rule: when neither `compliance_status` nor
         `allowed_for_sale` is provided, restrict the result to
         products matching the shared blocker predicate. When
         either explicit filter is provided, the caller is taking
         control of the predicate and the default is NOT applied,
         so callers can intentionally inspect allowed /
         allowed_for_sale products via the queue endpoint.
      3. Apply explicit filters.
      4. Count matches BEFORE pagination → `total`.
      5. Deterministic ordering: `updated_at DESC, created_at DESC,
         name ASC, id ASC`. Same ordering as the admin products
         list so a queue row appears consistently across surfaces.
      6. Slice `[offset:offset+limit]`.

    No `store_id` filter (F2.20.0 §4). No mutations.
    """
    _assert_admin_caller(actor)

    q_value = _normalize_optional_text(q)

    stmt = select(Product)
    count_stmt = select(func.count()).select_from(Product)

    # Default queue rule: only apply the blocker predicate when the
    # caller has not opted into explicit compliance_status or
    # allowed_for_sale filters. Explicit filters give the caller
    # full control (including looking at allowed / allowed_for_sale
    # products through the queue endpoint).
    use_default_queue = (
        compliance_status is None and allowed_for_sale is None
    )
    if use_default_queue:
        predicate = product_compliance_blocker_predicate()
        stmt = stmt.where(predicate)
        count_stmt = count_stmt.where(predicate)

    if compliance_status is not None:
        stmt = stmt.where(Product.compliance_status == compliance_status)
        count_stmt = count_stmt.where(
            Product.compliance_status == compliance_status
        )

    if allowed_for_sale is not None:
        stmt = stmt.where(Product.allowed_for_sale.is_(allowed_for_sale))
        count_stmt = count_stmt.where(
            Product.allowed_for_sale.is_(allowed_for_sale)
        )

    if is_active is not None:
        stmt = stmt.where(Product.is_active.is_(is_active))
        count_stmt = count_stmt.where(Product.is_active.is_(is_active))

    if q_value is not None:
        pattern = f"%{q_value}%"
        search = or_(
            Product.name.ilike(pattern),
            Product.brand.ilike(pattern),
            Product.category.ilike(pattern),
            Product.description.ilike(pattern),
        )
        stmt = stmt.where(search)
        count_stmt = count_stmt.where(search)

    total = int(db.scalar(count_stmt) or 0)

    stmt = (
        stmt.order_by(
            Product.updated_at.desc(),
            Product.created_at.desc(),
            Product.name.asc(),
            Product.id.asc(),
        )
        .limit(limit)
        .offset(offset)
    )

    rows = list(db.scalars(stmt).all())
    items = [ProductRead.model_validate(row) for row in rows]

    return AdminComplianceProductsListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
