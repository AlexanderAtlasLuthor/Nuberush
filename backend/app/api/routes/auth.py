import logging
import uuid

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.deps import require_manager_or_above
from app.core.permissions import can_caller_create_role
from app.core.permissions import ensure_admin_email_allowed
from app.core.permissions import resolve_target_store_id
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.db.session import get_db
from app.schemas.auth import CreateUserRequest
from app.schemas.auth import UserRead
from app.services import supabase_admin
from app.services.supabase_admin import SupabaseAdminError


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _rollback_supabase_auth_user(auth_user_id: uuid.UUID) -> None:
    """Best-effort delete of a Supabase auth user after a failed DB insert.

    Prevents an `auth.users` row orphaned without a `public.users` mapping.
    If the cleanup itself fails, we log a warning (no secrets) and let the
    caller surface the original error — a stuck orphan is preferable to
    masking the failure, and is recoverable by an operator.
    """
    try:
        supabase_admin.delete_auth_user(auth_user_id)
    except SupabaseAdminError:
        logger.warning(
            "Failed to roll back Supabase auth user %s after a public.users "
            "insert error; manual cleanup of the orphaned auth.users row "
            "may be required.",
            auth_user_id,
        )


@router.post(
    "/register",
    deprecated=True,
    summary="Public registration is disabled",
)
def register_user() -> None:
    # Public self-register would let anyone pick role and store_id, which is a
    # privilege-escalation vector for a B2B tenant system. Authenticated
    # administrators must create users via POST /auth/users instead.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail=(
            "Public registration is disabled. "
            "Authenticated administrators create users via POST /auth/users."
        ),
    )


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
)
def create_user(
    payload: CreateUserRequest,
    # require_manager_or_above is the coarse gate: it rejects staff and
    # driver before we touch the body. can_caller_create_role still runs
    # below to enforce the fine-grained matrix (admin->admin denied, owner
    # can't create owner, etc.). Both layers are intentional.
    current_user: User = Depends(require_manager_or_above),
    db: Session = Depends(get_db),
) -> User:
    if not can_caller_create_role(current_user.role, payload.role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"You cannot create users with role '{payload.role.value}'.",
        )

    target_store_id = resolve_target_store_id(
        caller=current_user,
        target_role=payload.role,
        requested_store_id=payload.store_id,
    )

    if target_store_id is not None:
        store = db.scalar(select(Store).where(Store.id == target_store_id))
        if store is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Store not found.",
            )

    normalized_email = str(payload.email).lower()
    # F2.24.C5: an admin may only be created with an official @nuberush.com
    # address. Admin creation is ALSO blocked by USER_CREATION_MATRIX above
    # (can_caller_create_role denies it for every caller today), so this is
    # the defense-in-depth layer — gated behind the same role, it activates
    # automatically and stays correct if that matrix is ever widened.
    if payload.role == UserRole.admin:
        ensure_admin_email_allowed(normalized_email)
    if db.scalar(select(User).where(User.email == normalized_email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered.",
        )

    # F2.22.2.E: identity lives in Supabase Auth, authorization in
    # public.users. Create the auth.users record FIRST so the
    # public.users row can carry its auth_user_id. user_metadata is
    # informational only — role/store/is_active authority stays in
    # public.users and is never read back from a Supabase claim.
    metadata = {
        "full_name": payload.full_name,
        "nuberush_role": payload.role.value,
        "nuberush_store_id": (
            str(target_store_id) if target_store_id is not None else None
        ),
    }
    try:
        auth_user_id = supabase_admin.create_auth_user(
            email=normalized_email,
            password=payload.password,
            user_metadata=metadata,
        )
    except SupabaseAdminError as exc:
        # Identity provider failed → nothing was written here. Surface a
        # controlled 502 without leaking provider internals or secrets.
        logger.warning("Supabase auth user creation failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create the user with the identity provider.",
        ) from exc

    # F2.22.2.F: there is no local password storage anymore. The password
    # the caller supplied was consumed above to create the Supabase
    # auth.users record; authentication is exclusively via Supabase JWT.
    # public.users carries only authorization data plus the auth_user_id
    # bridge.
    new_user = User(
        full_name=payload.full_name,
        email=normalized_email,
        phone=payload.phone,
        role=payload.role,
        store_id=target_store_id,
        is_active=True,
        auth_user_id=auth_user_id,
    )
    db.add(new_user)
    try:
        db.commit()
    except Exception as exc:
        # public.users insert failed after the auth.users row was created
        # (e.g. a unique-constraint race on email or auth_user_id). Roll
        # back the DB and the Supabase side so neither table is orphaned.
        db.rollback()
        _rollback_supabase_auth_user(auth_user_id)
        logger.warning("public.users insert failed after auth create: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist the new user.",
        ) from exc

    db.refresh(new_user)
    return new_user
