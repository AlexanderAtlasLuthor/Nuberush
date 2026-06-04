"""Branded plain-text templates for notification emails (F2.25.7).

Pure functions that turn primitive, caller-supplied values into a
`NotificationEmailMessage`. No I/O, no DB access, no config/env reads, no
provider details, no secrets. Each builder is total: given its parameters
it returns a complete, send-ready message.

These are NOTIFICATION emails — operational digests and reminders — kept
deliberately separate from the store-application business emails in
`app.services.email_templates`. The link a message points at is always
passed in by the caller (composed from `APP_PUBLIC_BASE_URL` upstream) so
these builders stay pure: no config access, no env reads, no secrets.

Content rules (enforced by the copy below and the F2.25.7 tests):

  - Every message is branded as NubeRush and signed by the team.
  - Each carries the caller-provided in-app link verbatim and nothing more —
    no auth token, password, recovery/callback URL, or provider detail.
  - The copy summarizes counts/names only; it never embeds IDs or secrets.
"""

from __future__ import annotations

from app.services.email_sender import NotificationEmailMessage


_BRAND = "NubeRush"
_SIGNOFF = f"— The {_BRAND} Team"


def build_low_stock_digest_email(
    *,
    to_email: str,
    store_name: str,
    low_stock_item_count: int,
    inventory_url: str,
) -> NotificationEmailMessage:
    """`store_low_stock_digest_requested` — low-stock summary for a store.

    Points the recipient at their in-app inventory view. Tokenless: the
    `inventory_url` is the only link and is supplied by the caller.
    """
    body = (
        f"Hi,\n\n"
        f"Here's a quick inventory check for \"{store_name}\" on {_BRAND}.\n\n"
        f"{low_stock_item_count} item(s) are at or below their reorder "
        "threshold and may need restocking soon.\n\n"
        f"Review and restock here:\n{inventory_url}\n\n"
        f"{_SIGNOFF}"
    )
    return NotificationEmailMessage(
        event_type="store_low_stock_digest_requested",
        to_email=to_email,
        subject=f"Low stock alert for {store_name}",
        body=body,
    )


def build_operations_alert_digest_email(
    *,
    to_email: str,
    alert_count: int,
    operations_url: str,
) -> NotificationEmailMessage:
    """`admin_operations_alert_digest_requested` — ops alert summary.

    Points an admin recipient at the in-app operations alerts view.
    Tokenless: the `operations_url` is the only link and is caller-supplied.
    """
    body = (
        f"Hi,\n\n"
        f"There are {alert_count} open operational alert(s) that need "
        f"attention on {_BRAND}.\n\n"
        f"Review the operations dashboard here:\n{operations_url}\n\n"
        f"{_SIGNOFF}"
    )
    return NotificationEmailMessage(
        event_type="admin_operations_alert_digest_requested",
        to_email=to_email,
        subject=f"{alert_count} operational alert(s) need attention",
        body=body,
    )


def build_onboarding_reminder_email(
    *,
    to_email: str,
    store_name: str,
    onboarding_url: str,
) -> NotificationEmailMessage:
    """`store_onboarding_reminder_requested` — nudge to finish setup.

    Reminds an owner to complete their store setup and points at the in-app
    onboarding checklist. Tokenless: the `onboarding_url` is the only link
    and is supplied by the caller (it must NOT carry an auth token).
    """
    body = (
        f"Hi,\n\n"
        f"Your {_BRAND} store \"{store_name}\" still has some setup steps "
        "left. Finishing them gets you ready to take orders.\n\n"
        f"Pick up where you left off here:\n{onboarding_url}\n\n"
        f"{_SIGNOFF}"
    )
    return NotificationEmailMessage(
        event_type="store_onboarding_reminder_requested",
        to_email=to_email,
        subject=f"Finish setting up your {_BRAND} store",
        body=body,
    )
