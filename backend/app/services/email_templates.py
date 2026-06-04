"""Branded plain-text templates for business emails (F2.24.C8).

Pure functions that turn a `StoreApplication`-like object into a
`BusinessEmailMessage`. No I/O, no DB access, no provider details, no
secrets. Each builder is total: given an application it returns a complete,
send-ready message.

Content rules (enforced by the copy below and the C8 tests):

  - Every message is branded as NubeRush and signed by the team.
  - submitted: thanks the applicant, states pending review, and is explicit
    that submitting does NOT grant immediate access.
  - approved: states approval and points at the official account-activation
    flow as the next step. It never claims the owner can log in immediately
    (account access is a separate, later flow) and never leaks a temporary
    password, auth token, or Supabase/internal detail.
  - rejected: states the application was reviewed and not approved at this
    time, includes the rejection reason when present, and stays professional
    without internal policy/debug detail.

Nothing here reads internal IDs, provisioning links, tokens, phone numbers,
or addresses — only the applicant's name, business name, and (for rejection)
the human-readable reason.
"""

from __future__ import annotations

from typing import Protocol

from app.services.email_sender import BusinessEmailMessage


_BRAND = "NubeRush"
_SIGNOFF = f"— The {_BRAND} Team"


class _ApplicationLike(Protocol):
    """The minimal surface the templates read off a StoreApplication.

    Declared structurally so the builders stay decoupled from the ORM model
    and remain trivially testable with a lightweight stand-in.
    """

    owner_full_name: str
    owner_email: str
    business_name: str
    rejection_reason: str | None


def _greeting(application: _ApplicationLike) -> str:
    name = (application.owner_full_name or "").strip() or "there"
    return f"Hi {name},"


def build_submitted_email(application: _ApplicationLike) -> BusinessEmailMessage:
    """`store_application_submitted` — receipt + pending-review notice."""
    body = (
        f"{_greeting(application)}\n\n"
        f"Thank you for applying to {_BRAND} with "
        f"\"{application.business_name}\". We've received your store "
        "application and it is now pending review.\n\n"
        "Submitting this application does not grant immediate access to "
        f"{_BRAND}. Our team will review the business information you "
        "provided and follow up with the next steps.\n\n"
        "You don't need to do anything further right now.\n\n"
        f"{_SIGNOFF}"
    )
    return BusinessEmailMessage(
        event_type="store_application_submitted",
        to_email=application.owner_email,
        subject=f"Your {_BRAND} store application was received",
        body=body,
    )


def build_approved_email(application: _ApplicationLike) -> BusinessEmailMessage:
    """`store_application_approved` — approval + activation next step."""
    body = (
        f"{_greeting(application)}\n\n"
        f"Good news — your {_BRAND} store application for "
        f"\"{application.business_name}\" has been approved.\n\n"
        "The next step is to set up your account access through the "
        f"official {_BRAND} account activation flow. Please watch for a "
        "separate message guiding you through activation; you'll choose "
        "your own credentials there.\n\n"
        f"{_SIGNOFF}"
    )
    return BusinessEmailMessage(
        event_type="store_application_approved",
        to_email=application.owner_email,
        subject=f"Your {_BRAND} store application was approved",
        body=body,
    )


def build_rejected_email(application: _ApplicationLike) -> BusinessEmailMessage:
    """`store_application_rejected` — professional not-approved notice."""
    reason = (application.rejection_reason or "").strip()
    reason_block = (
        f"Reason: {reason}\n\n" if reason else ""
    )
    body = (
        f"{_greeting(application)}\n\n"
        f"Thank you for your interest in {_BRAND}. We've reviewed your "
        f"store application for \"{application.business_name}\", and it "
        "was not approved at this time.\n\n"
        f"{reason_block}"
        "If your circumstances change, you're welcome to apply again in "
        "the future.\n\n"
        f"{_SIGNOFF}"
    )
    return BusinessEmailMessage(
        event_type="store_application_rejected",
        to_email=application.owner_email,
        subject=f"Your {_BRAND} store application was not approved",
        body=body,
    )


def build_onboarding_email(
    application: _ApplicationLike, *, onboarding_url: str
) -> BusinessEmailMessage:
    """`store_onboarding` — welcome + setup checklist (F2.25.6).

    A tokenless business email. The onboarding link is passed in by the
    caller (composed from APP_PUBLIC_BASE_URL) so this builder stays pure —
    no config/env access, no secrets. It carries NO auth token, password,
    or Supabase recovery link; it only points the owner at the in-app
    onboarding landing page where the setup steps live.
    """
    body = (
        f"{_greeting(application)}\n\n"
        f"Welcome to {_BRAND}! Your store \"{application.business_name}\" "
        "is approved and ready to set up.\n\n"
        "Get started with these steps:\n"
        "  - Complete your store profile\n"
        "  - Add your first products\n"
        "  - Set your inventory thresholds\n"
        "  - Review your orders dashboard\n"
        "  - Contact NubeRush support if you need a hand\n\n"
        f"Open your getting-started checklist here:\n{onboarding_url}\n\n"
        f"{_SIGNOFF}"
    )
    return BusinessEmailMessage(
        event_type="store_onboarding",
        to_email=application.owner_email,
        subject=f"Start setting up your {_BRAND} store",
        body=body,
    )
