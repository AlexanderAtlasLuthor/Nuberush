"""Public (unauthenticated) HTTP surface (F2.24.C2).

The only endpoint here is the merchant store-application intake:

  POST /public/store-applications   create a pending-review application

This router is deliberately UNAUTHENTICATED — no `require_admin`, no store
context, no owner session, no Supabase Auth dependency. It creates inert
application data only; it never provisions a store, a user, an auth record,
or any access. Thin-client boundary is preserved: the frontend submits
through this FastAPI endpoint, never through supabase-js.

Why a dedicated `/public` prefix: it makes the unauthenticated surface
explicit and auditable in one place, separate from every other router
which gates on an auth dependency.
"""

from fastapi import APIRouter
from fastapi import Depends
from fastapi import status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.store_applications import StoreApplicationSubmitRequest
from app.schemas.store_applications import StoreApplicationSubmitResponse
from app.services import store_applications as svc


router = APIRouter(prefix="/public", tags=["public"])


@router.post(
    "/store-applications",
    response_model=StoreApplicationSubmitResponse,
    status_code=status.HTTP_201_CREATED,
)
def submit_store_application_endpoint(
    payload: StoreApplicationSubmitRequest,
    db: Session = Depends(get_db),
) -> StoreApplicationSubmitResponse:
    application = svc.create_store_application(db, payload=payload)
    return StoreApplicationSubmitResponse(
        id=application.id,
        status=application.status,
        message="Application submitted for review.",
    )
