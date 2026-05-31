"""Tests for the F2.24.C5 admin-domain guard.

Only emails whose domain is EXACTLY `nuberush.com` (case-insensitive, no
subdomains, no lookalikes) may ever hold the admin role. Covers the pure
helper plus the active production chokepoint — admin promotion via
`change_user_role` (`assert_can_change_user_role`) — and confirms the
F2.24 paths (public intake, approval) can never mint an admin.
"""
from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.permissions import ensure_admin_email_allowed
from app.core.permissions import is_nuberush_admin_email
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.users import UserRoleChangeRequest
from app.services.users import change_user_role
from tests.helpers.auth import make_user as central_make_user


# --------------------------------------------------------------------- #
# Helper — is_nuberush_admin_email / ensure_admin_email_allowed
# --------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "email",
    [
        "person@nuberush.com",
        "PERSON@NUBERUSH.COM",
        "  Mixed.Case@NubeRush.Com  ",
    ],
)
def test_helper_allows_official_domain(email: str):
    assert is_nuberush_admin_email(email) is True
    # ensure_* does not raise for allowed addresses.
    ensure_admin_email_allowed(email)


@pytest.mark.parametrize(
    "email",
    [
        "admin@gmail.com",
        "admin@nuberush.co",
        "admin@nuberush.com.fake",
        "admin@sub.nuberush.com",
        "admin@nuberush.comm",
        "admin@evilnuberush.com",
        "no-at-sign.com",
        "a@b@nuberush.com",
        "@nuberush.com",
        "",
        "   ",
    ],
)
def test_helper_rejects_disallowed_or_malformed(email: str):
    assert is_nuberush_admin_email(email) is False
    with pytest.raises(HTTPException) as exc:
        ensure_admin_email_allowed(email)
    assert exc.value.status_code == 403
    assert "nuberush.com" in exc.value.detail


# --------------------------------------------------------------------- #
# Active promotion path — change_user_role
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create() -> Store:
        store = Store(name="S", code=f"s-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


def _promote_to_admin(db: Session, target: User, actor: User) -> User:
    return change_user_role(
        db,
        target.id,
        UserRoleChangeRequest(role=UserRole.admin),
        actor=actor,
    )


def test_promote_to_admin_allowed_for_nuberush_email(
    db_session: Session, make_store
):
    admin = central_make_user(db_session, role=UserRole.admin, store_id=None)
    target = central_make_user(
        db_session,
        role=UserRole.manager,
        store_id=make_store().id,
        email="newadmin@nuberush.com",
    )
    promoted = _promote_to_admin(db_session, target, admin)
    assert promoted.role is UserRole.admin
    assert promoted.store_id is None  # cross-field invariant


@pytest.mark.parametrize(
    "email",
    [
        "ext@gmail.com",
        "ext@nuberush.co",
        "ext@nuberush.com.fake",
        "ext@sub.nuberush.com",
        "ext@nuberush.comm",
        "ext@evilnuberush.com",
    ],
)
def test_promote_to_admin_blocked_for_non_nuberush_email(
    db_session: Session, make_store, email: str
):
    admin = central_make_user(db_session, role=UserRole.admin, store_id=None)
    target = central_make_user(
        db_session,
        role=UserRole.manager,
        store_id=make_store().id,
        email=email,
    )
    with pytest.raises(HTTPException) as exc:
        _promote_to_admin(db_session, target, admin)
    assert exc.value.status_code == 403
    assert "nuberush.com" in exc.value.detail

    db_session.expire_all()
    # Role unchanged — the promotion did not persist.
    assert (
        db_session.get(User, target.id).role is UserRole.manager
    )


def test_non_admin_cannot_promote_to_admin_even_with_official_email(
    db_session: Session, make_store
):
    store = make_store()
    owner = central_make_user(
        db_session, role=UserRole.owner, store_id=store.id
    )
    target = central_make_user(
        db_session,
        role=UserRole.staff,
        store_id=store.id,
        email="wouldbe@nuberush.com",
    )
    # Owner can't assign admin at all — the role-matrix 403 fires before the
    # domain check, so the guard is never a bypass for non-admins.
    with pytest.raises(HTTPException) as exc:
        _promote_to_admin(db_session, target, owner)
    assert exc.value.status_code == 403


# --------------------------------------------------------------------- #
# Admin CREATION path remains structurally blocked (matrix), email aside
# --------------------------------------------------------------------- #


def test_create_user_admin_role_is_blocked_by_matrix(
    client: TestClient, db_session: Session
):
    # POST /auth/users can never create an admin (USER_CREATION_MATRIX), so
    # even a @nuberush.com admin payload is rejected — admin self/seed
    # creation is not an API path. (Unauthenticated here → 401/403; the key
    # assertion is that it never succeeds.)
    resp = client.post(
        "/auth/users",
        json={
            "full_name": "Would Be Admin",
            "email": "boss@nuberush.com",
            "password": "supersecret123",
            "role": "admin",
        },
    )
    assert resp.status_code in (401, 403), resp.text
    # No admin row created.
    from sqlalchemy import func
    from sqlalchemy import select

    assert (
        db_session.scalar(
            select(func.count())
            .select_from(User)
            .where(User.email == "boss@nuberush.com")
        )
        == 0
    )


# --------------------------------------------------------------------- #
# F2.24 regression — no path mints an admin
# --------------------------------------------------------------------- #


def test_public_intake_cannot_set_admin_role(client: TestClient):
    # The submit schema is extra="forbid"; a smuggled role is a 422.
    resp = client.post(
        "/public/store-applications",
        json={
            "business_name": "Acme",
            "business_type": "vape_shop",
            "owner_full_name": "Jane",
            "owner_email": "jane@example.com",
            "owner_phone": "+1 555 0100",
            "business_phone": "+1 555 0199",
            "address_line_1": "1 Way",
            "city": "Miami",
            "state": "FL",
            "postal_code": "33101",
            "country": "US",
            "location_count": 1,
            "estimated_weekly_orders": 5,
            "hours_of_operation": "9-5",
            "terms_accepted": True,
            "role": "admin",
        },
    )
    assert resp.status_code == 422, resp.text


def test_approval_provisions_owner_never_admin(
    db_session: Session, make_store
):
    # Approval hardcodes UserRole.owner; an application owner email under
    # @nuberush.com still becomes an OWNER, not an admin.
    from app.db.models import StoreApplication
    from app.db.models import StoreApplicationStatus
    from app.services.store_applications import approve_store_application

    admin = central_make_user(db_session, role=UserRole.admin, store_id=None)
    application = StoreApplication(
        business_name="Acme Vapes",
        business_type="vape_shop",
        owner_full_name="Olive Owner",
        owner_email="owner@nuberush.com",  # official domain, still owner
        owner_phone="+1 555 0100",
        address_line_1="1 Test Way",
        city="Miami",
        state="FL",
        postal_code="33101",
        status=StoreApplicationStatus.pending_review,
    )
    db_session.add(application)
    db_session.commit()
    db_session.refresh(application)

    approved = approve_store_application(
        db_session, application.id, actor=admin
    )
    owner = db_session.get(User, approved.provisioned_owner_user_id)
    assert owner.role is UserRole.owner  # never admin
