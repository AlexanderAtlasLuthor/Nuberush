import jwt
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.security import HTTPBearer
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_auth_settings
from app.db.models import User
from app.db.models import UserRole
from app.db.session import get_db
from app.schemas.auth import TokenPayload


# auto_error=False so we control the response code/headers ourselves;
# FastAPI's default is 403, we want 401 with a WWW-Authenticate header.
bearer_scheme = HTTPBearer(auto_error=False)

WWW_AUTH_HEADER = {"WWW-Authenticate": "Bearer"}


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers=WWW_AUTH_HEADER,
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise _unauthorized("Not authenticated")
    if credentials.scheme.lower() != "bearer":
        raise _unauthorized("Not authenticated")

    settings = get_auth_settings()
    try:
        raw_payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise _unauthorized("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        # Covers MissingRequiredClaimError, InvalidIssuerError,
        # InvalidAudienceError, DecodeError, InvalidSignatureError, etc.
        raise _unauthorized("Invalid token") from exc

    try:
        token_payload = TokenPayload.model_validate(raw_payload)
    except ValidationError as exc:
        raise _unauthorized("Invalid token") from exc

    user = db.scalar(select(User).where(User.id == token_payload.sub))
    if user is None:
        raise _unauthorized("Invalid token")

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )

    return user


def require_roles(*allowed_roles: UserRole):
    def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource",
            )
        return current_user

    return role_dependency
