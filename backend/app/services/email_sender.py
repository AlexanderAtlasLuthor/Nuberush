"""Mock/log business email sender layer (F2.24.C8).

A deliberately minimal, transport-free seam for the three business-event
emails NubeRush sends around the store-application lifecycle:

  - store_application_submitted
  - store_application_approved
  - store_application_rejected

C8 ships ONLY a logging implementation. No real delivery transport is wired:
no mail-protocol client, no third-party delivery service, no API key, no
runtime configuration reads, and no network call. The abstraction exists so
a future subphase can swap `_LoggingEmailSender` for a real transport
without touching the call sites in `app.services.store_applications`.

Account/auth emails (invite, password reset, verification, magic link)
remain Supabase Auth's responsibility and are intentionally NOT modeled
here — this layer carries business-event notifications only.

PII posture: the recipient address is logged (it is the email's destination
and already appears in audit/log context elsewhere), but phone numbers,
postal addresses, tokens, internal IDs, and full payload dumps are never
logged.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal
from typing import Protocol


logger = logging.getLogger(__name__)


# The closed set of business email events C8 knows how to send. Using a
# Literal (not an open str) means a typo at a call site is a type error and
# the template/sender dispatch stays exhaustive.
BusinessEmailEvent = Literal[
    "store_application_submitted",
    "store_application_approved",
    "store_application_rejected",
]


class EmailSenderError(Exception):
    """Raised when sending a business email fails.

    Mirrors `SupabaseAdminError`: the message is deliberately coarse and
    secret-free. Callers in `store_applications` catch this (and any other
    exception) AFTER the DB commit and must never re-raise — a committed
    submit/approve/reject still returns its success response.
    """


@dataclass(frozen=True)
class BusinessEmailMessage:
    """An immutable, transport-agnostic business email.

    Built by `app.services.email_templates` from a `StoreApplication`-like
    object and handed to `send_business_email`. Carries only what any
    transport needs; no internal IDs, tokens, or provider details.
    """

    event_type: BusinessEmailEvent
    to_email: str
    subject: str
    body: str


class EmailSender(Protocol):
    """The seam a future real-provider transport will implement."""

    def send(self, message: BusinessEmailMessage) -> None: ...


class _LoggingEmailSender:
    """The only C8 implementation: log that a mock email was triggered.

    No network, no provider, no secrets. Logs the event type and recipient
    (the destination) at INFO; the subject is included as it is non-PII
    branded boilerplate. The body — which may restate applicant-provided
    context — is intentionally NOT logged to avoid an accidental PII sink.
    """

    def send(self, message: BusinessEmailMessage) -> None:
        logger.info(
            "Mock business email triggered: event=%s to=%s subject=%r",
            message.event_type,
            message.to_email,
            message.subject,
        )


def send_business_email(message: BusinessEmailMessage) -> None:
    """Send a business email through the configured sender.

    The single entry point `store_applications` calls from its post-commit
    notification seams. The concrete sender is resolved per call by
    `build_email_sender` (F2.25.2): with email delivery disabled or
    unconfigured it is `_LoggingEmailSender` (the log-only behavior); with
    delivery enabled and configured it is the real transport. The seam
    stays provider-agnostic — the concrete transport and its config live
    only in the separate provider module. Any transport failure surfaces
    as `EmailSenderError`; the caller is responsible for swallowing it so a
    committed DB change is never undone by a notification problem.
    """
    # Imported inside the function so the provider module (which imports
    # names from this module) does not create an import cycle at load time.
    from app.services.email_provider import build_email_sender

    try:
        sender = build_email_sender()
        sender.send(message)
    except EmailSenderError:
        # Already the right type — let the caller's handler log + swallow.
        raise
    except Exception as exc:  # noqa: BLE001 — normalize any transport error
        raise EmailSenderError(
            f"Failed to send business email '{message.event_type}'."
        ) from exc
