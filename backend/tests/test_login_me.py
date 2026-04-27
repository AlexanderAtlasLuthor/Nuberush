import uuid
from datetime import UTC
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Callable

import jwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_auth_settings
from app.core.security import hash_password
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole


# ---------------------------------------------------------------------------
# Fixtures local to this suite
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
    """Returns (user, plaintext_password) so login tests can use real creds."""

    def _create(
        role: UserRole,
        store_id: uuid.UUID | None = None,
        email: str | None = None,
        password: str = "supersecret123",
        is_active: bool = True,
    ) -> tuple[User, str]:
        user = User(
            full_name=f"Login {role.value}",
            email=email or f"{role.value}-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password(password),
            role=role,
            store_id=store_id,
            is_active=is_active,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user, password

    return _create


def _forge_token(claims: dict[str, Any]) -> str:
    """Encode an arbitrary claim set with the test secret/algorithm.

    Used to build tokens that violate one specific rule (missing sub, wrong
    iss, expired, etc.) without relying on create_access_token.
    """
    settings = get_auth_settings()
    return jwt.encode(
        claims, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def _base_claims(sub: str | None = None, **overrides: Any) -> dict[str, Any]:
    settings = get_auth_settings()
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": sub if sub is not None else str(uuid.uuid4()),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=10)).timestamp()),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
    }
    claims.update(overrides)
    return claims


# ---------------------------------------------------------------------------
# /auth/login
# ---------------------------------------------------------------------------


class TestLoginSuccess:
    def test_login_returns_bearer_token(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, password = make_user(UserRole.staff, store_id=store.id)
        resp = client.post(
            "/auth/login",
            json={"email": user.email, "password": password},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["token_type"] == "bearer"
        assert isinstance(body["access_token"], str)
        assert body["access_token"].count(".") == 2  # JWT shape

    def test_token_carries_required_claims(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, password = make_user(UserRole.manager, store_id=store.id)
        resp = client.post(
            "/auth/login",
            json={"email": user.email, "password": password},
        )
        assert resp.status_code == 200
        token = resp.json()["access_token"]
        settings = get_auth_settings()
        decoded = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
            issuer=settings.jwt_issuer,
            audience=settings.jwt_audience,
        )
        for claim in ("sub", "exp", "iat", "iss", "aud"):
            assert claim in decoded, f"missing claim {claim}"
        assert decoded["sub"] == str(user.id)
        assert decoded["iss"] == settings.jwt_issuer
        assert decoded["aud"] == settings.jwt_audience
        assert decoded["exp"] > decoded["iat"]

    def test_login_normalizes_email_case(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, password = make_user(
            UserRole.staff, store_id=store.id, email="case@example.com"
        )
        resp = client.post(
            "/auth/login",
            json={"email": "CASE@example.com", "password": password},
        )
        assert resp.status_code == 200


class TestLoginFailures:
    def test_wrong_password_returns_401(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, _ = make_user(UserRole.staff, store_id=store.id)
        resp = client.post(
            "/auth/login",
            json={"email": user.email, "password": "wrong-password"},
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid email or password"

    def test_unknown_email_returns_401_with_same_detail(self, client: TestClient):
        resp = client.post(
            "/auth/login",
            json={"email": "ghost@example.com", "password": "supersecret123"},
        )
        assert resp.status_code == 401
        # Same detail string as wrong-password — no enumeration leak.
        assert resp.json()["detail"] == "Invalid email or password"

    def test_inactive_user_returns_403(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, password = make_user(
            UserRole.staff, store_id=store.id, is_active=False
        )
        resp = client.post(
            "/auth/login",
            json={"email": user.email, "password": password},
        )
        assert resp.status_code == 403
        assert "inactive" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# /auth/me
# ---------------------------------------------------------------------------


class TestMeSuccess:
    def test_valid_token_returns_user(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, password = make_user(UserRole.owner, store_id=store.id)
        login = client.post(
            "/auth/login",
            json={"email": user.email, "password": password},
        )
        token = login.json()["access_token"]
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(user.id)
        assert body["email"] == user.email
        assert body["role"] == UserRole.owner.value
        assert body["store_id"] == str(store.id)

    def test_response_does_not_leak_password_hash(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, password = make_user(UserRole.staff, store_id=store.id)
        login = client.post(
            "/auth/login",
            json={"email": user.email, "password": password},
        )
        resp = client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {login.json()['access_token']}"},
        )
        body = resp.json()
        assert "password_hash" not in body
        assert "password" not in body
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
        # FastAPI's HTTPBearer with auto_error=False treats a non-Bearer
        # scheme as "no credentials" and yields None, which we map to 401.
        assert resp.status_code == 401

    def test_garbage_token_returns_401_invalid(self, client: TestClient):
        resp = client.get(
            "/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"

    def test_token_signed_with_wrong_secret_returns_401(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, _ = make_user(UserRole.staff, store_id=store.id)
        bad_token = jwt.encode(
            _base_claims(sub=str(user.id)),
            "this-is-not-the-real-secret",
            algorithm="HS256",
        )
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {bad_token}"}
        )
        assert resp.status_code == 401


class TestMeTokenClaimsValidation:
    def test_expired_token_returns_401_with_specific_detail(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, _ = make_user(UserRole.staff, store_id=store.id)
        now = datetime.now(UTC)
        token = _forge_token(
            _base_claims(
                sub=str(user.id),
                iat=int((now - timedelta(hours=2)).timestamp()),
                exp=int((now - timedelta(hours=1)).timestamp()),
            )
        )
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Token expired"

    def test_token_missing_sub_is_rejected(self, client: TestClient):
        claims = _base_claims()
        claims.pop("sub")
        token = _forge_token(claims)
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"

    def test_token_with_non_uuid_sub_is_rejected(self, client: TestClient):
        token = _forge_token(_base_claims(sub="not-a-uuid"))
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"

    def test_token_for_unknown_user_is_rejected(self, client: TestClient):
        token = _forge_token(_base_claims(sub=str(uuid.uuid4())))
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"

    def test_token_with_wrong_issuer_is_rejected(self, client: TestClient):
        token = _forge_token(_base_claims(iss="someone-else"))
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"

    def test_token_with_wrong_audience_is_rejected(self, client: TestClient):
        token = _forge_token(_base_claims(aud="someone-else"))
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401
        assert resp.json()["detail"] == "Invalid token"

    def test_token_missing_iat_is_rejected(self, client: TestClient):
        claims = _base_claims()
        claims.pop("iat")
        token = _forge_token(claims)
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 401


class TestMeUserState:
    def test_inactive_user_returns_403(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        user, _ = make_user(
            UserRole.staff, store_id=store.id, is_active=False
        )
        token = _forge_token(_base_claims(sub=str(user.id)))
        resp = client.get(
            "/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 403
        assert "inactive" in resp.json()["detail"].lower()
