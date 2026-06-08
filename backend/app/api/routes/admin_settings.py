"""HTTP layer for the admin settings surface.

Thin routes: authorize via `require_admin`, delegate to
`app.services.admin_settings`, return the service response unchanged.

Endpoints:

  GET /admin/settings    — read the full settings snapshot.
  PATCH /admin/settings  — update the writable platform-settings cluster
                           (F2.27.10).

    admin                              →  200
    owner / manager / staff / driver   →  403
    anon                               →  401
    invalid / unknown fields           →  422

The GET takes no params and is computed-on-request. The PATCH accepts a
partial `AdminSettingsUpdate` body restricted to the four editable fields
(`extra="forbid"` rejects anything else with a 422); the service persists the
change and writes a dedicated audit row. Both return the same
`AdminSettingsResponse` envelope.
"""

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.models import User
from app.db.session import get_db
from app.schemas.admin_settings import AdminSettingsResponse
from app.schemas.admin_settings import AdminSettingsUpdate
from app.services import admin_settings as svc


router = APIRouter(tags=["admin-settings"])


@router.get(
    "/admin/settings",
    response_model=AdminSettingsResponse,
)
def get_admin_settings_endpoint(
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminSettingsResponse:
    return svc.get_admin_settings_snapshot(db, actor=actor)


@router.patch(
    "/admin/settings",
    response_model=AdminSettingsResponse,
)
def update_admin_settings_endpoint(
    payload: AdminSettingsUpdate,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> AdminSettingsResponse:
    return svc.update_admin_settings(db, payload, actor=actor)
