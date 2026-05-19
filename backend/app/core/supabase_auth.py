"""Supabase Auth access-token verification (F2.22.2.D).

FastAPI verifies Supabase-issued access tokens here. Two hard rules:

1. The JWT establishes IDENTITY ONLY. The single value trusted out of a
   verified token is `sub` (= `auth.users.id`). Role, `store_id`,
   `is_active` and every permission decision come from `public.users`
   downstream — never from token claims, `app_metadata` or `user_metadata`.
   `SupabaseTokenPayload` therefore exposes nothing but `sub`, so no
   caller can accidentally trust a claim.

2. Signatures are verified against the project's JWKS endpoint
   (asymmetric ES256/RS256 keys). There is intentionally no HS256 /
   shared-secret fallback: a JWKS flow must not silently degrade to a
   symmetric secret.

`get_current_user` (app.api.deps) catches `SupabaseAuthError` and maps
it to HTTP 401. The error message is deliberately coarse so a caller
cannot tell which check failed.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

import jwt
from jwt import PyJWKClient

from app.core.config import get_supabase_auth_settings


# Supabase signs access tokens with asymmetric keys published on the
# JWKS endpoint. HS256 is intentionally excluded.
_ALLOWED_ALGORITHMS = ("ES256", "RS256")

# Claims a verified token must carry. `iss` is required only when an
# issuer is configured (added dynamically in `verify_supabase_jwt`).
_REQUIRED_CLAIMS = ("sub", "exp", "iat", "aud")


class SupabaseAuthError(Exception):
    """Raised when a Supabase access token cannot be verified.

    Covers every failure mode — bad signature, wrong audience, expired,
    malformed, missing/!UUID `sub`, JWKS resolution failure. `deps.py`
    converts it to a uniform HTTP 401.
    """


@dataclass(frozen=True)
class SupabaseTokenPayload:
    """The verified, trusted subset of a Supabase access token.

    Only `sub` is carried forward — it is the identity key used to
    locate the `public.users` row via `auth_user_id`. No role/store/
    permission claim is surfaced, by design (see module docstring).
    """

    sub: uuid.UUID


# Process-wide JWKS client. PyJWKClient fetches the JWKS document lazily
# on first use and caches the keys in-process, so steady-state token
# verification performs no network I/O. Kept module-level (not lru_cache)
# so tests can swap it via `_get_jwk_client` monkeypatching.
_jwk_client: PyJWKClient | None = None


def _get_jwk_client() -> PyJWKClient:
    """Return the process-cached `PyJWKClient` for the configured JWKS URL.

    Tests monkeypatch this function to return a client backed by a
    test-only keypair, so the suite never touches the network.
    """
    global _jwk_client
    if _jwk_client is None:
        settings = get_supabase_auth_settings()
        if not settings.supabase_jwks_url:
            raise SupabaseAuthError("Supabase JWKS URL is not configured")
        _jwk_client = PyJWKClient(settings.supabase_jwks_url)
    return _jwk_client


def reset_jwk_client_cache() -> None:
    """Drop the cached `PyJWKClient`. Used by tests between configurations."""
    global _jwk_client
    _jwk_client = None


def verify_supabase_jwt(token: str) -> SupabaseTokenPayload:
    """Verify a Supabase access token and return its trusted identity.

    Raises `SupabaseAuthError` on any failure: unresolved signing key,
    bad signature, wrong audience, wrong issuer (when configured),
    expired/not-yet-valid, missing required claim, or a `sub` that is
    not a UUID.
    """
    settings = get_supabase_auth_settings()

    decode_options: dict = {"require": list(_REQUIRED_CLAIMS)}
    decode_kwargs: dict = {
        "algorithms": list(_ALLOWED_ALGORITHMS),
        "audience": settings.supabase_jwt_audience,
    }
    # Issuer is validated only when configured (derived from SUPABASE_URL).
    if settings.supabase_jwt_issuer:
        decode_kwargs["issuer"] = settings.supabase_jwt_issuer
        decode_options["require"] = list(_REQUIRED_CLAIMS) + ["iss"]
    decode_kwargs["options"] = decode_options

    try:
        signing_key = _get_jwk_client().get_signing_key_from_jwt(token)
        claims = jwt.decode(token, signing_key.key, **decode_kwargs)
    except SupabaseAuthError:
        raise
    except jwt.PyJWTError as exc:
        # Covers DecodeError, InvalidSignatureError, ExpiredSignatureError,
        # InvalidAudienceError, InvalidIssuerError, MissingRequiredClaimError,
        # and PyJWKClient errors (PyJWKClientError is a PyJWTError subclass).
        raise SupabaseAuthError("Invalid token") from exc

    raw_sub = claims.get("sub")
    try:
        sub = uuid.UUID(str(raw_sub))
    except (ValueError, TypeError, AttributeError) as exc:
        raise SupabaseAuthError("Token subject is not a valid UUID") from exc

    return SupabaseTokenPayload(sub=sub)
