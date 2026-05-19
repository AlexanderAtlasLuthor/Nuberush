"""Centralized auth helpers for the test suite.

Single chokepoint for how tests build credentialed users and request
headers.

F2.22.2.D cutover — the suite now authenticates with **Supabase-style
JWTs**, matching the production verifier (`app.core.supabase_auth`):

  - `auth_headers_for` mints an RS256 token whose `sub` is the user's
    `auth_user_id` (not `users.id`). `app.api.deps.get_current_user`
    verifies it and resolves `public.users` via `auth_user_id`.
  - Tokens are signed with a **test-only RSA keypair** generated in this
    module. `tests/conftest.py` monkeypatches the verifier's JWKS client
    to trust this keypair's public half, so the suite never touches the
    network and never depends on a live Supabase project.
  - `make_user` now assigns an `auth_user_id` automatically (a random
    UUID) so every credentialed test user is reachable by the new
    identity bridge. Pass `auth_user_id=None` explicitly to create an
    unmapped row (used only by the `auth_user_id` column schema tests).

The token still carries identity only. role / store_id / is_active come
from `public.users`; nothing here puts authorization data in a claim.

F2.22.2.F — the legacy `password_hash` column and `make_password_hash`
helper are gone. `public.users` carries no credentials; authentication
is exclusively via Supabase JWT, so test users only need an
`auth_user_id`.
"""

from __future__ import annotations

import datetime as dt
import uuid

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.models import UserRole


# --------------------------------------------------------------------- #
# Test-only Supabase JWT signing
# --------------------------------------------------------------------- #

# Supabase access tokens are signed with asymmetric keys (ES256/RS256)
# published on the project JWKS endpoint. The suite mints equivalent
# RS256 tokens with this throwaway keypair, generated once per session.
# It is NEVER used outside tests — production verifies real Supabase JWKS.
TEST_JWT_ALGORITHM = "RS256"
TEST_JWT_KID = "nuberush-test-key"
TEST_JWT_AUDIENCE = "authenticated"

_test_private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def get_test_public_key():
    """Public half of the test signing key.

    `tests/conftest.py` feeds this to a fake JWKS client so the production
    verifier (`app.core.supabase_auth.verify_supabase_jwt`) trusts tokens
    minted by `make_supabase_token` / `auth_headers_for`.
    """
    return _test_private_key.public_key()


def make_supabase_token(
    *,
    sub: uuid.UUID | str | None,
    audience: str = TEST_JWT_AUDIENCE,
    expires_in_seconds: int = 3600,
    issued_at: dt.datetime | None = None,
    issuer: str | None = None,
    signing_key=None,
    algorithm: str = TEST_JWT_ALGORITHM,
    kid: str | None = TEST_JWT_KID,
    include_sub: bool = True,
    extra_claims: dict | None = None,
) -> str:
    """Mint a Supabase-style access token for tests.

    Defaults produce a valid token the verifier accepts. Override the
    keyword args to craft rejection cases: `signing_key=<other key>`
    (bad signature), `audience="..."` (wrong audience), a past
    `issued_at` with a short `expires_in_seconds` (expired),
    `include_sub=False` (missing subject), `extra_claims={...}` (bogus
    role/app_metadata claims the verifier must ignore).
    """
    now = issued_at or dt.datetime.now(dt.UTC)
    claims: dict = {
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + dt.timedelta(seconds=expires_in_seconds)).timestamp()),
        # Supabase tokens carry a Postgres `role` claim ("authenticated").
        # Included for realism only — the verifier never reads it.
        "role": "authenticated",
    }
    if include_sub and sub is not None:
        claims["sub"] = str(sub)
    if issuer is not None:
        claims["iss"] = issuer
    if extra_claims:
        claims.update(extra_claims)

    headers = {"kid": kid} if kid is not None else {}
    return jwt.encode(
        claims,
        signing_key or _test_private_key,
        algorithm=algorithm,
        headers=headers,
    )


def auth_headers_for(user: User) -> dict[str, str]:
    """Return the ``Authorization`` header for a request as ``user``.

    Mints a Supabase-style JWT whose ``sub`` is ``user.auth_user_id`` —
    the identity key `get_current_user` resolves against
    ``public.users.auth_user_id``.

    Raises if the user has no ``auth_user_id``: such a row cannot
    authenticate under the F2.22.2.D bridge. Build credentialed users
    with :func:`make_user`, which assigns one automatically.
    """
    if user.auth_user_id is None:
        raise ValueError(
            "auth_headers_for(user) requires user.auth_user_id to be set. "
            "Build the user via tests.helpers.auth.make_user (it assigns "
            "an auth_user_id), or set one explicitly before authenticating."
        )
    token = make_supabase_token(sub=user.auth_user_id)
    return {"Authorization": f"Bearer {token}"}


# Sentinel: `make_user(auth_user_id=...)` left at the default auto-assigns
# a random UUID; passing `auth_user_id=None` explicitly creates an
# unmapped row (only the auth_user_id column schema tests need that).
_AUTO_AUTH_USER_ID = object()


def make_user(
    db: Session,
    *,
    role: UserRole,
    store_id: uuid.UUID | None = None,
    email: str | None = None,
    full_name: str | None = None,
    phone: str | None = None,
    is_active: bool = True,
    auth_user_id=_AUTO_AUTH_USER_ID,
    id: uuid.UUID | None = None,
) -> User:
    """Persist and return a ``User`` row for tests.

    F2.22.2.F — ``public.users`` no longer stores credentials, so no
    password is needed to build a test user.

    ``auth_user_id`` defaults to a freshly generated UUID so the user is
    reachable by the Supabase identity bridge and by
    :func:`auth_headers_for`. Pass ``auth_user_id=None`` to create an
    unmapped row, or a specific UUID to pin the mapping.

    Commits and refreshes so the returned row has its server-side
    defaults (``id``, timestamps) populated.
    """
    resolved_auth_user_id = (
        uuid.uuid4()
        if auth_user_id is _AUTO_AUTH_USER_ID
        else auth_user_id
    )
    user = User(
        full_name=full_name or f"Test {role.value}",
        email=email or f"{role.value}-{uuid.uuid4().hex[:10]}@example.com",
        phone=phone,
        role=role,
        store_id=store_id,
        is_active=is_active,
        auth_user_id=resolved_auth_user_id,
    )
    if id is not None:
        user.id = id
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def make_supabase_mapped_user(
    db: Session,
    *,
    role: UserRole,
    store_id: uuid.UUID | None = None,
    email: str | None = None,
    is_active: bool = True,
    auth_user_id: uuid.UUID | None = None,
) -> User:
    """Like :func:`make_user`, with an explicit guarantee of a mapping.

    Generates a random ``auth_user_id`` when none is given. Kept as a
    distinct, intention-revealing entry point for tests that specifically
    exercise the Supabase identity bridge; since F2.22.2.D, plain
    :func:`make_user` also assigns an ``auth_user_id`` by default.
    """
    return make_user(
        db,
        role=role,
        store_id=store_id,
        email=email,
        is_active=is_active,
        auth_user_id=auth_user_id or uuid.uuid4(),
    )
