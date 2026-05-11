"""HTTP layer for the unified store audit feed (F2.16.3).

Thin route: parse path/query, authorize via existing dependencies,
delegate to `app.services.audit.list_store_audit`, return the
service's response unchanged.

Aggregation, normalization, filter dispatch, stable sort and
post-merge pagination all live in the service layer; this module
exists only to wire the service to FastAPI.

Access tiers (F2.16 contract):

  GET /stores/{store_id}/audit:
      admin / owner / manager / staff   →  allowed
      driver / anon                      →  denied

`require_store_member` on the path enforces tenancy (admin global,
non-admin own-store, anti-probe collapse for cross/unknown store).
`require_staff_or_above` on the caller enforces the role gate —
driver is operational-only and never sees this surface.

Both gates produce the same matrix the service's
`_assert_audit_access` would produce when invoked directly, so a
future internal caller (admin script, batch job) sees the same
contract as HTTP clients.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from sqlalchemy.orm import Session

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
