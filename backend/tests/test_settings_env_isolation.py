"""Guard tests for backend test-env isolation (F2.24.X1).

The autouse `_isolate_settings_env` fixture in conftest must guarantee that
the test harness reflects PROCESS ENV ONLY — it must never read the dev
`backend/.env` file. Without that, a populated `SUPABASE_URL` in `.env`
leaks through pydantic-settings, derives a JWT issuer, and makes
`verify_supabase_jwt` reject every bare test token with 401 "Invalid token"
(the ~825-failure baseline this fixture exists to prevent).

These tests are the canary: if a future change re-enables `.env` loading
under pytest, exactly one focused test fails here instead of hundreds of
opaque 401s across the suite.
"""
from __future__ import annotations

import pytest


def test_supabase_settings_do_not_load_backend_dotenv_by_default() -> None:
    """With no Supabase process env set, settings must be empty.

    If `backend/.env` were still being read, `supabase_url` would be the
    live project URL and the derived issuer/JWKS fields would be populated.
    """
    from app.core.config import get_supabase_auth_settings

    # The autouse fixture already cleared the cache after disabling env_file,
    # but clear again to be explicit and independent of fixture ordering.
    get_supabase_auth_settings.cache_clear()
    settings = get_supabase_auth_settings()

    assert settings.supabase_url == ""
    assert settings.supabase_jwks_url == ""
    assert settings.supabase_jwt_issuer == ""


def test_supabase_settings_can_opt_in_via_process_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A test that genuinely needs Supabase config opts in via process env.

    Disabling the `.env` file must not break the opt-in path: setting
    `SUPABASE_URL` in the process env (and clearing the cache) must still
    flow through and derive the issuer + JWKS URL.
    """
    from app.core.config import get_supabase_auth_settings

    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    get_supabase_auth_settings.cache_clear()
    settings = get_supabase_auth_settings()

    assert settings.supabase_url == "https://example.supabase.co"
    assert (
        settings.supabase_jwt_issuer
        == "https://example.supabase.co/auth/v1"
    )
    assert (
        settings.supabase_jwks_url
        == "https://example.supabase.co/auth/v1/.well-known/jwks.json"
    )

    # Leave no cached opt-in value behind for the next test.
    get_supabase_auth_settings.cache_clear()


def test_admin_settings_update_schema_only_exposes_safe_fields() -> None:
    """F2.27.10: the writable Admin Settings contract must NEVER admit an
    env-backed or secret field. The mutation schema's field set is the
    authoritative allow-list — if a future edit adds a sensitive field, this
    canary fails instead of leaking it through PATCH.
    """
    from app.schemas.admin_settings import AdminSettingsUpdate

    assert set(AdminSettingsUpdate.model_fields) == {
        "platform_name",
        "support_email",
        "default_locale",
        "default_timezone",
    }

    forbidden = {
        "app_env",
        "app_debug",
        "version",
        "database_url",
        "supabase_url",
        "supabase_service_role_key",
        "supabase_jwks_url",
        "resend_api_key",
        "backend_cors_origins",
        "commission_rate_basis_points",
        "currency",
    }
    assert forbidden.isdisjoint(AdminSettingsUpdate.model_fields)


def test_admin_editable_section_only_exposes_safe_fields() -> None:
    """The persisted editable block surfaced on GET also stays inside the
    four-field allow-list — no secret/env value rides along on the response.
    """
    from app.schemas.admin_settings import AdminEditableSettings

    assert set(AdminEditableSettings.model_fields) == {
        "platform_name",
        "support_email",
        "default_locale",
        "default_timezone",
    }


def test_quickbooks_settings_default_safe_and_empty() -> None:
    """F2.27.9.A: with no QuickBooks process env set, settings must be safe.

    If `backend/.env` were still being read (or a host shell leaked a value),
    a real QUICKBOOKS_CLIENT_SECRET / QUICKBOOKS_TOKEN_ENCRYPTION_KEY would
    appear here. The offline suite must start QuickBooks-unconfigured: blank
    secrets, blank token-encryption key, sandbox environment.
    """
    from app.core.config import get_quickbooks_settings

    get_quickbooks_settings.cache_clear()
    settings = get_quickbooks_settings()

    assert settings.quickbooks_client_id == ""
    assert settings.quickbooks_client_secret == ""
    assert settings.quickbooks_redirect_url == ""
    assert settings.quickbooks_token_encryption_key == ""
    # Safe defaults: sandbox environment, modest timeout / item cap.
    assert settings.quickbooks_environment == "sandbox"
    assert settings.quickbooks_timeout_seconds == 10.0
    assert settings.quickbooks_max_items_per_run == 100


def test_quickbooks_settings_can_opt_in_via_process_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A test that needs QuickBooks config opts in via process env.

    Disabling the `.env` file must not break the opt-in path: setting the
    QuickBooks vars in the process env (and clearing the cache) must flow
    through. The secret values stay server-side — they are read here only to
    prove the loader works, never serialized to a client.
    """
    from app.core.config import get_quickbooks_settings

    monkeypatch.setenv("QUICKBOOKS_CLIENT_ID", "test-client-id")
    monkeypatch.setenv("QUICKBOOKS_CLIENT_SECRET", "test-client-secret")
    monkeypatch.setenv("QUICKBOOKS_ENVIRONMENT", "production")
    get_quickbooks_settings.cache_clear()
    settings = get_quickbooks_settings()

    assert settings.quickbooks_client_id == "test-client-id"
    assert settings.quickbooks_client_secret == "test-client-secret"
    assert settings.quickbooks_environment == "production"

    # Leave no cached opt-in value behind for the next test.
    get_quickbooks_settings.cache_clear()
