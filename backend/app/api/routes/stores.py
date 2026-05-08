"""HTTP layer for the stores module (F2.14.3).

Thin: parse, authorize, call service, return. The schemas
(`app.schemas.stores`) define the wire contract and the service
(`app.services.stores`) owns the read/update behaviour. This router
only enforces:

  - authentication (Bearer) — inherited via `require_store_member`
  - tenancy on the path `store_id` via `require_store_member`
  - role gating on writes via `require_owner_or_admin`

Mapping of access tiers (F2.14 contract):

  Read (GET /stores/{store_id}):
      admin               →  any active store (404 unknown, 400 inactive)
      owner / manager / staff / driver
                          →  only their own active store (403 cross-store,
                             400 inactive)
      anon                →  401

  Write (PATCH /stores/{store_id}):
      admin / owner       →  same access window as read
      manager / staff / driver
                          →  403 (role gate fails after tenancy passes
                             on their own store)
      anon                →  401

`require_store_member` is the source of truth for "wrong store" vs
"no such store" — a non-admin caller gets 403 in both cases,
deliberately collapsed so an attacker cannot probe existence.
"""

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from sqlalchemy.orm import Session

from app.api.deps import require_owner_or_admin
from app.api.deps import require_store_member
from app.db.models import Store
from app.db.session import get_db
from app.schemas.stores import StoreRead
from app.schemas.stores import StoreUpdate
from app.services import stores as svc


router = APIRouter(prefix="/stores", tags=["stores"])


@router.get(
    "/{store_id}",
    response_model=StoreRead,
    dependencies=[Depends(require_store_member)],
)
def get_store_endpoint(
    store_id: UUID,
    db: Session = Depends(get_db),
) -> Store:
    return svc.get_store(db, store_id)


@router.patch(
    "/{store_id}",
    response_model=StoreRead,
    dependencies=[Depends(require_store_member)],
)
def update_store_endpoint(
    store_id: UUID,
    payload: StoreUpdate,
    # `require_owner_or_admin` runs after `require_store_member` finishes,
    # so a non-owner with valid tenancy still gets 403 here. A non-admin
    # touching a store that isn't theirs will already have been rejected
    # by the tenancy gate above.
    current_user=Depends(require_owner_or_admin),
    db: Session = Depends(get_db),
) -> Store:
    return svc.update_store(db, store_id, payload)
