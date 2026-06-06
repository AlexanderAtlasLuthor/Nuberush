"""HTTP layer for the admin Regulatory Intelligence API (F2.26.5.E).

Thin admin-only routes under `/admin/regulatory`: authorize via
`require_admin`, validate query/body params, delegate to
`app.services.regulatory`, and return the service response unchanged.

The routes expose the already-validated service foundation (F2.26.5.B–.D)
and add NO new business behavior:

  - sources  : list + create;
  - notices  : list + ingest (manual);
  - matching : POST .../detect-matches (explicit, idempotent);
  - alerts   : POST .../create-alerts (explicit, idempotent), list, detail;
  - lifecycle: acknowledge / dismiss / resolve(no_action|hold|ban).

Every endpoint is admin-only (admin → 2xx; owner/manager/staff/driver →
403; anon → 401), matching the other `/admin/*` routers. Side effects stay
in the service layer: ingest never auto-matches, detect-matches never
auto-creates alerts, create-alerts never auto-resolves, and a real compliance
change happens ONLY through `resolve` with action `hold`/`ban`, which the
service applies via `set_product_compliance()`. No route writes Product or
Inventory directly.
"""

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi import status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.models import ComplianceAlertSeverity
from app.db.models import ComplianceAlertStatus
from app.db.models import ComplianceRecommendedAction
from app.db.models import RegulatoryNoticeType
from app.db.models import User
from app.db.session import get_db
from app.schemas.regulatory import ComplianceAlertActionRequest
from app.schemas.regulatory import ComplianceAlertListResponse
from app.schemas.regulatory import ComplianceAlertRead
from app.schemas.regulatory import ComplianceAlertResolveRequest
from app.schemas.regulatory import RegulatoryDecisionAuditLogListResponse
from app.schemas.regulatory import RegulatoryNoticeIngestRequest
from app.schemas.regulatory import RegulatoryNoticeListResponse
from app.schemas.regulatory import RegulatoryNoticeRead
from app.schemas.regulatory import RegulatoryProductMatchRead
from app.schemas.regulatory import RegulatorySourceCreate
from app.schemas.regulatory import RegulatorySourceListResponse
from app.schemas.regulatory import RegulatorySourceRead
from app.services import regulatory as svc


router = APIRouter(prefix="/admin/regulatory", tags=["admin-regulatory"])


# --------------------------------------------------------------------- #
# Sources
# --------------------------------------------------------------------- #


@router.get("/sources", response_model=RegulatorySourceListResponse)
def list_sources_endpoint(
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    is_active: bool | None = Query(default=None),
) -> RegulatorySourceListResponse:
    return svc.list_regulatory_sources(
        db, limit=limit, offset=offset, is_active=is_active
    )


@router.post(
    "/sources",
    response_model=RegulatorySourceRead,
    status_code=status.HTTP_201_CREATED,
)
def create_source_endpoint(
    payload: RegulatorySourceCreate,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RegulatorySourceRead:
    return svc.create_regulatory_source(db, payload)


# --------------------------------------------------------------------- #
# Notices
# --------------------------------------------------------------------- #


@router.get("/notices", response_model=RegulatoryNoticeListResponse)
def list_notices_endpoint(
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    source_id: UUID | None = Query(default=None),
    notice_type: RegulatoryNoticeType | None = Query(default=None),
) -> RegulatoryNoticeListResponse:
    return svc.list_regulatory_notices(
        db,
        limit=limit,
        offset=offset,
        source_id=source_id,
        notice_type=notice_type,
    )


@router.post(
    "/notices",
    response_model=RegulatoryNoticeRead,
    status_code=status.HTTP_201_CREATED,
)
def ingest_notice_endpoint(
    payload: RegulatoryNoticeIngestRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> RegulatoryNoticeRead:
    return svc.ingest_regulatory_notice(db, payload)


@router.post(
    "/notices/{notice_id}/detect-matches",
    response_model=list[RegulatoryProductMatchRead],
)
def detect_matches_endpoint(
    notice_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[RegulatoryProductMatchRead]:
    return svc.detect_regulatory_product_matches(db, notice_id)


@router.post(
    "/notices/{notice_id}/create-alerts",
    response_model=list[ComplianceAlertRead],
)
def create_alerts_endpoint(
    notice_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> list[ComplianceAlertRead]:
    return svc.create_compliance_alerts_from_matches(db, notice_id)


# --------------------------------------------------------------------- #
# Alerts — list / detail / lifecycle
# --------------------------------------------------------------------- #


@router.get("/alerts", response_model=ComplianceAlertListResponse)
def list_alerts_endpoint(
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    status: ComplianceAlertStatus | None = Query(default=None),
    severity: ComplianceAlertSeverity | None = Query(default=None),
    recommended_action: ComplianceRecommendedAction | None = Query(
        default=None
    ),
    product_id: UUID | None = Query(default=None),
    notice_id: UUID | None = Query(default=None),
) -> ComplianceAlertListResponse:
    return svc.list_compliance_alerts(
        db,
        limit=limit,
        offset=offset,
        status_filter=status,
        severity=severity,
        recommended_action=recommended_action,
        product_id=product_id,
        notice_id=notice_id,
    )


@router.get("/alerts/{alert_id}", response_model=ComplianceAlertRead)
def get_alert_endpoint(
    alert_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ComplianceAlertRead:
    return svc.get_compliance_alert(db, alert_id)


@router.get(
    "/alerts/{alert_id}/decisions",
    response_model=RegulatoryDecisionAuditLogListResponse,
)
def list_alert_decisions_endpoint(
    alert_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> RegulatoryDecisionAuditLogListResponse:
    return svc.list_regulatory_decisions_for_alert(
        db, alert_id, limit=limit, offset=offset
    )


@router.post(
    "/alerts/{alert_id}/acknowledge", response_model=ComplianceAlertRead
)
def acknowledge_alert_endpoint(
    alert_id: UUID,
    payload: ComplianceAlertActionRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ComplianceAlertRead:
    return svc.acknowledge_compliance_alert(
        db, alert_id, payload, actor_user_id=actor.id
    )


@router.post(
    "/alerts/{alert_id}/dismiss", response_model=ComplianceAlertRead
)
def dismiss_alert_endpoint(
    alert_id: UUID,
    payload: ComplianceAlertActionRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ComplianceAlertRead:
    return svc.dismiss_compliance_alert(
        db, alert_id, payload, actor_user_id=actor.id
    )


@router.post(
    "/alerts/{alert_id}/resolve", response_model=ComplianceAlertRead
)
def resolve_alert_endpoint(
    alert_id: UUID,
    payload: ComplianceAlertResolveRequest,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> ComplianceAlertRead:
    return svc.resolve_compliance_alert(
        db, alert_id, payload, actor_user_id=actor.id
    )
