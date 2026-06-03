"""Tests for the F2.25.1 email-delivery config (config only).

F2.25.1 adds `EmailSettings` / `get_email_settings()` to `app.core.config`
to declare the server-only business-email delivery contract. No provider is
wired and no email is sent yet (that is F2.25.2) — these tests only prove:

  1. Defaults are safe: delivery is disabled, provider is "resend", and no
     address/key is present.
  2. Process-env values override the defaults.
  3. Under pytest the settings reflect PROCESS ENV ONLY — a populated dev
     `backend/.env` (e.g. EMAIL_ENABLED=true, a real RESEND_API_KEY) must
     never leak in. This mirrors `test_settings_env_isolation.py`: the
     autouse `_isolate_settings_env` fixture strips the EMAIL_* vars and
     neutralizes the `.env` file source.

No network, no provider import, no EmailSender touch.
"""
from __future__ import annotations

import pytest


def test_email_settings_safe_defaults() -> None:
    """With no email process env set, settings must be safe/empty.

    If `backend/.env` were still being read, a developer's EMAIL_ENABLED or
    RESEND_API_KEY would leak through here.
    """
    from app.core.config import get_email_settings

    # The autouse fixture already cleared the cache after disabling env_file,
    # but clear again to be explicit and independent of fixture ordering.
    get_email_settings.cache_clear()
    settings = get_email_settings()

    assert settings.email_enabled is False
    assert settings.email_provider == "resend"
    assert settings.email_from_address == ""
    assert settings.email_from_name == "NubeRush"
    assert settings.resend_api_key == ""


def test_email_settings_override_via_process_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Process-env values must override the defaults.

    Disabling the `.env` file must not break the opt-in path: setting the
    EMAIL_* vars in the process env (and clearing the cache) flows through.
    """
    from app.core.config import get_email_settings

    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("EMAIL_PROVIDER", "resend")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "notifications@example.com")
    monkeypatch.setenv("EMAIL_FROM_NAME", "Example App")
    monkeypatch.setenv("RESEND_API_KEY", "test_resend_key")
    get_email_settings.cache_clear()
    settings = get_email_settings()

    assert settings.email_enabled is True
    assert settings.email_provider == "resend"
    assert settings.email_from_address == "notifications@example.com"
    assert settings.email_from_name == "Example App"
    assert settings.resend_api_key == "test_resend_key"

    # Leave no cached opt-in value behind for the next test.
    get_email_settings.cache_clear()


def test_email_settings_do_not_load_backend_dotenv_by_default() -> None:
    """pytest must not read backend/.env email values.

    Independent of whatever a developer has in `backend/.env`, a fresh
    `get_email_settings()` with no email process env set must return the
    safe defaults — proving the test harness reflects process env only.
    """
    from app.core.config import get_email_settings

    get_email_settings.cache_clear()
    settings = get_email_settings()

    assert settings.email_enabled is False
    assert settings.resend_api_key == ""
