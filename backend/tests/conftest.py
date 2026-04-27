import os
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
    "JWT_SECRET_KEY",
    "JWT_ALGORITHM",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "BACKEND_CORS_ORIGINS",
    "DATABASE_URL",
)


TEST_DATABASE_URL = os.environ.get(
    "DATABASE_URL_TEST",
    "postgresql+psycopg://nuberush:nuberush@localhost:5432/nuberush_test",
)


@pytest.fixture(autouse=True)
def _isolate_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Strip settings env vars per-test so each suite starts from a known state
    # and only sets exactly what it needs.
    for var in SETTINGS_ENV_VARS:
        monkeypatch.delenv(var, raising=False)


@pytest.fixture(scope="session")
def test_engine() -> Generator[Engine, None, None]:
    """Engine bound to the test database with migrations applied once.

    Uses DATABASE_URL_TEST or a local default. The schema is created by
    running alembic against that URL so triggers and other DDL stay in sync
    with production migrations.
    """
    previous_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = TEST_DATABASE_URL

    from app.core.config import get_db_settings

    get_db_settings.cache_clear()

    cfg = Config("alembic.ini")
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")

    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True, future=True)
    try:
        yield engine
    finally:
        engine.dispose()
        if previous_url is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous_url
        get_db_settings.cache_clear()


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
    """FastAPI TestClient with get_db overridden to the transactional session.

    Sets a development JWT secret so AuthSettings instantiates cleanly without
    relying on the host shell environment.
    """
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("JWT_SECRET_KEY", "dev-only-test-secret")
    monkeypatch.setenv("DATABASE_URL", TEST_DATABASE_URL)

    from app.core.config import get_auth_settings, get_db_settings

    get_auth_settings.cache_clear()
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
        get_auth_settings.cache_clear()
        get_db_settings.cache_clear()


