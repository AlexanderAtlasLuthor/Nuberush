import os
import uuid
from collections.abc import Generator

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.orm import sessionmaker


SETTINGS_ENV_VARS = (
    "APP_NAME",
    "APP_ENV",
    "APP_DEBUG",
    "BACKEND_CORS_ORIGINS",
    "DATABASE_URL",
    # F2.22.2.D: strip Supabase auth vars so SupabaseAuthSettings falls
    # back to deterministic defaults (audience "authenticated", no
    # issuer) regardless of the host shell. The test suite verifies
    # tokens via a monkeypatched JWKS client, not real Supabase config.
    "SUPABASE_URL",
    "SUPABASE_JWKS_URL",
    "SUPABASE_JWT_AUDIENCE",
    "SUPABASE_JWT_ISSUER",
    "SUPABASE_SERVICE_ROLE_KEY",
)


TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL_TEST",
    "postgresql+psycopg://nuberush:nuberush@localhost:5432/nuberush_test",
)


def _get_alembic_config() -> Config:
    return Config("alembic.ini")


def _should_reset_test_db() -> bool:
    return os.environ.get("RESET_TEST_DB") == "1"


def _prepare_test_database() -> None:
    """Prepare the test database schema for this pytest session.

    Default fast path: run `alembic upgrade head` only. Alembic is
    idempotent when the database is already current, so focused DB
    tests avoid paying the destructive rebuild cost on every pytest
    invocation.

    Reset path: set RESET_TEST_DB=1 when a clean rebuild is needed
    after migration churn or suspected local DB drift. That opt-in
    path preserves the old downgrade(base) -> upgrade(head) behavior.
    """
    cfg = _get_alembic_config()
    if _should_reset_test_db():
        command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")


@pytest.fixture(autouse=True)
def _isolate_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Strip settings env vars per-test so each suite starts from a known state
    # and only sets exactly what it needs.
    for var in SETTINGS_ENV_VARS:
        monkeypatch.delenv(var, raising=False)

    # Stripping the process env above is NOT enough on its own: every settings
    # class sets `model_config = SettingsConfigDict(env_file=ENV_FILE)`, so
    # pydantic-settings re-reads backend/.env from disk on each instantiation
    # and the dev Supabase/DB config leaks straight back in (a populated
    # SUPABASE_URL derives an issuer, which makes verify_supabase_jwt require
    # an `iss` claim the bare test tokens don't carry -> 401 "Invalid token").
    #
    # Neutralize the file source for the duration of each test so settings
    # reflect the process env ONLY (the contract the suite already assumes).
    # Each concrete class carries its OWN merged model_config dict, so patch
    # all three, not just CommonSettings. monkeypatch.setitem auto-reverts on
    # teardown, leaving production behavior untouched. Tests that genuinely
    # need Supabase config opt in via monkeypatch.setenv(...).
    from app.core import config

    for settings_cls in (
        config.AppSettings,
        config.DatabaseSettings,
        config.SupabaseAuthSettings,
    ):
        monkeypatch.setitem(settings_cls.model_config, "env_file", None)

    # Drop any value cached from a prior (file-backed) instantiation so the
    # next call rebuilds from the now file-free source.
    config.get_app_settings.cache_clear()
    config.get_db_settings.cache_clear()
    config.get_supabase_auth_settings.cache_clear()


@pytest.fixture(autouse=True)
def _supabase_jwt_verifier(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the Supabase JWT verifier at the test-only keypair.

    F2.22.2.D: `app.api.deps.get_current_user` verifies Supabase access
    tokens via `app.core.supabase_auth.verify_supabase_jwt`, which fetches
    signing keys from a JWKS endpoint. Tokens minted by
    `tests.helpers.auth` (`make_supabase_token` / `auth_headers_for`) are
    signed with a throwaway RSA keypair generated in that module.

    This autouse fixture swaps the verifier's JWKS client for a fake that
    returns that keypair's public half. Verification stays fully real —
    signature, audience, expiry and required-claim checks all run — but
    offline: no network, no live Supabase project.
    """
    from types import SimpleNamespace

    from app.core import supabase_auth
    from app.core.config import get_supabase_auth_settings
    from tests.helpers.auth import get_test_public_key

    class _FakeJWKClient:
        """Stands in for jwt.PyJWKClient: always yields the test key."""

        def get_signing_key_from_jwt(self, token: str):  # noqa: ARG002
            return SimpleNamespace(key=get_test_public_key())

    # Fresh settings each test (deterministic defaults), and route the
    # verifier through the fake client.
    get_supabase_auth_settings.cache_clear()
    supabase_auth.reset_jwk_client_cache()
    monkeypatch.setattr(
        supabase_auth, "_get_jwk_client", lambda: _FakeJWKClient()
    )


class _FakeSupabaseAdmin:
    """In-memory stand-in for app.services.supabase_admin (F2.22.2.E).

    Records calls and lets a test simulate failures, so POST /auth/users
    can be exercised offline and deterministically — no real Supabase
    project, no service-role key.
    """

    def __init__(self) -> None:
        self.created: list[dict] = []  # email / password / user_metadata / id
        self.deleted: list[uuid.UUID] = []  # auth_user_ids passed to delete
        self.create_should_fail = False
        self.delete_should_fail = False
        self.next_auth_user_id: uuid.UUID | None = None  # pin the returned id

    def create_auth_user(
        self, email: str, password: str, user_metadata: dict | None = None
    ) -> uuid.UUID:
        from app.services.supabase_admin import SupabaseAdminError

        if self.create_should_fail:
            raise SupabaseAdminError("simulated Supabase create failure")
        new_id = self.next_auth_user_id or uuid.uuid4()
        self.created.append(
            {
                "email": email,
                "password": password,
                "user_metadata": user_metadata,
                "id": new_id,
            }
        )
        return new_id

    def delete_auth_user(self, auth_user_id: uuid.UUID) -> None:
        from app.services.supabase_admin import SupabaseAdminError

        self.deleted.append(auth_user_id)
        if self.delete_should_fail:
            raise SupabaseAdminError("simulated Supabase delete failure")


@pytest.fixture(autouse=True)
def supabase_admin_fake(monkeypatch: pytest.MonkeyPatch) -> _FakeSupabaseAdmin:
    """Swap the Supabase Admin API wrapper for an offline fake.

    F2.22.2.E: POST /auth/users calls `app.services.supabase_admin` to
    create (and, on rollback, delete) `auth.users` records. The suite must
    never hit a real Supabase project, so this autouse fixture replaces
    both functions with `_FakeSupabaseAdmin` methods. Tests that exercise
    the endpoint request this fixture by name to inspect calls
    (`fake.created` / `fake.deleted`) or to simulate failures
    (`fake.create_should_fail` / `fake.delete_should_fail`).
    """
    from app.services import supabase_admin

    fake = _FakeSupabaseAdmin()
    monkeypatch.setattr(
        supabase_admin, "create_auth_user", fake.create_auth_user
    )
    monkeypatch.setattr(
        supabase_admin, "delete_auth_user", fake.delete_auth_user
    )
    return fake


@pytest.fixture(scope="session")
def migrated_test_db() -> Generator[str, None, None]:
    """Ensure the configured test database is migrated for this session."""
    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

    from app.core.config import get_db_settings

    get_db_settings.cache_clear()
    _prepare_test_database()

    try:
        yield TEST_DATABASE_URL
    finally:
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url
        get_db_settings.cache_clear()


@pytest.fixture(scope="session")
def test_engine(migrated_test_db: str) -> Generator[Engine, None, None]:
    """Engine bound to the migrated test database.

    Uses DATABASE_URL_TEST or a local default. The schema is prepared by
    migrated_test_db so triggers and other DDL stay in sync with production
    migrations.
    """
    engine = create_engine(migrated_test_db, pool_pre_ping=True, future=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def db_session(test_engine: Engine) -> Generator[Session, None, None]:
    """Per-test transactional session that rolls back on teardown.

    Uses the SAVEPOINT-on-commit pattern so test code can call session.commit()
    without affecting other tests.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    SessionLocal = sessionmaker(
        bind=connection, autocommit=False, autoflush=False, future=True
    )
    session = SessionLocal()
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def _restart_savepoint(sess: Session, trans) -> None:  # type: ignore[no-untyped-def]
        nonlocal nested
        if trans.nested and not trans._parent.nested:  # type: ignore[attr-defined]
            nested = connection.begin_nested()

    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def client(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with get_db overridden to the transactional session."""
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)

    from app.core.config import get_db_settings

    get_db_settings.cache_clear()

    from app.db.session import get_db
    from app.main import app

    def _override_get_db() -> Generator[Session, None, None]:
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        with TestClient(app) as c:
            yield c
    finally:
        app.dependency_overrides.pop(get_db, None)
        get_db_settings.cache_clear()


