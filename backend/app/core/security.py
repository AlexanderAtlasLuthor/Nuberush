from datetime import UTC
from datetime import datetime
from datetime import timedelta
from uuid import UUID

import jwt
from passlib.context import CryptContext

from app.core.config import get_auth_settings


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# Computed lazily so importing this module never blocks on bcrypt.
_DUMMY_HASH: str | None = None


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_dummy_password_hash() -> str:
    """Return a stable bcrypt hash usable for constant-time login responses.

    Login flows verify against this hash when the email is unknown so the
    timing of "user not found" matches "user found, wrong password" and we
    don't leak the existence of accounts.
    """
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password("__nuberush_timing_safety_placeholder__")
    return _DUMMY_HASH


def create_access_token(subject: str | UUID) -> str:
    settings = get_auth_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    return jwt.encode(
        payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )
