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
