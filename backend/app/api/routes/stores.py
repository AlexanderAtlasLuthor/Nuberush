"""HTTP layer for the stores module (F2.14.3 + F2.17.3).

Thin: parse, authorize, call service, return. The schemas
(`app.schemas.stores`) define the wire contract and the service
(`app.services.stores`) owns the read/update/list/create/lifecycle
behaviour.

F2.14.3 endpoints (unchanged):

  GET   /stores/{store_id}        store-member tenancy
  PATCH /stores/{store_id}        store-member tenancy + owner/admin role

F2.17.3 endpoints (admin-only, /stores namespace):

  GET   /stores                       admin list with filters + pagination
  POST  /stores                       admin create (201)
  POST  /stores/{store_id}/deactivate admin lifecycle (NOT idempotent)
  POST  /stores/{store_id}/reactivate admin lifecycle (NOT idempotent)

Why `/stores` and not `/admin/stores`:

  F2.15 set the precedent by extending `/auth/users` instead of
  introducing `/admin/users`. Keeping admin store CRUD under the same
  prefix means tenancy-aware reads (`require_store_member`) and
  admin-only writes (`require_admin`) coexist in one router with no
  duplicate code paths. The route layer guards on a per-endpoint basis.

Lifecycle endpoints deliberately use `require_admin` (NOT
`require_store_member`). The latter rejects inactive stores with 400,
which would make reactivation impossible. Tenancy isn't relevant for
admin-only lifecycle operations.

Anti-probe behaviour for non-admins on GET /stores/{store_id} and
PATCH /stores/{store_id} is unchanged: `require_store_member`
collapses "wrong store" and "no such store" into 403 so existence
cannot be probed via status code.
"""

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from fastapi import status
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.api.deps import require_owner_or_admin
from app.api.deps import require_store_member
from app.db.models import Store
from app.db.models import User
from app.db.session import get_db
from app.schemas.stores import StoreCreate
from app.schemas.stores import StoreListResponse
from app.schemas.stores import StoreRead
from app.schemas.stores import StoreUpdate
from app.services import stores as svc


router = APIRouter(prefix="/stores", tags=["stores"])


# --------------------------------------------------------------------- #
# Collection-level endpoints (F2.17.3)
# --------------------------------------------------------------------- #
#
# Declared before `/{store_id}` for readability; FastAPI's path matching
# is unambiguous either way (empty vs path-param routes are distinct).


@router.get(
    "",
    response_model=StoreListResponse,
)
def list_stores_endpoint(
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    is_active: bool | None = Query(None),
    q: str | None = Query(None),
) -> StoreListResponse:
    return svc.list_stores(
        db,
        actor=actor,
        limit=limit,
        offset=offset,
        is_active=is_active,
        q=q,
    )


@router.post(
    "",
    response_model=StoreRead,
    status_code=status.HTTP_201_CREATED,
)
def create_store_endpoint(
    payload: StoreCreate,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StoreRead:
    return svc.create_store(db, actor=actor, payload=payload)


# --------------------------------------------------------------------- #
# Item-level endpoints (F2.14.3, unchanged)
# --------------------------------------------------------------------- #


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
    return svc.update_store(db, store_id, payload, actor=current_user)


# --------------------------------------------------------------------- #
# Lifecycle endpoints (F2.17.3)
# --------------------------------------------------------------------- #
#
# Admin-only. Tenancy guard intentionally NOT applied — admin can target
# any store (active or inactive). Service enforces NOT-idempotent semantics:
# deactivating an already-inactive store → 422; reactivating an already-
# active store → 422.


@router.post(
    "/{store_id}/deactivate",
    response_model=StoreRead,
)
def deactivate_store_endpoint(
    store_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StoreRead:
    return svc.deactivate_store(db, actor=actor, store_id=store_id)


@router.post(
    "/{store_id}/reactivate",
    response_model=StoreRead,
)
def reactivate_store_endpoint(
    store_id: UUID,
    actor: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> StoreRead:
    return svc.reactivate_store(db, actor=actor, store_id=store_id)
