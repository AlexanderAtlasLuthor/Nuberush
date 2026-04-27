import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config import AppSettings


# ---------------------------------------------------------------------------
# Settings-level CORS policy
# ---------------------------------------------------------------------------


class TestCorsPolicyOnSettings:
    def test_wildcard_in_development_is_allowed(self):
        # Development is permissive so local hacking with `*` is possible.
        settings = AppSettings(
            _env_file=None,
            app_env="development",
            backend_cors_origins=["*"],
        )
        assert settings.backend_cors_origins == ["*"]

    def test_wildcard_in_production_is_rejected(self):
        with pytest.raises(ValidationError) as excinfo:
            AppSettings(
                _env_file=None,
                app_env="production",
                backend_cors_origins=["*"],
            )
        assert "cannot contain '*'" in str(excinfo.value)

    def test_wildcard_in_staging_is_rejected(self):
        with pytest.raises(ValidationError) as excinfo:
            AppSettings(
                _env_file=None,
                app_env="staging",
                backend_cors_origins=["*"],
            )
        assert "cannot contain '*'" in str(excinfo.value)

    def test_wildcard_alongside_real_origins_is_rejected(self):
        with pytest.raises(ValidationError):
            AppSettings(
                _env_file=None,
                app_env="production",
                backend_cors_origins=["https://app.example.com", "*"],
            )

    def test_empty_origins_in_production_is_rejected(self):
        with pytest.raises(ValidationError) as excinfo:
            AppSettings(
                _env_file=None,
                app_env="production",
                backend_cors_origins=[],
            )
        assert "must declare at least one origin" in str(excinfo.value)

    def test_empty_origins_in_development_is_allowed(self):
        # Dev may legitimately want CORS off entirely.
        settings = AppSettings(
            _env_file=None,
            app_env="development",
            backend_cors_origins=[],
        )
        assert settings.backend_cors_origins == []

    def test_csv_string_with_real_origins_in_production_is_accepted(self):
        settings = AppSettings(
            _env_file=None,
            app_env="production",
            backend_cors_origins="https://app.example.com,https://admin.example.com",
        )
        assert settings.backend_cors_origins == [
            "https://app.example.com",
            "https://admin.example.com",
        ]

    def test_env_var_with_wildcard_in_production_is_rejected(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.setenv("BACKEND_CORS_ORIGINS", "*")
        with pytest.raises(ValidationError):
            AppSettings(_env_file=None)


# ---------------------------------------------------------------------------
# Live CORSMiddleware behaviour through the actual FastAPI app
# ---------------------------------------------------------------------------
#
# The app loads CORS settings once at import time. The conftest `client`
# fixture sets APP_ENV=development and falls back to the default origins
# ("http://localhost:3000", "http://127.0.0.1:3000") for backend_cors_origins.

ALLOWED_ORIGIN = "http://localhost:3000"
DISALLOWED_ORIGIN = "http://evil.test"


class TestCorsSimpleRequests:
    def test_allowed_origin_receives_acao_header(self, client: TestClient):
        resp = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN

    def test_second_default_origin_is_also_allowed(self, client: TestClient):
        resp = client.get(
            "/health", headers={"Origin": "http://127.0.0.1:3000"}
        )
        assert resp.status_code == 200
        assert (
            resp.headers.get("access-control-allow-origin")
            == "http://127.0.0.1:3000"
        )

    def test_disallowed_origin_does_not_get_acao_header(
        self, client: TestClient
    ):
        resp = client.get("/health", headers={"Origin": DISALLOWED_ORIGIN})
        # The request itself is not blocked server-side, but the browser
        # would refuse the response because there is no matching ACAO.
        assert resp.status_code == 200
        acao = resp.headers.get("access-control-allow-origin")
        assert acao != DISALLOWED_ORIGIN
        assert acao is None or acao == ""

    def test_credentials_are_allowed_for_real_origins(
        self, client: TestClient
    ):
        resp = client.get("/health", headers={"Origin": ALLOWED_ORIGIN})
        assert (
            resp.headers.get("access-control-allow-credentials") == "true"
        )


class TestCorsPreflight:
    def test_preflight_for_allowed_origin(self, client: TestClient):
        resp = client.options(
            "/auth/users",
            headers={
                "Origin": ALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "authorization,content-type",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN
        allow_methods = resp.headers.get("access-control-allow-methods", "")
        assert "POST" in allow_methods or allow_methods == "*"

    def test_preflight_for_disallowed_origin_is_rejected(
        self, client: TestClient
    ):
        resp = client.options(
            "/auth/users",
            headers={
                "Origin": DISALLOWED_ORIGIN,
                "Access-Control-Request-Method": "POST",
            },
        )
        # Starlette returns 400 "Disallowed CORS origin" for preflight from
        # an origin not in the allow-list.
        assert resp.status_code == 400
        assert (
            resp.headers.get("access-control-allow-origin")
            != DISALLOWED_ORIGIN
        )


class TestCorsDoesNotBreakAuthRoutes:
    """Sanity: the middleware did not change /auth/* contracts."""

    def test_login_still_returns_token_with_origin_header(
        self, client: TestClient, db_session
    ):
        from app.core.security import hash_password
        from app.db.models import Store, User, UserRole
        import uuid

        store = Store(name="C", code=f"cors-{uuid.uuid4().hex[:6]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)

        user = User(
            full_name="cors",
            email=f"cors-{uuid.uuid4().hex[:6]}@example.com",
            password_hash=hash_password("supersecret123"),
            role=UserRole.staff,
            store_id=store.id,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)

        resp = client.post(
            "/auth/login",
            json={"email": user.email, "password": "supersecret123"},
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert resp.status_code == 200
        assert "access_token" in resp.json()
        assert resp.headers.get("access-control-allow-origin") == ALLOWED_ORIGIN

    def test_register_still_403_with_origin_header(self, client: TestClient):
        resp = client.post(
            "/auth/register",
            json={
                "full_name": "x",
                "email": "x@example.com",
                "password": "supersecret123",
                "role": "admin",
            },
            headers={"Origin": ALLOWED_ORIGIN},
        )
        assert resp.status_code == 403
