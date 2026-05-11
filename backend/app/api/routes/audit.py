"""HTTP layer for the unified audit feed (F2.16.3 + F2.17.5).

Thin routes: parse path/query, authorize via existing dependencies,
delegate to `app.services.audit.list_store_audit` or
`app.services.audit.list_admin_audit`, return the service response
unchanged.

Aggregation, normalization, filter dispatch, stable sort and
post-merge pagination all live in the service layer; this module
exists only to wire services to FastAPI.

Access tiers:

  GET /stores/{store_id}/audit  (F2.16.3, store-scoped)
      admin / owner / manager / staff   →  allowed
      driver / anon                      →  denied
      (require_store_member tenancy + require_staff_or_above role)

  GET /admin/audit  (F2.17.5, global / admin-only)
      admin                              →  allowed
      owner / manager / staff / driver   →  denied
      anon                               →  denied
      (require_admin)

The two paths share the same `AuditEventListResponse` envelope and
identical query-param shapes (with the admin endpoint adding an
optional `store_id` filter). The store-scoped route never reaches
the global feed; the global route never reaches the store-tenant
matrix. They coexist on the same router without collision because
the path segments are distinct.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.api.deps import require_staff_or_above
from app.api.deps import require_store_member
from app.db.models import User
from app.db.session import get_db
from app.schemas.audit import AuditEntityType
from app.schemas.audit import AuditEventListResponse
from app.schemas.audit import AuditSource
from app.services import audit as svc


router = APIRouter(tags=["audit"])


@router.get(
    "/stores/{store_id}/audit",
    response_model=AuditEventListResponse,
    dependencies=[Depends(require_store_member)],
)
def list_store_audit_endpoint(
    store_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    source: AuditSource | None = Query(default=None),
    entity_type: AuditEntityType | None = Query(default=None),
    action: str | None = Query(default=None, max_length=100),
    actor_id: UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    current_user: User = Depends(require_staff_or_above),
    db: Session = Depends(get_db),
) -> AuditEventListResponse:
    return svc.list_store_audit(
        db,
        store_id=store_id,
        actor=current_user,
        limit=limit,
        offset=offset,
        source=source,
        entity_type=entity_type,
        action=action,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get(
    "/admin/audit",
    response_model=AuditEventListResponse,
)
def list_admin_audit_endpoint(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    store_id: UUID | None = Query(default=None),
    source: AuditSource | None = Query(default=None),
    entity_type: AuditEntityType | None = Query(default=None),
    action: str | None = Query(default=None, max_length=100),
    actor_id: UUID | None = Query(default=None),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AuditEventListResponse:
    return svc.list_admin_audit(
        db,
        actor=actor,
        store_id=store_id,
        limit=limit,
        offset=offset,
        source=source,
        entity_type=entity_type,
        action=action,
        actor_id=actor_id,
        date_from=date_from,
        date_to=date_to,
    )
