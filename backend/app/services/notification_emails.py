"""Dispatch for notification emails (F2.25.7).

A thin, callable foundation that sends a `NotificationEmailMessage` through
the SAME transport seam as business emails (`build_email_sender`), while
staying conceptually separate from the store-application business-email
path: it never calls `send_business_email` and never writes an audit row
(notification emails have no `store_application_id`, so the existing
`store_application_audit_logs` table cannot host them, and F2.25.7 adds no
notification table).

Scope is deliberately minimal — this module is callable + tested only:
no scheduler, no background task, no cron, no queue, no retry/dead-letter,
no automatic digest, and no route triggers it. A future subphase decides
WHEN to call it and how to handle failures; this layer just sends.

Failure posture mirrors `send_business_email`: `EmailSenderError` passes
through unchanged, and any other transport error is normalized to a
secret-free `EmailSenderError`. Unlike the business post-commit seams,
this function does NOT swallow — the future caller owns that decision.
"""

from __future__ import annotations

# `notification_emails` is a leaf module: `email_provider` imports from
# `email_sender` only, so importing the factory at top level here creates no
# import cycle (unlike `email_sender.send_business_email`, which must defer
# its import). A module-level binding also lets tests monkeypatch
# `notification_emails.build_email_sender` directly.
from app.services.email_provider import build_email_sender
from app.services.email_sender import EmailSenderError
from app.services.email_sender import NotificationEmailMessage


def send_notification_email(message: NotificationEmailMessage) -> None:
    """Send a notification email through the configured sender.

    Resolves the concrete sender per call via `build_email_sender`
    (F2.25.2): with email delivery disabled or unconfigured it is the
    log-only `_LoggingEmailSender` (no network), and with delivery enabled
    and configured it is the real transport. The seam stays
    provider-agnostic — the concrete transport and its config live only in
    the provider module.

    Any `EmailSenderError` is re-raised as-is; any other transport failure
    is normalized to a secret-free `EmailSenderError`. The caller is
    responsible for deciding whether to swallow it.
    """
    try:
        sender = build_email_sender()
        sender.send(message)
    except EmailSenderError:
        # Already the right type — let the caller handle it.
        raise
    except Exception as exc:  # noqa: BLE001 — normalize any transport error
        raise EmailSenderError(
            f"Failed to send notification email '{message.event_type}'."
        ) from exc
