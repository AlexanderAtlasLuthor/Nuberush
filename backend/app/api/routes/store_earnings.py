"""HTTP layer for the store-scoped earnings surface.

Thin route: validate store membership + staff role, delegate to
`app.services.earnings.get_store_earnings_summary`, return the service
response unchanged.

Single endpoint:

  GET /stores/{store_id}/earnings

    admin / owner / manager / staff   -> 200 (with membership)
    driver                            -> 403
    non-member                        -> 403
    anon                              -> 401
"""

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import require_staff_or_above
from app.api.deps import require_store_member
from app.db.models import User
from app.db.session import get_db
from app.schemas.earnings import StoreEarningsSummary
from app.services import earnings as svc


router = APIRouter(tags=["store-earnings"])


@router.get(
    "/stores/{store_id}/earnings",
    response_model=StoreEarningsSummary,
    dependencies=[Depends(require_store_member)],
)
def get_store_earnings_endpoint(
    store_id: UUID,
    _: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> StoreEarningsSummary:
    return svc.get_store_earnings_summary(db, store_id=store_id)
