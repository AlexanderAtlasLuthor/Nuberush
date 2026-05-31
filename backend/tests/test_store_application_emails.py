"""Tests for the mock business email layer (F2.24.C8).

Covers the three post-commit notification seams in
`app.services.store_applications`:

  - submit  -> store_application_submitted
  - reject  -> store_application_rejected
  - approve -> store_application_approved

The seams call `send_business_email` (imported into the service module's
namespace). Tests monkeypatch that name to a local recorder so assertions
stay fully offline and deterministic — no real sender, no network.

Three things are asserted across the suite:
  1. A successful submit/approve/reject triggers exactly one email with the
     right event_type and recipient.
  2. A guard/duplicate failure triggers ZERO emails (the seam runs only
     after a successful commit).
  3. A sender failure AFTER commit does not break the response — the
     committed change persists and the API still returns 201/200.

Style mirrors the existing store-application suites (TestClient `client`,
transactional `db_session`, the autouse `supabase_admin_fake`).
"""
from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import StoreApplication
from app.db.models import StoreApplicationStatus
from app.db.models import User
from app.db.models import UserRole
from app.services import store_applications as svc
from app.services.email_sender import BusinessEmailMessage
from app.services.email_sender import EmailSenderError
from tests.helpers.auth import make_supabase_token
from tests.helpers.auth import make_user as central_make_user


_PUBLIC = "/public/store-applications"
_ADMIN = "/admin/store-applications"


# --------------------------------------------------------------------- #
# Local fake sender + fixtures
# --------------------------------------------------------------------- #


class _RecordingSender:
    """Captures every BusinessEmailMessage passed to the seam."""

    def __init__(self) -> None:
        self.sent: list[BusinessEmailMessage] = []

    def __call__(self, message: BusinessEmailMessage) -> None:
        self.sent.append(message)


@pytest.fixture
def sent_emails(monkeypatch: pytest.MonkeyPatch) -> _RecordingSender:
    """Replace the service module's `send_business_email` with a recorder.

    Patching the name in `store_applications` (where it is called) captures
    the exact message the templates built, and keeps the real sender out of
    the test entirely.
    """
    recorder = _RecordingSender()
    monkeypatch.setattr(svc, "send_business_email", recorder)
    return recorder


@pytest.fixture
def raising_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the seam's sender raise EmailSenderError on every call."""

    def _boom(message: BusinessEmailMessage) -> None:
        raise EmailSenderError("simulated mock sender failure")

    monkeypatch.setattr(svc, "send_business_email", _boom)


def _auth(user: User) -> dict[str, str]:
    from app.core.config import get_supabase_auth_settings

    issuer = get_supabase_auth_settings().supabase_jwt_issuer or None
    token = make_supabase_token(sub=user.auth_user_id, issuer=issuer)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_admin(db_session: Session) -> Callable[..., User]:
    def _create() -> User:
        return central_make_user(
            db_session, role=UserRole.admin, store_id=None, full_name="Admin"
        )

    return _create


@pytest.fixture
def make_application(db_session: Session) -> Callable[..., StoreApplication]:
    def _create(
        *,
        status: StoreApplicationStatus = StoreApplicationStatus.pending_review,
        **over,
    ) -> StoreApplication:
        data = dict(
            business_name="Acme Vapes",
            business_type="vape_shop",
            owner_full_name="Jane Owner",
            owner_email=f"jane-{uuid.uuid4().hex[:8]}@example.com",
            owner_phone="+1 555 0100",
            address_line_1="1 Test Way",
            city="Miami",
            state="FL",
            postal_code="33101",
            status=status,
        )
        if status is StoreApplicationStatus.rejected:
            data.setdefault("rejection_reason", "seeded rejection")
        data.update(over)
        application = StoreApplication(**data)
        db_session.add(application)
        db_session.commit()
        db_session.refresh(application)
        return application

    return _create


def _valid_body(**overrides) -> dict:
    body = {
        "business_name": "Acme Vapes",
        "business_type": "vape_shop",
        "owner_full_name": "Jane Owner",
        "owner_email": "jane@example.com",
        "owner_phone": "+1 555 0100",
        "business_phone": "+1 555 0199",
        "address_line_1": "1 Test Way",
        "city": "Miami",
        "state": "FL",
        "postal_code": "33101",
        "country": "US",
        "location_count": 2,
        "estimated_weekly_orders": 150,
        "hours_of_operation": "Mon-Fri 9-5",
        "terms_accepted": True,
    }
    body.update(overrides)
    return body


def _count(db: Session, model) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


# --------------------------------------------------------------------- #
# 1. Submit success triggers store_application_submitted
# --------------------------------------------------------------------- #


def test_submit_success_triggers_submitted_email(
    client: TestClient, sent_emails: _RecordingSender
):
    resp = client.post(
        _PUBLIC, json=_valid_body(owner_email="Jane.Owner@Example.COM")
    )
    assert resp.status_code == 201, resp.text

    assert len(sent_emails.sent) == 1
    msg = sent_emails.sent[0]
    assert msg.event_type == "store_application_submitted"
    # Recipient is the NORMALIZED (lowercased) owner email.
    assert msg.to_email == "jane.owner@example.com"
    assert "received" in msg.subject.lower()


# --------------------------------------------------------------------- #
# 2. Reject success triggers store_application_rejected
# --------------------------------------------------------------------- #


def test_reject_success_triggers_rejected_email(
    client: TestClient,
    db_session: Session,
    make_admin,
    make_application,
    sent_emails: _RecordingSender,
):
    admin = make_admin()
    app_row = make_application()
    resp = client.post(
        f"{_ADMIN}/{app_row.id}/reject",
        json={"rejection_reason": "incomplete license"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200, resp.text

    assert len(sent_emails.sent) == 1
    msg = sent_emails.sent[0]
    assert msg.event_type == "store_application_rejected"
    assert msg.to_email == app_row.owner_email
    # The human-readable reason is surfaced in the generated body.
    assert "incomplete license" in msg.body


# --------------------------------------------------------------------- #
# 3. Approve success triggers store_application_approved
# --------------------------------------------------------------------- #


def test_approve_success_triggers_approved_email(
    client: TestClient,
    make_admin,
    make_application,
    sent_emails: _RecordingSender,
):
    app_row = make_application()
    resp = client.post(
        f"{_ADMIN}/{app_row.id}/approve", headers=_auth(make_admin())
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "approved"

    assert len(sent_emails.sent) == 1
    msg = sent_emails.sent[0]
    assert msg.event_type == "store_application_approved"
    assert msg.to_email == app_row.owner_email


# --------------------------------------------------------------------- #
# 4-6. Guard/failure paths send ZERO emails
# --------------------------------------------------------------------- #


def test_no_email_on_submit_duplicate_conflict(
    client: TestClient, db_session: Session, sent_emails: _RecordingSender
):
    # First submit succeeds (1 email); a second with the same active email
    # is a 409 and must NOT send.
    first = client.post(_PUBLIC, json=_valid_body(owner_email="dup@example.com"))
    assert first.status_code == 201, first.text
    assert len(sent_emails.sent) == 1

    second = client.post(
        _PUBLIC, json=_valid_body(owner_email="dup@example.com")
    )
    assert second.status_code == 409, second.text
    # Still exactly one email — the duplicate sent nothing.
    assert len(sent_emails.sent) == 1


def test_no_email_on_reject_guard_failure(
    client: TestClient, make_admin, make_application, sent_emails: _RecordingSender
):
    # Already-rejected application cannot be rejected again -> 409, no email.
    app_row = make_application(
        status=StoreApplicationStatus.rejected, rejection_reason="prior"
    )
    resp = client.post(
        f"{_ADMIN}/{app_row.id}/reject",
        json={"rejection_reason": "again"},
        headers=_auth(make_admin()),
    )
    assert resp.status_code == 409, resp.text
    assert sent_emails.sent == []

    # And a missing application -> 404, no email.
    resp_missing = client.post(
        f"{_ADMIN}/{uuid.uuid4()}/reject",
        json={"rejection_reason": "x"},
        headers=_auth(make_admin()),
    )
    assert resp_missing.status_code == 404, resp_missing.text
    assert sent_emails.sent == []


def test_no_email_on_approve_guard_failure(
    client: TestClient,
    db_session: Session,
    make_admin,
    make_application,
    sent_emails: _RecordingSender,
):
    # An owner email that already maps to a user blocks approval -> 409.
    app_row = make_application(owner_email="taken@example.com")
    central_make_user(
        db_session,
        role=UserRole.owner,
        email="taken@example.com",
        store_id=None,
    )
    resp = client.post(
        f"{_ADMIN}/{app_row.id}/approve", headers=_auth(make_admin())
    )
    assert resp.status_code == 409, resp.text
    assert sent_emails.sent == []


# --------------------------------------------------------------------- #
# 7-9. Sender failure after commit does NOT break the response
# --------------------------------------------------------------------- #


def test_sender_failure_does_not_break_submit(
    client: TestClient, db_session: Session, raising_sender
):
    resp = client.post(_PUBLIC, json=_valid_body(owner_email="ok@example.com"))
    assert resp.status_code == 201, resp.text

    # The application was still committed despite the sender raising.
    app_row = db_session.scalar(
        select(StoreApplication).where(
            StoreApplication.owner_email == "ok@example.com"
        )
    )
    assert app_row is not None
    assert app_row.status is StoreApplicationStatus.pending_review


def test_sender_failure_does_not_break_reject(
    client: TestClient,
    db_session: Session,
    make_admin,
    make_application,
    raising_sender,
):
    app_row = make_application()
    resp = client.post(
        f"{_ADMIN}/{app_row.id}/reject",
        json={"rejection_reason": "nope"},
        headers=_auth(make_admin()),
    )
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    refreshed = db_session.get(StoreApplication, app_row.id)
    assert refreshed.status is StoreApplicationStatus.rejected


def test_sender_failure_does_not_break_approve(
    client: TestClient,
    db_session: Session,
    make_admin,
    make_application,
    raising_sender,
):
    app_row = make_application()
    resp = client.post(
        f"{_ADMIN}/{app_row.id}/approve", headers=_auth(make_admin())
    )
    assert resp.status_code == 200, resp.text

    db_session.expire_all()
    refreshed = db_session.get(StoreApplication, app_row.id)
    assert refreshed.status is StoreApplicationStatus.approved
    # Provisioning still happened — the sender failure changed nothing.
    assert refreshed.provisioned_store_id is not None
    assert refreshed.provisioned_owner_user_id is not None


# --------------------------------------------------------------------- #
# 10. Boundary / source guard — no provider, no env, no settings
# --------------------------------------------------------------------- #


_FORBIDDEN_TOKENS = (
    "smtp",
    "resend",
    "postmark",
    "sendgrid",
    "mailgun",
    "smtplib",
    "httpx",
    "requests",
    "getenv",
    "environ",
    "basesettings",
    "settingsconfigdict",
)


@pytest.mark.parametrize(
    "module_name",
    ["email_sender", "email_templates"],
)
def test_email_modules_contain_no_provider_or_config(module_name: str):
    import importlib
    import pathlib

    module = importlib.import_module(f"app.services.{module_name}")
    source = pathlib.Path(module.__file__).read_text(encoding="utf-8").lower()
    for token in _FORBIDDEN_TOKENS:
        assert token not in source, (
            f"{module_name}.py must not reference '{token}'"
        )
