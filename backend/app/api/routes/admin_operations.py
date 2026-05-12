"""HTTP layer for the admin operations alerts feed (F2.19.2).

Thin route: authorize via `require_admin`, parse + validate query
params, delegate to
`app.services.admin_operations.list_admin_operations_alerts`, return
the service response unchanged.

Single endpoint:

  GET /admin/operations/alerts

    admin                              →  200
    owner / manager / staff / driver   →  403
    anon                               →  401

Read-only. Computed-on-request. No persistence. No alert mutations
(no acknowledge, dismiss, resolve, snooze).
"""

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.models import User
from app.db.session import get_db
from app.schemas.admin_operations import AdminOperationsAlertCategory
from app.schemas.admin_operations import AdminOperationsAlertSeverity
from app.schemas.admin_operations import AdminOperationsAlertsListResponse
from app.services import admin_operations as svc


router = APIRouter(tags=["admin-operations"])


@router.get(
    "/admin/operations/alerts",
    response_model=AdminOperationsAlertsListResponse,
)
def list_admin_operations_alerts_endpoint(
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    category: AdminOperationsAlertCategory | None = Query(default=None),
    severity: AdminOperationsAlertSeverity | None = Query(default=None),
    store_id: UUID | None = Query(default=None),
    aging_minutes: int = Query(default=1440, ge=1),
) -> AdminOperationsAlertsListResponse:
    return svc.list_admin_operations_alerts(
        db,
        actor=actor,
        limit=limit,
        offset=offset,
        category=category,
        severity=severity,
        store_id=store_id,
        aging_minutes=aging_minutes,
    )
