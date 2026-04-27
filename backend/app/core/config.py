from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic import model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

DEVELOPMENT_ENV = "development"
JWT_SECRET_MIN_LENGTH = 32
JWT_SECRET_BLOCKLIST = frozenset(
    {"change-me", "dev-secret", "secret", "password", "jwt-secret"}
)
JWT_SECRET_DEV_PREFIXES = ("dev-only-",)


class CommonSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


class AppSettings(CommonSettings):
    app_name: str = "NubeRush API"
    app_env: str = DEVELOPMENT_ENV
    app_debug: bool = True
    # NoDecode keeps pydantic-settings from JSON-parsing this env var so the
    # field_validator below sees the raw CSV string we actually receive.
    backend_cors_origins: Annotated[list[str], NoDecode] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    @field_validator("backend_cors_origins", mode="before")
    @classmethod
    def _split_cors_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


class DatabaseSettings(CommonSettings):
    database_url: str


class AuthSettings(CommonSettings):
    app_env: str = DEVELOPMENT_ENV
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    @model_validator(mode="after")
    def _enforce_jwt_secret_policy(self) -> "AuthSettings":
        secret = (self.jwt_secret_key or "").strip()
        if not secret:
            raise ValueError("JWT_SECRET_KEY must not be empty.")

        is_development = self.app_env.strip().lower() == DEVELOPMENT_ENV
        if is_development:
            return self

        if secret.lower() in JWT_SECRET_BLOCKLIST:
            raise ValueError(
                "JWT_SECRET_KEY uses a known insecure value. "
                "Set a strong secret before running outside development."
            )
        if any(secret.lower().startswith(prefix) for prefix in JWT_SECRET_DEV_PREFIXES):
            raise ValueError(
                "JWT_SECRET_KEY contains a development-only marker. "
                "Generate a production secret before running outside development."
            )
        if len(secret) < JWT_SECRET_MIN_LENGTH:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least {JWT_SECRET_MIN_LENGTH} characters "
                f"outside development."
            )
        return self


@lru_cache
def get_app_settings() -> AppSettings:
    return AppSettings()


@lru_cache
def get_db_settings() -> DatabaseSettings:
    return DatabaseSettings()


@lru_cache
def get_auth_settings() -> AuthSettings:
    return AuthSettings()
