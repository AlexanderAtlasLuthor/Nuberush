"""Tests for the store-onboarding business email (F2.25.6).

After an admin approves a store application, FastAPI sends a tokenless
onboarding business email linking to the in-app `/app/store/onboarding`
landing page — but only when `APP_PUBLIC_BASE_URL` is configured. It rides
the existing `send_business_email` + `email_triggered` audit path, so a
failure is swallowed and never rolls back the committed approval.

All offline: the autouse fixtures fake the Supabase Admin API and keep the
email seam log-only; `send_business_email` is monkeypatched on the service
module where it is called, as in `test_store_application_emails.py`.
"""
from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Store
from app.db.models import StoreApplication
from app.db.models import StoreApplicationAuditLog
from app.db.models import StoreApplicationStatus
from app.db.models import User
from app.db.models import UserRole
from app.services import store_applications as svc
from app.services.email_sender import BusinessEmailMessage
from app.services.email_sender import EmailSenderError
from tests.helpers.auth import make_supabase_token
from tests.helpers.auth import make_user as central_make_user


_ADMIN = "/admin/store-applications"
_BASE = "http://localhost:5173"


# --------------------------------------------------------------------- #
# Fixtures / helpers (mirror test_owner_activation.py)
# --------------------------------------------------------------------- #
def _set_base_url(monkeypatch: pytest.MonkeyPatch, url: str) -> None:
    from app.core.config import get_app_settings

    monkeypatch.setenv("APP_PUBLIC_BASE_URL", url)
    get_app_settings.cache_clear()


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
            owner_email=f"owner-{uuid.uuid4().hex[:8]}@example.com",
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


@pytest.fixture
def captured_emails(monkeypatch: pytest.MonkeyPatch) -> list[BusinessEmailMessage]:
    """Record every BusinessEmailMessage the service sends (log-only)."""
    sent: list[BusinessEmailMessage] = []
    monkeypatch.setattr(svc, "send_business_email", lambda msg: sent.append(msg))
    return sent


def _onboarding(sent: list[BusinessEmailMessage]) -> list[BusinessEmailMessage]:
    return [m for m in sent if m.event_type == "store_onboarding"]


def _onboarding_audits(
    db: Session, application_id
) -> list[StoreApplicationAuditLog]:
    rows = db.scalars(
        select(StoreApplicationAuditLog).where(
            StoreApplicationAuditLog.application_id == application_id,
            StoreApplicationAuditLog.event_type == "email_triggered",
        )
    ).all()
    return [r for r in rows if (r.payload or {}).get("event") == "store_onboarding"]


def _assert_committed(db: Session, app_id) -> None:
    app_row = db.get(StoreApplication, app_id)
    assert app_row is not None
    assert app_row.status is StoreApplicationStatus.approved
    owner = db.scalar(
        select(User).where(User.email == app_row.owner_email)
    )
    assert owner is not None and owner.role is UserRole.owner
    assert db.scalar(select(Store).where(Store.id == owner.store_id)) is not None


# --------------------------------------------------------------------- #
# A. configured base URL -> onboarding email sent with the in-app link
# --------------------------------------------------------------------- #
def test_approve_sends_onboarding_email_when_configured(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    make_admin,
    make_application,
    captured_emails,
) -> None:
    _set_base_url(monkeypatch, _BASE)
    admin = make_admin()
    app_row = make_application(owner_email="onboard@acme.test")

    resp = client.post(f"{_ADMIN}/{app_row.id}/approve", headers=_auth(admin))
    assert resp.status_code == 200, resp.text

    msgs = _onboarding(captured_emails)
    assert len(msgs) == 1
    assert msgs[0].event_type == "store_onboarding"
    assert msgs[0].to_email == "onboard@acme.test"
    assert f"{_BASE}/app/store/onboarding" in msgs[0].body
    _assert_committed(db_session, app_row.id)


# --------------------------------------------------------------------- #
# B. blank base URL -> onboarding email skipped, approval committed
# --------------------------------------------------------------------- #
def test_blank_base_url_skips_onboarding_email(
    client: TestClient,
    db_session: Session,
    make_admin,
    make_application,
    captured_emails,
) -> None:
    # APP_PUBLIC_BASE_URL is stripped by the autouse isolation fixture.
    admin = make_admin()
    app_row = make_application(owner_email="noonboard@acme.test")

    resp = client.post(f"{_ADMIN}/{app_row.id}/approve", headers=_auth(admin))
    assert resp.status_code == 200, resp.text

    assert _onboarding(captured_emails) == []
    _assert_committed(db_session, app_row.id)


# --------------------------------------------------------------------- #
# C. onboarding email failure does not roll back approval; failed audit
# --------------------------------------------------------------------- #
def test_onboarding_failure_does_not_rollback_and_audits_failed(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    make_admin,
    make_application,
) -> None:
    _set_base_url(monkeypatch, _BASE)

    # Fail only the onboarding send; let the approved email succeed.
    def _maybe_boom(message: BusinessEmailMessage) -> None:
        if message.event_type == "store_onboarding":
            raise EmailSenderError("simulated onboarding send failure")

    monkeypatch.setattr(svc, "send_business_email", _maybe_boom)

    admin = make_admin()
    app_row = make_application(owner_email="failonboard@acme.test")

    resp = client.post(f"{_ADMIN}/{app_row.id}/approve", headers=_auth(admin))
    assert resp.status_code == 200, resp.text
    _assert_committed(db_session, app_row.id)

    rows = _onboarding_audits(db_session, app_row.id)
    assert len(rows) == 1
    assert rows[0].payload["status"] == "failed"
    assert rows[0].payload["error_type"] == "EmailSenderError"


# --------------------------------------------------------------------- #
# D. onboarding email writes a sent email_triggered audit row
# --------------------------------------------------------------------- #
def test_onboarding_writes_sent_audit(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    make_admin,
    make_application,
) -> None:
    _set_base_url(monkeypatch, _BASE)
    admin = make_admin()
    app_row = make_application(owner_email="sentonboard@acme.test")

    resp = client.post(f"{_ADMIN}/{app_row.id}/approve", headers=_auth(admin))
    assert resp.status_code == 200, resp.text

    rows = _onboarding_audits(db_session, app_row.id)
    assert len(rows) == 1
    payload = rows[0].payload
    assert payload["event"] == "store_onboarding"
    assert payload["status"] == "sent"
    assert payload["source"] == "business_email"


# --------------------------------------------------------------------- #
# E. guard path (non-existent application) -> no onboarding email
# --------------------------------------------------------------------- #
def test_guard_path_sends_no_onboarding_email(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    make_admin,
    captured_emails,
) -> None:
    _set_base_url(monkeypatch, _BASE)
    admin = make_admin()

    resp = client.post(f"{_ADMIN}/{uuid.uuid4()}/approve", headers=_auth(admin))
    assert resp.status_code == 404, resp.text
    assert _onboarding(captured_emails) == []


# --------------------------------------------------------------------- #
# F. onboarding body carries no token / secret / auth-route
# --------------------------------------------------------------------- #
def test_onboarding_body_security_hygiene(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    make_admin,
    make_application,
    captured_emails,
) -> None:
    _set_base_url(monkeypatch, _BASE)
    admin = make_admin()
    app_row = make_application(owner_email="clean@acme.test")

    resp = client.post(f"{_ADMIN}/{app_row.id}/approve", headers=_auth(admin))
    assert resp.status_code == 200, resp.text

    body = _onboarding(captured_emails)[0].body
    for token in (
        "access_token",
        "refresh_token",
        "service_role",
        "SERVICE_ROLE",
        "password",
        "token_urlsafe",
        "/auth/callback",
        "/auth/set-password",
        "/auth/forgot-password",
    ):
        assert token not in body
