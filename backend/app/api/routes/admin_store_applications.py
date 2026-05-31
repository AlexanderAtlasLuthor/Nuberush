"""Admin review API for store applications (F2.24.C3).

Admin-only surface for the merchant onboarding queue:

  GET  /admin/store-applications                    paginated list + filters
  GET  /admin/store-applications/{application_id}    detail + audit trail
  POST /admin/store-applications/{application_id}/approve   (blocked until C4)
  POST /admin/store-applications/{application_id}/reject    full reject flow

Thin route: authorize via `require_admin`, parse + validate, call the
service, return. Mirrors the existing admin routers (`admin_products`,
`admin_dashboard`): no router prefix, the full `/admin/...` path on each
decorator, `tags=["admin-store-applications"]`.

Approve is deliberately NOT functional in C3: the C1 CHECK constraints make
an `approved` application impossible without a provisioned store + owner,
and that atomic provisioning is F2.24.C4. The endpoint exists and is
admin-protected but returns 501 without mutating anything — see
`app.services.store_applications.approve_store_application`.
"""

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.models import StoreApplicationStatus
from app.db.models import User
from app.db.session import get_db
from app.schemas.store_applications import StoreApplicationDetailResponse
from app.schemas.store_applications import StoreApplicationListResponse
from app.schemas.store_applications import StoreApplicationRejectRequest
from app.schemas.store_applications import StoreApplicationReviewResponse
from app.services import store_applications as svc


router = APIRouter(tags=["admin-store-applications"])


@router.get(
    "/admin/store-applications",
    response_model=StoreApplicationListResponse,
)
def list_store_applications_endpoint(
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    status: StoreApplicationStatus | None = Query(default=None),
    q: str | None = Query(default=None, max_length=200),
) -> StoreApplicationListResponse:
    return svc.list_store_applications(
        db, status_filter=status, q=q, limit=limit, offset=offset
    )


@router.get(
    "/admin/store-applications/{application_id}",
    response_model=StoreApplicationDetailResponse,
)
def get_store_application_endpoint(
    application_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StoreApplicationDetailResponse:
    return svc.get_store_application(db, application_id)


@router.post(
    "/admin/store-applications/{application_id}/approve",
    response_model=StoreApplicationReviewResponse,
)
def approve_store_application_endpoint(
    application_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StoreApplicationReviewResponse:
    application = svc.approve_store_application(db, application_id, actor=actor)
    return StoreApplicationReviewResponse(
        id=application.id,
        status=application.status,
        reviewed_by_user_id=application.reviewed_by_user_id,
        reviewed_at=application.reviewed_at,
        provisioned_store_id=application.provisioned_store_id,
        provisioned_owner_user_id=application.provisioned_owner_user_id,
        rejection_reason=application.rejection_reason,
        message="Application approved.",
    )


@router.post(
    "/admin/store-applications/{application_id}/reject",
    response_model=StoreApplicationReviewResponse,
)
def reject_store_application_endpoint(
    application_id: UUID,
    payload: StoreApplicationRejectRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StoreApplicationReviewResponse:
    application = svc.reject_store_application(
        db, application_id, payload, actor=actor
    )
    return StoreApplicationReviewResponse(
        id=application.id,
        status=application.status,
        reviewed_by_user_id=application.reviewed_by_user_id,
        reviewed_at=application.reviewed_at,
        rejection_reason=application.rejection_reason,
        message="Application rejected.",
    )
