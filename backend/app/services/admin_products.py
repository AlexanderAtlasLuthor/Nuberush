"""Service layer for the admin products list (F2.20.1).

Read-only, admin-only, paginated, filterable list of every global
`Product` row. Backs `GET /admin/products`.

Locked rules (F2.20.0 §4, §6):

- Product is **global**. There is no `store_id` filter — store-scoped
  availability lives on `InventoryItem`, not Product.
- Read-only: no `db.add`, `db.delete`, or `db.commit`.
- `total` is the filtered count BEFORE pagination so the wire shape
  matches the rest of the admin list envelopes.
- Deterministic ordering before slice: `updated_at DESC, created_at
  DESC, name ASC, id ASC`. The trailing `id ASC` breaks ties so two
  consecutive calls always return the same page.

RBAC: admin-only. Non-admin actors → 403 at the service boundary so
direct callers (admin scripts, batch jobs) see the same contract as
the HTTP route. Mirrors `app.services.admin_dashboard._assert_admin_caller`
and `app.services.admin_operations._assert_admin_caller`.
"""

from __future__ import annotations

from fastapi import HTTPException
from fastapi import status
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ComplianceStatus
from app.db.models import Product
from app.db.models import ProductApprovalStatus
from app.db.models import User
from app.db.models import UserRole
from app.schemas.admin_products import AdminProductsListResponse
from app.schemas.products import ProductRead


def _assert_admin_caller(actor: User) -> None:
    """Service-level RBAC gate.

    Defense in depth: the route already enforces `require_admin`,
    but a direct service caller is also gated so admin scripts and
    batch jobs match the HTTP contract.
    """
    if actor.role != UserRole.admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required.",
        )


def _normalize_optional_text(value: str | None) -> str | None:
    """Strip whitespace; treat empty as absent.

    Matches the convention used by other list services (users,
    stores) so admin clients see the same filter semantics across
    the admin surfaces.
    """
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def list_admin_products(
    db: Session,
    *,
    actor: User,
    limit: int = 50,
    offset: int = 0,
    q: str | None = None,
    compliance_status: ComplianceStatus | None = None,
    approval_status: ProductApprovalStatus | None = None,
    allowed_for_sale: bool | None = None,
    is_active: bool | None = None,
    category: str | None = None,
) -> AdminProductsListResponse:
    """Return the filtered, ordered, paginated admin products page.

    Pipeline (locked by F2.20.0 §6):

      1. RBAC gate (admin-only; 403 otherwise).
      2. Build the filtered SELECT against `Product`.
      3. Count matches BEFORE pagination → `total`.
      4. Apply deterministic ordering: `updated_at DESC, created_at
         DESC, name ASC, id ASC`.
      5. Slice `[offset:offset+limit]`.

    Read-only end-to-end. No `store_id` filter — Product is global
    (F2.20.0 §4) and store-specific availability lives on
    `InventoryItem`, not Product.
    """
    _assert_admin_caller(actor)

    q_value = _normalize_optional_text(q)
    category_value = _normalize_optional_text(category)

    stmt = select(Product)
    count_stmt = select(func.count()).select_from(Product)

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

    if compliance_status is not None:
        stmt = stmt.where(Product.compliance_status == compliance_status)
        count_stmt = count_stmt.where(
            Product.compliance_status == compliance_status
        )

    if approval_status is not None:
        stmt = stmt.where(Product.approval_status == approval_status)
        count_stmt = count_stmt.where(
            Product.approval_status == approval_status
        )

    if allowed_for_sale is not None:
        stmt = stmt.where(Product.allowed_for_sale.is_(allowed_for_sale))
        count_stmt = count_stmt.where(
            Product.allowed_for_sale.is_(allowed_for_sale)
        )

    if is_active is not None:
        stmt = stmt.where(Product.is_active.is_(is_active))
        count_stmt = count_stmt.where(Product.is_active.is_(is_active))

    if category_value is not None:
        # Case-insensitive match keeps the filter forgiving for admins
        # typing free-form category names without worrying about the
        # exact stored casing.
        stmt = stmt.where(Product.category.ilike(category_value))
        count_stmt = count_stmt.where(
            Product.category.ilike(category_value)
        )

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

    return AdminProductsListResponse(
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )
