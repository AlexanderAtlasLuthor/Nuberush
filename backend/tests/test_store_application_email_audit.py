"""Tests for the post-commit `email_triggered` audit (F2.25.3).

Each business email attempt (submit / approve / reject) writes one
`email_triggered` row into `store_application_audit_logs` in an isolated,
non-blocking transaction. These tests assert the row is written with a
secret- and body-free payload on success, written with `status="failed"`
+ `error_type` on a sender failure (without changing the committed business
state or the HTTP response), and that audit-path failures are swallowed.

All offline: the autouse fixtures strip EMAIL_* env (so the seam is
log-only) and fake the Supabase Admin API. The sender is monkeypatched on
the service module's `send_business_email` name where it is called, exactly
as `test_store_application_emails.py` does.

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
from app.db.models import StoreApplicationAuditLog
from app.db.models import StoreApplicationStatus
from app.db.models import User
from app.db.models import UserRole
from app.services import store_applications as svc
from app.services.email_sender import EmailSenderError
from tests.helpers.auth import make_supabase_token
from tests.helpers.auth import make_user as central_make_user


_PUBLIC = "/public/store-applications"
_ADMIN = "/admin/store-applications"

# A distinctive marker that appears in the rendered email body/secret context
# but must NEVER appear in any audit row.
_SECRET = "re_super_secret_resend_key_value"


# --------------------------------------------------------------------- #
# Fixtures / helpers (mirrors the existing store-application suites)
# --------------------------------------------------------------------- #
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
    def _create(**over) -> StoreApplication:
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
            status=StoreApplicationStatus.pending_review,
        )
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


def _email_audits(db: Session, application_id) -> list[StoreApplicationAuditLog]:
    return db.scalars(
        select(StoreApplicationAuditLog).where(
            StoreApplicationAuditLog.application_id == application_id,
            StoreApplicationAuditLog.event_type == "email_triggered",
        )
    ).all()


def _count_email_audits(db: Session, application_id) -> int:
    return db.scalar(
        select(func.count())
        .select_from(StoreApplicationAuditLog)
        .where(
            StoreApplicationAuditLog.application_id == application_id,
            StoreApplicationAuditLog.event_type == "email_triggered",
        )
    ) or 0


@pytest.fixture
def raising_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the service seam raise EmailSenderError on every send."""

    def _boom(message):
        raise EmailSenderError("simulated provider failure %s" % _SECRET)

    monkeypatch.setattr(svc, "send_business_email", _boom)


@pytest.fixture
def unexpected_sender(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make the service seam raise an unexpected (non-EmailSenderError)."""

    def _boom(message):
        raise RuntimeError("unexpected boom %s" % _SECRET)

    monkeypatch.setattr(svc, "send_business_email", _boom)


# --------------------------------------------------------------------- #
# A. submitted success -> sent audit row
# --------------------------------------------------------------------- #
def test_submitted_success_writes_sent_audit(
    client: TestClient, db_session: Session
) -> None:
    email = f"sub-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(_PUBLIC, json=_valid_body(owner_email=email))
    assert resp.status_code == 201, resp.text

    application = db_session.scalars(
        select(StoreApplication).where(StoreApplication.owner_email == email)
    ).one()

    rows = _email_audits(db_session, application.id)
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["event"] == "store_application_submitted"
    assert payload["provider"] == "resend"
    assert payload["status"] == "sent"
    assert payload["provider_message_id"] is None
    assert payload["source"] == "business_email"
    assert payload["recipient"] == email
    assert "error_type" not in payload
    assert rows[0].actor_user_id is None


# --------------------------------------------------------------------- #
# B. approved success -> sent audit row
# --------------------------------------------------------------------- #
def test_approved_success_writes_sent_audit(
    client: TestClient, db_session: Session, make_admin, make_application
) -> None:
    admin = make_admin()
    app_row = make_application(owner_email="approve-ok@acme.test")

    resp = client.post(f"{_ADMIN}/{app_row.id}/approve", headers=_auth(admin))
    assert resp.status_code == 200, resp.text

    rows = _email_audits(db_session, app_row.id)
    assert len(rows) == 1
    assert rows[0].payload["event"] == "store_application_approved"
    assert rows[0].payload["status"] == "sent"


# --------------------------------------------------------------------- #
# C. rejected success -> sent audit row
# --------------------------------------------------------------------- #
def test_rejected_success_writes_sent_audit(
    client: TestClient, db_session: Session, make_admin, make_application
) -> None:
    admin = make_admin()
    app_row = make_application(owner_email="reject-ok@acme.test")

    resp = client.post(
        f"{_ADMIN}/{app_row.id}/reject",
        headers=_auth(admin),
        json={"rejection_reason": "incomplete license"},
    )
    assert resp.status_code == 200, resp.text

    rows = _email_audits(db_session, app_row.id)
    assert len(rows) == 1
    assert rows[0].payload["event"] == "store_application_rejected"
    assert rows[0].payload["status"] == "sent"


# --------------------------------------------------------------------- #
# D. provider EmailSenderError -> failed audit row, response preserved
# --------------------------------------------------------------------- #
def test_provider_failure_writes_failed_audit_and_preserves_response(
    client: TestClient,
    db_session: Session,
    raising_sender: None,
) -> None:
    email = f"fail-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(_PUBLIC, json=_valid_body(owner_email=email))
    # Committed application still returns 201 despite the sender failure.
    assert resp.status_code == 201, resp.text

    application = db_session.scalars(
        select(StoreApplication).where(StoreApplication.owner_email == email)
    ).one()
    assert application.status is StoreApplicationStatus.pending_review

    rows = _email_audits(db_session, application.id)
    assert len(rows) == 1
    assert rows[0].payload["status"] == "failed"
    assert rows[0].payload["error_type"] == "EmailSenderError"


# --------------------------------------------------------------------- #
# E. unexpected provider error -> failed audit row with the class name
# --------------------------------------------------------------------- #
def test_unexpected_failure_writes_failed_audit_without_message(
    client: TestClient,
    db_session: Session,
    unexpected_sender: None,
) -> None:
    email = f"boom-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(_PUBLIC, json=_valid_body(owner_email=email))
    assert resp.status_code == 201, resp.text

    application = db_session.scalars(
        select(StoreApplication).where(StoreApplication.owner_email == email)
    ).one()

    rows = _email_audits(db_session, application.id)
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["status"] == "failed"
    assert payload["error_type"] == "RuntimeError"
    # The exception MESSAGE (and its secret) must not leak into the payload.
    assert _SECRET not in str(payload)
    assert "unexpected boom" not in str(payload)


# --------------------------------------------------------------------- #
# F. audit write failure is swallowed; response + business state preserved
# --------------------------------------------------------------------- #
def test_audit_write_failure_is_swallowed(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(*args, **kwargs):
        raise RuntimeError("audit write blew up")

    monkeypatch.setattr(svc, "_write_email_triggered_audit", _boom)

    email = f"auditfail-{uuid.uuid4().hex[:8]}@example.com"
    resp = client.post(_PUBLIC, json=_valid_body(owner_email=email))
    # The committed application still returns 201.
    assert resp.status_code == 201, resp.text

    application = db_session.scalars(
        select(StoreApplication).where(StoreApplication.owner_email == email)
    ).one()
    assert application.status is StoreApplicationStatus.pending_review
    # The helper was fully bypassed, so no email_triggered row exists.
    assert _count_email_audits(db_session, application.id) == 0


# --------------------------------------------------------------------- #
# G. guard / duplicate path -> no email_triggered audit
# --------------------------------------------------------------------- #
def test_duplicate_submission_writes_no_email_audit(
    client: TestClient, db_session: Session
) -> None:
    email = f"dup-{uuid.uuid4().hex[:8]}@example.com"
    first = client.post(_PUBLIC, json=_valid_body(owner_email=email))
    assert first.status_code == 201, first.text

    application = db_session.scalars(
        select(StoreApplication).where(StoreApplication.owner_email == email)
    ).one()
    audits_after_first = _count_email_audits(db_session, application.id)

    # A second active submission for the same email is rejected with 409 and
    # must trigger no email and therefore no email_triggered audit row.
    dup = client.post(_PUBLIC, json=_valid_body(owner_email=email))
    assert dup.status_code == 409, dup.text

    assert _count_email_audits(db_session, application.id) == audits_after_first


# --------------------------------------------------------------------- #
# H. payload hygiene -> no body/subject/secret in any audit row
# --------------------------------------------------------------------- #
def test_audit_payload_hygiene_success_and_failure(
    client: TestClient,
    db_session: Session,
    make_admin,
    make_application,
) -> None:
    # One successful row (approve).
    admin = make_admin()
    ok_row = make_application(owner_email="hygiene-ok@acme.test")
    resp = client.post(f"{_ADMIN}/{ok_row.id}/approve", headers=_auth(admin))
    assert resp.status_code == 200, resp.text
    sent = _email_audits(db_session, ok_row.id)[0]

    forbidden = (
        "RESEND_API_KEY",
        "Authorization",
        "Bearer",
        _SECRET,
        "Hi ",  # email body greeting
        "— The NubeRush Team",  # email body signoff
    )
    for blob in (str(sent.payload), sent.message or ""):
        for token in forbidden:
            assert token not in blob
    assert "subject" not in sent.payload
    assert "body" not in sent.payload
    assert "message_body" not in sent.payload
