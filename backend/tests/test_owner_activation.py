"""Tests for the post-commit owner-activation trigger (F2.25.4 backend).

After an admin approves a store application, FastAPI asks Supabase Auth to
email the (already-created) owner a set-password/recovery link back to the
frontend `/auth/callback`. Supabase owns the token and sends the email;
FastAPI never sees a token and never sends a plaintext password.

These tests prove the trigger fires post-commit when `APP_PUBLIC_BASE_URL`
is configured, is skipped safely when blank, never rolls back a committed
approval on failure, is not attempted on guard paths, builds the correct
redirect, and leaks no secret/token/password.

All offline: the autouse `supabase_admin_fake` records the (email,
redirect_to) call without any network; the autouse `_isolate_settings_env`
fixture strips APP_PUBLIC_BASE_URL between tests.
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
from app.db.models import StoreApplicationStatus
from app.db.models import User
from app.db.models import UserRole
from app.services import store_applications as svc
from tests.helpers.auth import make_supabase_token
from tests.helpers.auth import make_user as central_make_user


_ADMIN = "/admin/store-applications"


# --------------------------------------------------------------------- #
# Fixtures / helpers (mirrors the existing store-application suites)
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


def _assert_committed_approval(db: Session, app_id) -> StoreApplication:
    app_row = db.get(StoreApplication, app_id)
    assert app_row is not None
    assert app_row.status is StoreApplicationStatus.approved
    # Owner was provisioned and committed, linked to a provisioned store.
    owner = db.scalar(
        select(User).where(User.email == app_row.owner_email)
    )
    assert owner is not None and owner.role is UserRole.owner
    assert owner.store_id is not None
    assert db.scalar(
        select(Store).where(Store.id == owner.store_id)
    ) is not None
    return app_row


# --------------------------------------------------------------------- #
# A. configured base URL -> activation email triggered
# --------------------------------------------------------------------- #
def test_approve_triggers_activation_email_when_configured(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    make_admin,
    make_application,
    supabase_admin_fake,
) -> None:
    _set_base_url(monkeypatch, "http://localhost:5173")
    admin = make_admin()
    app_row = make_application(owner_email="activate@acme.test")

    resp = client.post(f"{_ADMIN}/{app_row.id}/approve", headers=_auth(admin))
    assert resp.status_code == 200, resp.text

    assert len(supabase_admin_fake.password_setup_emails) == 1
    call = supabase_admin_fake.password_setup_emails[0]
    assert call["email"] == "activate@acme.test"
    assert call["redirect_to"] == "http://localhost:5173/auth/callback"

    _assert_committed_approval(db_session, app_row.id)


# --------------------------------------------------------------------- #
# B. blank base URL -> trigger skipped, approval still committed
# --------------------------------------------------------------------- #
def test_blank_base_url_skips_activation(
    client: TestClient,
    db_session: Session,
    make_admin,
    make_application,
    supabase_admin_fake,
) -> None:
    # APP_PUBLIC_BASE_URL is stripped by the autouse isolation fixture.
    admin = make_admin()
    app_row = make_application(owner_email="noskip@acme.test")

    resp = client.post(f"{_ADMIN}/{app_row.id}/approve", headers=_auth(admin))
    assert resp.status_code == 200, resp.text

    assert supabase_admin_fake.password_setup_emails == []
    _assert_committed_approval(db_session, app_row.id)


# --------------------------------------------------------------------- #
# C. activation email failure does not roll back the committed approval
# --------------------------------------------------------------------- #
def test_activation_failure_does_not_rollback_approval(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
    make_admin,
    make_application,
    supabase_admin_fake,
) -> None:
    _set_base_url(monkeypatch, "http://localhost:5173")
    supabase_admin_fake.password_setup_should_fail = True

    admin = make_admin()
    app_row = make_application(owner_email="failmail@acme.test")

    resp = client.post(f"{_ADMIN}/{app_row.id}/approve", headers=_auth(admin))
    # Swallowed: the committed approval still returns 200.
    assert resp.status_code == 200, resp.text

    # The failing call recorded nothing, but provisioning is committed.
    assert supabase_admin_fake.password_setup_emails == []
    _assert_committed_approval(db_session, app_row.id)


# --------------------------------------------------------------------- #
# D. guard path (non-existent application) -> no activation attempted
# --------------------------------------------------------------------- #
def test_guard_path_does_not_trigger_activation(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    make_admin,
    supabase_admin_fake,
) -> None:
    _set_base_url(monkeypatch, "http://localhost:5173")
    admin = make_admin()

    resp = client.post(
        f"{_ADMIN}/{uuid.uuid4()}/approve", headers=_auth(admin)
    )
    assert resp.status_code == 404, resp.text
    assert supabase_admin_fake.password_setup_emails == []


# --------------------------------------------------------------------- #
# E. redirect URL strips a trailing slash on the base
# --------------------------------------------------------------------- #
def test_base_url_trailing_slash_is_stripped(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    make_admin,
    make_application,
    supabase_admin_fake,
) -> None:
    _set_base_url(monkeypatch, "http://localhost:5173/")
    admin = make_admin()
    app_row = make_application(owner_email="trailing@acme.test")

    resp = client.post(f"{_ADMIN}/{app_row.id}/approve", headers=_auth(admin))
    assert resp.status_code == 200, resp.text

    call = supabase_admin_fake.password_setup_emails[0]
    assert call["redirect_to"] == "http://localhost:5173/auth/callback"


# --------------------------------------------------------------------- #
# F. no plaintext password / token leakage in the recorded call or logs
# --------------------------------------------------------------------- #
def test_no_password_or_token_in_activation_call_or_logs(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    make_admin,
    make_application,
    supabase_admin_fake,
    caplog: pytest.LogCaptureFixture,
) -> None:
    _set_base_url(monkeypatch, "http://localhost:5173")
    admin = make_admin()
    app_row = make_application(owner_email="hygiene@acme.test")

    caplog.set_level("DEBUG")
    resp = client.post(f"{_ADMIN}/{app_row.id}/approve", headers=_auth(admin))
    assert resp.status_code == 200, resp.text

    call = supabase_admin_fake.password_setup_emails[0]
    # The recorded call carries ONLY email + redirect_to.
    assert set(call.keys()) == {"email", "redirect_to"}

    forbidden = (
        "password",
        "access_token",
        "refresh_token",
        "service_role",
        "Bearer ",
        "token_urlsafe",
    )
    blob = str(call) + caplog.text
    for token in forbidden:
        assert token not in blob


# --------------------------------------------------------------------- #
# G. the approval business email body carries no auth token / secret
# --------------------------------------------------------------------- #
def test_business_email_body_has_no_auth_token(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    make_admin,
    make_application,
) -> None:
    _set_base_url(monkeypatch, "http://localhost:5173")

    sent: list = []
    real_send = svc.send_business_email
    monkeypatch.setattr(
        svc, "send_business_email", lambda msg: sent.append(msg) or real_send(msg)
    )

    admin = make_admin()
    app_row = make_application(owner_email="bizmail@acme.test")
    resp = client.post(f"{_ADMIN}/{app_row.id}/approve", headers=_auth(admin))
    assert resp.status_code == 200, resp.text

    approved = [m for m in sent if m.event_type == "store_application_approved"]
    assert len(approved) == 1
    body = approved[0].body + approved[0].subject
    for token in (
        "access_token",
        "refresh_token",
        "/auth/callback",
        "service_role",
        "?redirect_to=",
    ):
        assert token not in body
