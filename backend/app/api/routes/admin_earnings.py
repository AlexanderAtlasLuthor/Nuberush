"""HTTP layer for the admin earnings surface.

Thin route: authorize via `require_admin`, delegate to
`app.services.earnings.get_admin_earnings_summary`, return the service
response unchanged.

Single endpoint:

  GET /admin/earnings

    admin                              -> 200
    owner / manager / staff / driver   -> 403
    anon                               -> 401
"""

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.models import User
from app.db.session import get_db
from app.schemas.earnings import AdminEarningsSummary
from app.services import earnings as svc


router = APIRouter(tags=["admin-earnings"])


@router.get(
    "/admin/earnings",
    response_model=AdminEarningsSummary,
)
def get_admin_earnings_endpoint(
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminEarningsSummary:
    return svc.get_admin_earnings_summary(db, actor=actor)
