"""Real business-email transport via Resend (F2.25.2).

This module is the real-provider implementation behind the protected
`email_sender` seam. It is deliberately small: a single `EmailSender`
implementation (`ResendEmailSender`) plus a `build_email_sender` factory
that decides, from `get_email_settings()`, whether the real transport or
the log-only fallback applies.

Design rules (mirror `app.services.supabase_admin`):

  - The factory reads config at CALL TIME, never at import time, so the
    test suite (which clears the settings cache per test) stays
    deterministic and `EMAIL_ENABLED` flips take effect immediately.
  - Delivery is OFF unless fully configured: disabled, a non-Resend
    provider, a blank API key, or a blank from-address all fall back to
    `_LoggingEmailSender`. Local/dev/test therefore stay log-only/offline
    by default (EMAIL_ENABLED defaults False).
  - The RESEND_API_KEY is a SERVER-ONLY SECRET: it is never logged, never
    placed in an exception message, and the full Authorization header,
    response body, and message body are never logged either. Error
    messages carry at most the provider name and an HTTP status code.

Scope: business emails only. No `email_triggered` audit (F2.25.3), no
auth/activation emails (F2.25.4/.5), no notification foundation (F2.25.7),
no html, no queue/retry/dead-letter.
"""

from __future__ import annotations

import httpx

from app.core.config import get_email_settings
from app.services.email_sender import BusinessEmailMessage
from app.services.email_sender import EmailSender
from app.services.email_sender import EmailSenderError
from app.services.email_sender import _LoggingEmailSender


_RESEND_ENDPOINT = "https://api.resend.com/emails"
_REQUEST_TIMEOUT_SECONDS = 10.0
_PROVIDER_RESEND = "resend"


def _format_from(from_address: str, from_name: str) -> str:
    """Build the Resend `from` field.

    With a display name: `NubeRush <sender@example.com>`. Without one: the
    bare address. Both inputs are assumed already-stripped by the caller.
    """
    if from_name:
        return f"{from_name} <{from_address}>"
    return from_address


class ResendEmailSender:
    """Send `BusinessEmailMessage`s via the Resend REST API.

    Structurally implements the `EmailSender` Protocol. Reads config at
    `send` time so a sender instance carries no captured secret. Raises
    `EmailSenderError` (secret-free) on any transport error or non-2xx
    response; the post-commit call sites swallow it.
    """

    def send(self, message: BusinessEmailMessage) -> None:
        settings = get_email_settings()
        api_key = settings.resend_api_key.strip()
        from_address = settings.email_from_address.strip()
        from_name = settings.email_from_name.strip()

        payload = {
            "from": _format_from(from_address, from_name),
            "to": [message.to_email],
            "subject": message.subject,
            "text": message.body,
        }
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        try:
            response = httpx.post(
                _RESEND_ENDPOINT,
                headers=headers,
                json=payload,
                timeout=_REQUEST_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as exc:
            # Bare message: never echo the key, header, URL with query, or
            # any provider response detail.
            raise EmailSenderError(
                "Resend request failed while sending a business email"
            ) from exc

        if response.status_code not in (200, 201):
            # Status code only — never the response body (it may restate the
            # payload) and never the key.
            raise EmailSenderError(
                "Resend returned status "
                f"{response.status_code} while sending a business email"
            )


def build_email_sender() -> EmailSender:
    """Resolve the active sender from email-delivery config (call time).

    Returns the real `ResendEmailSender` only when delivery is fully
    configured; otherwise returns `_LoggingEmailSender` so nothing is sent
    and no network call is attempted. This is the swap point the C8
    `email_sender` docstring anticipated.
    """
    settings = get_email_settings()

    if not settings.email_enabled:
        return _LoggingEmailSender()
    if settings.email_provider.strip().lower() != _PROVIDER_RESEND:
        return _LoggingEmailSender()
    if not settings.resend_api_key.strip():
        return _LoggingEmailSender()
    if not settings.email_from_address.strip():
        return _LoggingEmailSender()

    return ResendEmailSender()
