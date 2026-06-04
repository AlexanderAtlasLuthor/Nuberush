"""Tests for the notification email foundation (F2.25.7).

A minimal, callable, fully-offline foundation:

  - three pure template builders -> NotificationEmailMessage
  - send_notification_email dispatch through the existing EmailSender seam

Style mirrors the existing email suites (`test_email_provider.py`,
`test_store_application_emails.py`): no network, no DB, no real provider
config. The disabled-by-default sender (`_LoggingEmailSender`) is what runs
unless a test opts in, and the `explode_post` fixture proves no network is
touched.
"""
from __future__ import annotations

import pathlib

import pytest

from app.services import email_provider
from app.services import notification_emails
from app.services.email_sender import EmailSenderError
from app.services.email_sender import NotificationEmailMessage
from app.services.notification_email_templates import (
    build_low_stock_digest_email,
)
from app.services.notification_email_templates import (
    build_onboarding_reminder_email,
)
from app.services.notification_email_templates import (
    build_operations_alert_digest_email,
)


# Tokens/secrets/auth-routes that must NEVER appear in a notification body.
_FORBIDDEN_BODY_TOKENS = (
    "password",
    "access_token",
    "refresh_token",
    "service_role",
    "SERVICE_ROLE",
    "token_urlsafe",
    "/auth/callback",
    "/auth/set-password",
    "/auth/forgot-password",
)


class _RecordingSender:
    """Captures every message passed to the seam; optionally raises."""

    def __init__(self, raises: BaseException | None = None) -> None:
        self.raises = raises
        self.sent: list[NotificationEmailMessage] = []

    def send(self, message: NotificationEmailMessage) -> None:
        self.sent.append(message)
        if self.raises is not None:
            raise self.raises


@pytest.fixture
def explode_post(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail loudly if any code path calls httpx.post (proves no network)."""

    def _boom(*args: object, **kwargs: object) -> object:
        raise AssertionError("httpx.post must not be called in this path")

    monkeypatch.setattr(email_provider.httpx, "post", _boom)


# --------------------------------------------------------------------- #
# A. low stock template
# --------------------------------------------------------------------- #
def test_low_stock_template() -> None:
    msg = build_low_stock_digest_email(
        to_email="owner@example.com",
        store_name="Acme Vapes",
        low_stock_item_count=7,
        inventory_url="https://app.example.com/app/store/inventory",
    )

    assert isinstance(msg, NotificationEmailMessage)
    assert msg.event_type == "store_low_stock_digest_requested"
    assert msg.to_email == "owner@example.com"
    assert msg.subject.strip() != ""
    assert "Acme Vapes" in msg.body
    assert "7" in msg.body
    assert "https://app.example.com/app/store/inventory" in msg.body


# --------------------------------------------------------------------- #
# B. operations alert template
# --------------------------------------------------------------------- #
def test_operations_alert_template() -> None:
    msg = build_operations_alert_digest_email(
        to_email="admin@example.com",
        alert_count=4,
        operations_url="https://app.example.com/app/admin/operations",
    )

    assert isinstance(msg, NotificationEmailMessage)
    assert msg.event_type == "admin_operations_alert_digest_requested"
    assert msg.to_email == "admin@example.com"
    assert msg.subject.strip() != ""
    assert "4" in msg.body
    assert "https://app.example.com/app/admin/operations" in msg.body


# --------------------------------------------------------------------- #
# C. onboarding reminder template
# --------------------------------------------------------------------- #
def test_onboarding_reminder_template() -> None:
    msg = build_onboarding_reminder_email(
        to_email="owner@example.com",
        store_name="Acme Vapes",
        onboarding_url="https://app.example.com/app/store/onboarding",
    )

    assert isinstance(msg, NotificationEmailMessage)
    assert msg.event_type == "store_onboarding_reminder_requested"
    assert msg.to_email == "owner@example.com"
    assert msg.subject.strip() != ""
    assert "Acme Vapes" in msg.body
    assert "https://app.example.com/app/store/onboarding" in msg.body


# --------------------------------------------------------------------- #
# D. template hygiene -> no tokens / secrets / auth routes in any body
# --------------------------------------------------------------------- #
def test_template_bodies_have_no_tokens_or_auth_routes() -> None:
    messages = [
        build_low_stock_digest_email(
            to_email="owner@example.com",
            store_name="Acme Vapes",
            low_stock_item_count=3,
            inventory_url="https://app.example.com/app/store/inventory",
        ),
        build_operations_alert_digest_email(
            to_email="admin@example.com",
            alert_count=2,
            operations_url="https://app.example.com/app/admin/operations",
        ),
        build_onboarding_reminder_email(
            to_email="owner@example.com",
            store_name="Acme Vapes",
            onboarding_url="https://app.example.com/app/store/onboarding",
        ),
    ]
    for msg in messages:
        for token in _FORBIDDEN_BODY_TOKENS:
            assert token not in msg.body, (
                f"{msg.event_type} body must not contain {token!r}"
            )


# --------------------------------------------------------------------- #
# E. send_notification_email dispatches the exact message through the seam
# --------------------------------------------------------------------- #
def test_send_dispatches_through_sender(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _RecordingSender()
    monkeypatch.setattr(
        notification_emails, "build_email_sender", lambda: recorder
    )

    msg = build_low_stock_digest_email(
        to_email="owner@example.com",
        store_name="Acme Vapes",
        low_stock_item_count=1,
        inventory_url="https://app.example.com/app/store/inventory",
    )
    notification_emails.send_notification_email(msg)

    assert recorder.sent == [msg]


# --------------------------------------------------------------------- #
# F. EmailSenderError passes through unchanged
# --------------------------------------------------------------------- #
def test_email_sender_error_passes_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorder = _RecordingSender(raises=EmailSenderError("boom"))
    monkeypatch.setattr(
        notification_emails, "build_email_sender", lambda: recorder
    )

    msg = build_operations_alert_digest_email(
        to_email="admin@example.com",
        alert_count=1,
        operations_url="https://app.example.com/app/admin/operations",
    )
    with pytest.raises(EmailSenderError) as excinfo:
        notification_emails.send_notification_email(msg)

    assert str(excinfo.value) == "boom"


# --------------------------------------------------------------------- #
# G. unexpected exception normalizes to a secret-free EmailSenderError
# --------------------------------------------------------------------- #
def test_unexpected_error_normalizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "re_super_secret_value"
    recorder = _RecordingSender(raises=RuntimeError(secret))
    monkeypatch.setattr(
        notification_emails, "build_email_sender", lambda: recorder
    )

    msg = build_onboarding_reminder_email(
        to_email="owner@example.com",
        store_name="Acme Vapes",
        onboarding_url="https://app.example.com/app/store/onboarding",
    )
    with pytest.raises(EmailSenderError) as excinfo:
        notification_emails.send_notification_email(msg)

    # Generic, event-named message — the underlying secret must not leak.
    assert "store_onboarding_reminder_requested" in str(excinfo.value)
    assert secret not in str(excinfo.value)


# --------------------------------------------------------------------- #
# H. default (disabled) sender completes with no network
# --------------------------------------------------------------------- #
def test_default_disabled_sender_no_network(explode_post: None) -> None:
    # EMAIL_* env is stripped by the autouse isolation fixture, so
    # build_email_sender() resolves to _LoggingEmailSender (no real config).
    from app.core.config import get_email_settings

    get_email_settings.cache_clear()

    msg = build_low_stock_digest_email(
        to_email="owner@example.com",
        store_name="Acme Vapes",
        low_stock_item_count=5,
        inventory_url="https://app.example.com/app/store/inventory",
    )
    # Must complete via the logging sender without raising or hitting httpx.
    notification_emails.send_notification_email(msg)


# --------------------------------------------------------------------- #
# I. template module boundary -> no provider/config tokens in source
# --------------------------------------------------------------------- #
def test_template_module_contains_no_provider_or_config() -> None:
    import app.services.notification_email_templates as templates_mod

    source = pathlib.Path(templates_mod.__file__).read_text(
        encoding="utf-8"
    ).lower()
    for token in (
        "getenv",
        "environ",
        "basesettings",
        "settingsconfigdict",
        "httpx",
        "resend",
        "smtp",
        "requests",
    ):
        assert token not in source, (
            f"notification_email_templates.py must not reference {token!r}"
        )
