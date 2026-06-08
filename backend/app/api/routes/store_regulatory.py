"""Store-scoped, read-only Regulatory surface (F2.27.6).

Two GET endpoints under `/stores/{store_id}/regulatory`:

  - GET /stores/{store_id}/regulatory/alerts            (paginated list)
  - GET /stores/{store_id}/regulatory/alerts/{alert_id} (single, store-scoped)

Tenancy is enforced by `require_store_member` (admin bypasses for any active
store; a store user may only read their own store) plus `require_staff_or_above`
for the role gate — mirroring the inventory read tier (admin/owner/manager/staff
allowed, driver/anon denied).

There are NO mutation endpoints here by design. acknowledge / dismiss / resolve,
detect-matches, create-alerts, ingest and the aggregate/decision trail all stay
on the admin surface (`/admin/regulatory/*`). This router never calls a
lifecycle function, writes an audit row, or exposes admin resolution metadata.
"""

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi import status
from sqlalchemy.orm import Session

from app.api.deps import require_staff_or_above
from app.api.deps import require_store_member
from app.db.models import ComplianceAlertSeverity
from app.db.models import ComplianceAlertStatus
from app.db.models import ComplianceRecommendedAction
from app.db.models import User
from app.db.session import get_db
from app.schemas.regulatory import StoreComplianceAlertListResponse
from app.schemas.regulatory import StoreComplianceAlertRead
from app.services import store_regulatory as svc


router = APIRouter(tags=["store-regulatory"])


@router.get(
    "/stores/{store_id}/regulatory/alerts",
    response_model=StoreComplianceAlertListResponse,
    dependencies=[Depends(require_store_member)],
)
def list_store_regulatory_alerts_endpoint(
    store_id: UUID,
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: ComplianceAlertStatus | None = Query(default=None),
    severity: ComplianceAlertSeverity | None = Query(default=None),
    recommended_action: ComplianceRecommendedAction | None = Query(
        default=None
    ),
    product_id: UUID | None = Query(default=None),
) -> StoreComplianceAlertListResponse:
    return svc.list_store_regulatory_alerts(
        db,
        store_id=store_id,
        limit=limit,
        offset=offset,
        status_filter=status,
        severity=severity,
        recommended_action=recommended_action,
        product_id=product_id,
    )


@router.get(
    "/stores/{store_id}/regulatory/alerts/{alert_id}",
    response_model=StoreComplianceAlertRead,
    dependencies=[Depends(require_store_member)],
)
def get_store_regulatory_alert_endpoint(
    store_id: UUID,
    alert_id: UUID,
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> StoreComplianceAlertRead:
    alert = svc.get_store_regulatory_alert_detail(
        db, store_id=store_id, alert_id=alert_id
    )
    if alert is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Regulatory alert not found.",
        )
    return alert
