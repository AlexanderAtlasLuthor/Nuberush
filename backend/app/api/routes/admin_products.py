"""HTTP layer for the admin products list (F2.20.1).

Thin route: authorize via `require_admin`, parse + validate query
params, delegate to `app.services.admin_products.list_admin_products`,
return the service response unchanged.

Single endpoint:

  GET /admin/products

    admin                              →  200
    owner / manager / staff / driver   →  403
    anon                               →  401

Read-only. No mutation route is exposed here — compliance changes
flow through the existing `PATCH /products/{product_id}/compliance`
canonical endpoint, not through admin routes (F2.20.0 §3).

Product is **global** (F2.20.0 §4): this endpoint accepts no
`store_id` query parameter. Store-specific availability belongs to
inventory, not Product.
"""

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.models import ComplianceStatus
from app.db.models import User
from app.db.session import get_db
from app.schemas.admin_products import AdminProductsListResponse
from app.services import admin_products as svc


router = APIRouter(tags=["admin-products"])


@router.get(
    "/admin/products",
    response_model=AdminProductsListResponse,
)
def list_admin_products_endpoint(
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=200),
    compliance_status: ComplianceStatus | None = Query(default=None),
    allowed_for_sale: bool | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    category: str | None = Query(default=None, max_length=100),
) -> AdminProductsListResponse:
    return svc.list_admin_products(
        db,
        actor=actor,
        limit=limit,
        offset=offset,
        q=q,
        compliance_status=compliance_status,
        allowed_for_sale=allowed_for_sale,
        is_active=is_active,
        category=category,
    )
