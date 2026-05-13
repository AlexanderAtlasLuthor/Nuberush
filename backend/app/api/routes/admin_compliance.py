"""HTTP layer for admin compliance oversight (F2.20.2).

Thin routes: authorize via `require_admin`, parse + validate query
params, delegate to `app.services.admin_compliance`, return the
service response unchanged.

Two endpoints:

  GET /admin/compliance

    admin                              →  200
    owner / manager / staff / driver   →  403
    anon                               →  401

  GET /admin/compliance/products

    admin                              →  200
    owner / manager / staff / driver   →  403
    anon                               →  401

Read-only. No mutation routes are exposed here. Compliance state
changes flow through the existing canonical endpoint
`PATCH /products/{product_id}/compliance` (F2.20.0 §3) — this
module deliberately does NOT introduce
`PATCH /admin/compliance/products/{product_id}/review` or any
duplicate compliance-review path.

Product is **global** (F2.20.0 §4): the queue endpoint does NOT
accept a `store_id` query parameter.
"""

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.models import ComplianceStatus
from app.db.models import User
from app.db.session import get_db
from app.schemas.admin_compliance import AdminComplianceProductsListResponse
from app.schemas.admin_compliance import AdminComplianceSummary
from app.services import admin_compliance as svc


router = APIRouter(tags=["admin-compliance"])


@router.get(
    "/admin/compliance",
    response_model=AdminComplianceSummary,
)
def get_admin_compliance_summary_endpoint(
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminComplianceSummary:
    return svc.get_admin_compliance_summary(db, actor=actor)


@router.get(
    "/admin/compliance/products",
    response_model=AdminComplianceProductsListResponse,
)
def list_admin_compliance_products_endpoint(
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    q: str | None = Query(default=None, max_length=200),
    compliance_status: ComplianceStatus | None = Query(default=None),
    allowed_for_sale: bool | None = Query(default=None),
    is_active: bool | None = Query(default=None),
) -> AdminComplianceProductsListResponse:
    return svc.list_admin_compliance_products(
        db,
        actor=actor,
        limit=limit,
        offset=offset,
        q=q,
        compliance_status=compliance_status,
        allowed_for_sale=allowed_for_sale,
        is_active=is_active,
    )
