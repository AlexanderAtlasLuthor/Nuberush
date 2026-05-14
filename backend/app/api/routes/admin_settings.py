"""HTTP layer for the admin settings snapshot.

Thin route: authorize via `require_admin`, delegate to
`app.services.admin_settings.get_admin_settings_snapshot`, return the
service response unchanged.

Single endpoint:

  GET /admin/settings

    admin                              →  200
    owner / manager / staff / driver   →  403
    anon                               →  401

No path params, no query params, no mutations. Response is a single
`AdminSettingsResponse` envelope; every section is computed by the
service on each call from existing tables and locked constants.
"""

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.db.models import User
from app.db.session import get_db
from app.schemas.admin_settings import AdminSettingsResponse
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
