from functools import lru_cache
from pathlib import Path
from typing import Annotated

from pydantic import field_validator
from pydantic import model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

DEVELOPMENT_ENV = "development"


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

    @model_validator(mode="after")
    def _enforce_cors_policy(self) -> "AppSettings":
        is_development = self.app_env.strip().lower() == DEVELOPMENT_ENV
        if is_development:
            return self

        if not self.backend_cors_origins:
            raise ValueError(
                "BACKEND_CORS_ORIGINS must declare at least one origin "
                "outside development."
            )

        if "*" in self.backend_cors_origins:
            raise ValueError(
                "BACKEND_CORS_ORIGINS cannot contain '*' outside development."
            )

        return self


class DatabaseSettings(CommonSettings):
    database_url: str


class SupabaseAuthSettings(CommonSettings):
    """Supabase Auth verification config (F2.22.2.D).

    FastAPI verifies Supabase-issued access tokens against the project's
    JWKS endpoint. The JWT establishes IDENTITY only — role, store_id and
    is_active always come from public.users, never from token claims.

    All fields default to empty so the app still imports/starts without
    Supabase configured (the test suite monkeypatches the JWKS resolver).
    A real deployment must set SUPABASE_URL (or SUPABASE_JWKS_URL directly).
    """

    supabase_url: str = ""
    supabase_jwks_url: str = ""
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_issuer: str = ""
    # F2.22.2.E will use the service-role key for the Supabase Admin API
    # (user creation). It is declared here so the env contract is stable,
    # but it is deliberately NOT read or used anywhere in F2.22.2.D.
    supabase_service_role_key: str = ""

    @model_validator(mode="after")
    def _derive_supabase_urls(self) -> "SupabaseAuthSettings":
        base = self.supabase_url.strip().rstrip("/")
        if base:
            if not self.supabase_jwks_url:
                self.supabase_jwks_url = f"{base}/auth/v1/.well-known/jwks.json"
            if not self.supabase_jwt_issuer:
                self.supabase_jwt_issuer = f"{base}/auth/v1"
        return self


class EmailSettings(CommonSettings):
    """Real business-email delivery config (F2.25.1 — config only).

    F2.25.1 prepares the server-only delivery contract for the existing
    business-email seam (`app.services.email_sender`); it does NOT wire a
    provider or send anything. Resend is the selected provider for F2.25,
    but no SDK or package is added — a later subphase (F2.25.2) implements
    the real sender. Until then the seam stays log-only.

    All fields default to safe/empty so the app imports and starts without
    email configured, and `email_enabled` defaults False so local, dev, and
    test stay log-only/offline. `resend_api_key` is a SERVER-ONLY SECRET:
    it lives on the backend only, is never exposed to the frontend, and is
    never logged.
    """

    email_enabled: bool = False
    email_provider: str = "resend"
    email_from_address: str = ""
    email_from_name: str = "NubeRush"
    resend_api_key: str = ""


@lru_cache
def get_app_settings() -> AppSettings:
    return AppSettings()


@lru_cache
def get_db_settings() -> DatabaseSettings:
    return DatabaseSettings()


@lru_cache
def get_supabase_auth_settings() -> SupabaseAuthSettings:
    return SupabaseAuthSettings()


@lru_cache
def get_email_settings() -> EmailSettings:
    return EmailSettings()
