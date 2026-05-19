"""HTTP layer for users management (F2.15.3).

Thin: parse query/body/path, inject db + current user, delegate to
`app.services.users`, return what the service hands back. Every RBAC,
tenancy, matrix and invariant decision lives in the service +
`app.core.permissions` — this router does not duplicate any of it.

Endpoints (all under prefix `/auth/users`):

  GET    /                      list users (paginated, scope-aware)
  GET    /{user_id}             read a single user
  PATCH  /{user_id}             update full_name / phone
  POST   /{user_id}/deactivate  set is_active=false
  POST   /{user_id}/reactivate  set is_active=true
  PATCH  /{user_id}/role        change role
  PATCH  /{user_id}/store       assign or clear store

Password changes are owned by Supabase Auth (F2.22.2.F); there is no
local password endpoint here.

Note on the `POST /auth/users` endpoint: that route lives in
`app.api.routes.auth` (user creation) and is intentionally NOT moved
here in F2.15.3. The new router does not declare a `POST /` so there
is no path conflict.
"""

from uuid import UUID

from fastapi import APIRouter
from fastapi import Depends
from fastapi import Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.models import User
from app.db.models import UserRole
from app.db.session import get_db
from app.schemas.auth import UserRead
from app.schemas.users import UserListResponse
from app.schemas.users import UserRoleChangeRequest
from app.schemas.users import UserStoreAssignmentRequest
from app.schemas.users import UserUpdateRequest
from app.services import users as svc


router = APIRouter(prefix="/auth/users", tags=["users"])


@router.get("", response_model=UserListResponse)
def list_users_endpoint(
    limit: int = Query(default=25, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    role: UserRole | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    store_id: UUID | None = Query(default=None),
    q: str | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    return svc.list_users(
        db,
        actor=current_user,
        role=role,
        is_active=is_active,
        store_id=store_id,
        q=q,
        limit=limit,
        offset=offset,
    )


@router.get("/{user_id}", response_model=UserRead)
def get_user_endpoint(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return svc.get_user(db, user_id, actor=current_user)


@router.patch("/{user_id}", response_model=UserRead)
def update_user_endpoint(
    user_id: UUID,
    payload: UserUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return svc.update_user(db, user_id, payload, actor=current_user)


@router.post("/{user_id}/deactivate", response_model=UserRead)
def deactivate_user_endpoint(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return svc.deactivate_user(db, user_id, actor=current_user)


@router.post("/{user_id}/reactivate", response_model=UserRead)
def reactivate_user_endpoint(
    user_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return svc.reactivate_user(db, user_id, actor=current_user)


@router.patch("/{user_id}/role", response_model=UserRead)
def change_user_role_endpoint(
    user_id: UUID,
    payload: UserRoleChangeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return svc.change_user_role(
        db, user_id, payload, actor=current_user
    )


@router.patch("/{user_id}/store", response_model=UserRead)
def assign_user_store_endpoint(
    user_id: UUID,
    payload: UserStoreAssignmentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    return svc.assign_user_store(
        db, user_id, payload, actor=current_user
    )
