"""Auth endpoint tests: GET /auth/me.

`/auth/me` (via `get_current_user`) authenticates with **Supabase-issued
JWTs**, verified against the project JWKS. The token establishes
identity only; its `sub` is matched against `public.users.auth_user_id`.
Role / store_id / is_active come from the `public.users` row, never from
token claims.

F2.22.2.F — the legacy `POST /auth/login` endpoint and the self-hosted
JWT it minted have been removed. Authentication is exclusively via
Supabase access tokens.

Test JWT strategy: tokens are signed with a test-only RSA keypair
(`tests.helpers.auth`); `conftest._supabase_jwt_verifier` points the
verifier's JWKS client at its public half. Verification is fully real
(signature / audience / expiry / required claims) but offline.
"""

import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Callable

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for
from tests.helpers.auth import make_supabase_token
from tests.helpers.auth import make_user as central_make_user


# A second keypair, unrelated to the suite's signing key, used only to
# produce a token with a signature the verifier must reject.
_WRONG_SIGNING_KEY = rsa.generate_private_key(
    public_exponent=65537, key_size=2048
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "Login Store", code: str | None = None) -> Store:
        store = Store(name=name, code=code or f"login-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_user(db_session: Session) -> Callable[..., tuple[User, str]]:
    """Returns (user, _) keeping this suite's historical tuple shape.

    Thin adapter over tests.helpers.auth.make_user. The central helper
    assigns an `auth_user_id`, so the user is reachable by the Supabase
    identity bridge. The second tuple element is vestigial (there are no
    local passwords since F2.22.2.F) and is conventionally bound to `_`.
    """

    def _create(
        role: UserRole,
        store_id: uuid.UUID | None = None,
        email: str | None = None,
        is_active: bool = True,
    ) -> tuple[User, str]:
        user = central_make_user(
            db_session,
            role=role,
            store_id=store_id,
            email=email,
            is_active=is_active,
        )
        return user, ""

    return _create


# ---------------------------------------------------------------------------
# GET /auth/me  —  Supabase JWT verification
# ---------------------------------------------------------------------------


class TestMeValidToken:
    def test_valid_supabase_token_returns_user(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, _ = make_user(UserRole.owner, store_id=store.id)
        # Token `sub` == user.auth_user_id is the identity bridge.
        token = make_supabase_token(sub=user.auth_user_id)
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(user.id)
        assert body["email"] == user.email
        assert body["role"] == UserRole.owner.value
        assert body["store_id"] == str(store.id)

    def test_auth_headers_for_helper_is_accepted(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, _ = make_user(UserRole.staff, store_id=store.id)
        resp = client.get("/auth/me", headers=auth_headers_for(user))
        assert resp.status_code == 200
        assert resp.json()["id"] == str(user.id)

    def test_response_does_not_leak_password_hash(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, _ = make_user(UserRole.staff, store_id=store.id)
        token = make_supabase_token(sub=user.auth_user_id)
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        body = resp.json()
        assert "password_hash" not in body
        assert "password" not in body
        assert "auth_user_id" not in body
        assert set(body.keys()) == {
            "id",
            "full_name",
            "email",
            "role",
            "store_id",
            "is_active",
        }


class TestMeAuthHeaderRules:
    def test_no_authorization_header_returns_401(self, client: TestClient):
        resp = client.get("/auth/me")
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Not authenticated"
        assert resp.headers.get("www-authenticate", "").lower() == "bearer"

    def test_non_bearer_scheme_returns_401(self, client: TestClient):
        resp = client.get(
            "/auth/me", headers={"Authorization": "Basic dXNlcjpwYXNz"}
        )
        assert resp.status_code == 401

    def test_garbage_token_returns_401_invalid(self, client: TestClient):
        resp = client.get(
            "/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"


class TestMeTokenVerification:
    """Signature / audience / expiry / claim checks on the Supabase JWT."""

    def test_invalid_signature_is_rejected(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, _ = make_user(UserRole.staff, store_id=store.id)
        # Signed with an unrelated key the verifier does not trust.
        token = make_supabase_token(
            sub=user.auth_user_id, signing_key=_WRONG_SIGNING_KEY
        )
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"

    def test_wrong_audience_is_rejected(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, _ = make_user(UserRole.staff, store_id=store.id)
        token = make_supabase_token(
            sub=user.auth_user_id, audience="not-authenticated"
        )
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"

    def test_expired_token_is_rejected(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, _ = make_user(UserRole.staff, store_id=store.id)
        # Issued two hours ago, valid for one hour → expired.
        token = make_supabase_token(
            sub=user.auth_user_id,
            issued_at=datetime.now(UTC) - timedelta(hours=2),
            expires_in_seconds=3600,
        )
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"

    def test_token_missing_sub_is_rejected(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        make_user(UserRole.staff, store_id=store.id)
        token = make_supabase_token(sub=None, include_sub=False)
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"

    def test_token_with_non_uuid_sub_is_rejected(self, client: TestClient):
        token = make_supabase_token(sub="not-a-uuid")
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"


class TestMeIdentityMapping:
    def test_token_without_mapped_user_is_rejected(self, client: TestClient):
        # Token verifies, but no public.users row has this auth_user_id.
        token = make_supabase_token(sub=uuid.uuid4())
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"

    def test_inactive_mapped_user_returns_403(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, _ = make_user(
            UserRole.staff, store_id=store.id, is_active=False
        )
        token = make_supabase_token(sub=user.auth_user_id)
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 403
        assert "inactive" in resp.json()["detail"].lower()


class TestMeClaimsAreNotAuthority:
    """The JWT identifies; public.users authorizes.

    Even if a token carries role / store_id / app_metadata claims, the
    response must reflect the database row, never the claims.
    """

    def test_role_and_store_come_from_db_not_claims(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        # DB user is a plain staff member bound to `store`.
        user, _ = make_user(UserRole.staff, store_id=store.id)
        bogus_store_id = str(uuid.uuid4())
        # Token lies: claims admin role and a different store.
        token = make_supabase_token(
            sub=user.auth_user_id,
            extra_claims={
                "role": "admin",
                "user_role": "admin",
                "store_id": bogus_store_id,
                "app_metadata": {
                    "role": "admin",
                    "store_id": bogus_store_id,
                },
            },
        )
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        # Authority is the DB row, not the token claims.
        assert body["role"] == UserRole.staff.value
        assert body["store_id"] == str(store.id)
        assert body["store_id"] != bogus_store_id
