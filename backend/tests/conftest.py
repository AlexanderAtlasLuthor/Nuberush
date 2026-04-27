import pytest


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


@pytest.fixture(autouse=True)
def _isolate_settings_env(monkeypatch: pytest.MonkeyPatch) -> None:
    # Remove any settings-related env var leaked from the host shell or .env so
    # each test starts from a known state and only sets what it needs.
    for var in SETTINGS_ENV_VARS:
        monkeypatch.delenv(var, raising=False)
