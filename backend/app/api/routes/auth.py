from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.permissions import can_caller_create_role
from app.core.permissions import resolve_target_store_id
from app.core.security import create_access_token
from app.core.security import hash_password
from app.core.security import verify_password
from app.db.models import Store
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import CreateUserRequest
from app.schemas.auth import LoginRequest
from app.schemas.auth import TokenResponse
from app.schemas.auth import UserRead


router = APIRouter(prefix="/auth", tags=["auth"])


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


@router.post("/login", response_model=TokenResponse)
def login_user(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == str(payload.email).lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    token = create_access_token(str(user.id))
    return TokenResponse(access_token=token)


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
    current_user: User = Depends(get_current_user),
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
    if db.scalar(select(User).where(User.email == normalized_email)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered.",
        )

    new_user = User(
        full_name=payload.full_name,
        email=normalized_email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        role=payload.role,
        store_id=target_store_id,
        is_active=True,
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return new_user
