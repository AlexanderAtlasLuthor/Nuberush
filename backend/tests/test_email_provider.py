"""Tests for the real Resend business-email transport (F2.25.2).

All offline: every test either proves no `httpx.post` is attempted (the
disabled/misconfigured fallbacks) or monkeypatches the provider module's
`httpx.post` to capture the request without touching the network. The
RESEND_API_KEY used here is the literal placeholder `test_resend_key`; the
suite also asserts it never leaks into logs or exception messages.

Style mirrors `test_email_settings.py`: env via monkeypatch.setenv, with
`get_email_settings.cache_clear()` after each change (the autouse
`_isolate_settings_env` fixture clears the EMAIL_* env + cache between
tests, so these tests only need to clear after their own opt-in).
"""
from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest

from app.core.config import get_email_settings
from app.services import email_provider
from app.services.email_provider import ResendEmailSender
from app.services.email_provider import build_email_sender
from app.services.email_sender import BusinessEmailMessage
from app.services.email_sender import EmailSenderError
from app.services.email_sender import _LoggingEmailSender


_KEY = "test_resend_key"


def _message() -> BusinessEmailMessage:
    return BusinessEmailMessage(
        event_type="store_application_submitted",
        to_email="owner@example.com",
        subject="Your NubeRush store application was received",
        body="Hi Jane,\n\nThanks for applying.\n\n— The NubeRush Team",
    )


@pytest.fixture
def explode_post(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if any code path calls httpx.post (proves no network)."""

    def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("httpx.post must not be called in this path")

    monkeypatch.setattr(email_provider.httpx, "post", _boom)


class _PostRecorder:
    """Capture a single httpx.post call and return a canned response."""

    def __init__(self, status_code: int = 200) -> None:
        self.status_code = status_code
        self.calls: list[dict] = []

    def __call__(
        self,
        url: str,
        *,
        headers: dict,
        json: dict,
        timeout: float,
    ) -> SimpleNamespace:
        self.calls.append(
            {"url": url, "headers": headers, "json": json, "timeout": timeout}
        )
        return SimpleNamespace(status_code=self.status_code)


def _enable(
    monkeypatch: pytest.MonkeyPatch,
    *,
    from_address: str = "notifications@example.com",
    from_name: str = "NubeRush",
    api_key: str = _KEY,
    provider: str = "resend",
) -> None:
    monkeypatch.setenv("EMAIL_ENABLED", "true")
    monkeypatch.setenv("EMAIL_PROVIDER", provider)
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", from_address)
    monkeypatch.setenv("EMAIL_FROM_NAME", from_name)
    monkeypatch.setenv("RESEND_API_KEY", api_key)
    get_email_settings.cache_clear()


# ------------------------------------------------------------------ #
# A. disabled default -> logging fallback, no network
# ------------------------------------------------------------------ #
def test_disabled_default_uses_logging_fallback_no_network(
    explode_post: None,
) -> None:
    get_email_settings.cache_clear()
    sender = build_email_sender()

    assert isinstance(sender, _LoggingEmailSender)
    # Must not touch the network even when actually sending.
    sender.send(_message())


# ------------------------------------------------------------------ #
# B. enabled + missing RESEND_API_KEY -> fallback, no network
# ------------------------------------------------------------------ #
def test_enabled_missing_api_key_falls_back_no_network(
    monkeypatch: pytest.MonkeyPatch, explode_post: None
) -> None:
    _enable(monkeypatch, api_key="")

    sender = build_email_sender()
    assert isinstance(sender, _LoggingEmailSender)
    sender.send(_message())


# ------------------------------------------------------------------ #
# C. enabled + missing EMAIL_FROM_ADDRESS -> fallback, no network
# ------------------------------------------------------------------ #
def test_enabled_missing_from_address_falls_back_no_network(
    monkeypatch: pytest.MonkeyPatch, explode_post: None
) -> None:
    _enable(monkeypatch, from_address="")

    sender = build_email_sender()
    assert isinstance(sender, _LoggingEmailSender)
    sender.send(_message())


# ------------------------------------------------------------------ #
# D. valid config -> posts expected Resend payload
# ------------------------------------------------------------------ #
def test_valid_config_posts_expected_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    recorder = _PostRecorder(status_code=200)
    monkeypatch.setattr(email_provider.httpx, "post", recorder)

    sender = build_email_sender()
    assert isinstance(sender, ResendEmailSender)

    msg = _message()
    sender.send(msg)

    assert len(recorder.calls) == 1
    call = recorder.calls[0]
    assert call["url"] == "https://api.resend.com/emails"
    assert call["headers"]["Authorization"] == "Bearer test_resend_key"
    assert call["headers"]["Content-Type"] == "application/json"
    assert call["json"]["from"] == "NubeRush <notifications@example.com>"
    assert msg.to_email in call["json"]["to"]
    assert call["json"]["subject"] == msg.subject
    assert call["json"]["text"] == msg.body
    assert call["timeout"] == 10.0


# ------------------------------------------------------------------ #
# E. blank EMAIL_FROM_NAME -> raw from address
# ------------------------------------------------------------------ #
def test_blank_from_name_uses_raw_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch, from_name="")
    recorder = _PostRecorder(status_code=200)
    monkeypatch.setattr(email_provider.httpx, "post", recorder)

    build_email_sender().send(_message())

    assert recorder.calls[0]["json"]["from"] == "notifications@example.com"


# ------------------------------------------------------------------ #
# F. non-2xx response -> EmailSenderError, no key leak
# ------------------------------------------------------------------ #
def test_non_2xx_response_raises_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)
    recorder = _PostRecorder(status_code=422)
    monkeypatch.setattr(email_provider.httpx, "post", recorder)

    sender = build_email_sender()
    with pytest.raises(EmailSenderError) as excinfo:
        sender.send(_message())

    assert "422" in str(excinfo.value)
    assert _KEY not in str(excinfo.value)


# ------------------------------------------------------------------ #
# G. httpx.HTTPError -> EmailSenderError, no key leak
# ------------------------------------------------------------------ #
def test_httpx_error_raises_without_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _enable(monkeypatch)

    def _raise(*args: object, **kwargs: object) -> object:
        raise httpx.HTTPError("connection blew up")

    monkeypatch.setattr(email_provider.httpx, "post", _raise)

    sender = build_email_sender()
    with pytest.raises(EmailSenderError) as excinfo:
        sender.send(_message())

    assert _KEY not in str(excinfo.value)


# ------------------------------------------------------------------ #
# H. secret hygiene -> key never in logs or exception text
# ------------------------------------------------------------------ #
def test_secret_never_logged_or_in_exception(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _enable(monkeypatch)
    recorder = _PostRecorder(status_code=500)
    monkeypatch.setattr(email_provider.httpx, "post", recorder)

    caplog.set_level("DEBUG")
    sender = build_email_sender()
    with pytest.raises(EmailSenderError) as excinfo:
        sender.send(_message())

    assert _KEY not in str(excinfo.value)
    assert _KEY not in caplog.text


# ------------------------------------------------------------------ #
# I. send_business_email uses the factory + preserves normalization
# ------------------------------------------------------------------ #
def test_send_business_email_uses_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services.email_sender import send_business_email

    _enable(monkeypatch)
    recorder = _PostRecorder(status_code=200)
    monkeypatch.setattr(email_provider.httpx, "post", recorder)

    send_business_email(_message())

    assert len(recorder.calls) == 1


def test_send_business_email_normalizes_unexpected_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.services import email_sender as seam

    def _boom() -> object:
        raise RuntimeError("unexpected non-EmailSenderError failure")

    # build_email_sender is imported inside send_business_email, so patch it
    # on the provider module where the function-local import resolves it.
    monkeypatch.setattr(email_provider, "build_email_sender", _boom)

    with pytest.raises(EmailSenderError):
        seam.send_business_email(_message())
