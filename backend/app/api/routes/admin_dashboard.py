"""HTTP layer for the admin dashboard aggregator (F2.19.1).

Thin route: authorize via `require_admin`, hand the actor + db to
`app.services.admin_dashboard.get_admin_dashboard_summary`, return
the service response unchanged.

Single endpoint:

  GET /admin/dashboard

    admin                              →  200
    owner / manager / staff / driver   →  403
    anon                               →  401

No path params, no query params, no mutations. Response is a single
`AdminDashboardSummary` object; pagination lives inside the bounded
recent tails owned by the service.
"""

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.models import User
from app.db.session import get_db
from app.schemas.admin_dashboard import AdminDashboardSummary
from app.services import admin_dashboard as svc


router = APIRouter(tags=["admin-dashboard"])


@router.get(
    "/admin/dashboard",
    response_model=AdminDashboardSummary,
)
def get_admin_dashboard_endpoint(
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminDashboardSummary:
    return svc.get_admin_dashboard_summary(db, actor=actor)
