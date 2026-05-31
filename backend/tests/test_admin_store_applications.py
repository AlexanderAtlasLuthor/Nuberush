"""Tests for the admin store-application review API (F2.24.C3).

Covers GET list / GET detail / POST approve / POST reject under the
`require_admin` guard, plus the C3 scope boundary: reject is a full
status transition; approve is admin-protected but BLOCKED (501) until C4
provisioning exists, and never mutates the row or fabricates a
store/user/auth record.

Auth note: `_auth` mints the Supabase test token with the `iss` claim set
to whatever issuer the verifier is configured with (real value when a
local .env is present, empty/None in CI). This keeps the authed tests
deterministic in both environments rather than tripping the
`MissingRequiredClaimError('iss')` path that the bare `auth_headers_for`
helper hits when an issuer is configured.
"""
from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Store
from app.db.models import StoreApplication
from app.db.models import StoreApplicationAuditLog
from app.db.models import StoreApplicationStatus
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import make_supabase_token
from tests.helpers.auth import make_user as central_make_user


_LIST = "/admin/store-applications"


def _auth(user: User) -> dict[str, str]:
    from app.core.config import get_supabase_auth_settings

    issuer = get_supabase_auth_settings().supabase_jwt_issuer or None
    token = make_supabase_token(sub=user.auth_user_id, issuer=issuer)
    return {"Authorization": f"Bearer {token}"}


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_admin(db_session: Session) -> Callable[..., User]:
    def _create() -> User:
        return central_make_user(
            db_session, role=UserRole.admin, store_id=None, full_name="Admin"
        )

    return _create


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create() -> Store:
        store = Store(name="S", code=f"s-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

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


# --------------------------------------------------------------------- #
# List / detail
# --------------------------------------------------------------------- #


def test_admin_can_list_applications(
    client: TestClient, make_admin, make_application
):
    make_application()
    make_application()
    resp = client.get(_LIST, headers=_auth(make_admin()))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 2
    assert len(body["items"]) == 2


def test_list_supports_status_filter(
    client: TestClient, make_admin, make_application
):
    make_application(status=StoreApplicationStatus.pending_review)
    make_application(
        status=StoreApplicationStatus.rejected,
        rejection_reason="nope",
    )
    resp = client.get(
        _LIST, params={"status": "rejected"}, headers=_auth(make_admin())
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["status"] == "rejected"


def test_list_supports_pagination(
    client: TestClient, make_admin, make_application
):
    for _ in range(3):
        make_application()
    resp = client.get(
        _LIST, params={"limit": 2, "offset": 0}, headers=_auth(make_admin())
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 3
    assert len(body["items"]) == 2
    assert body["limit"] == 2


def test_list_returns_safe_list_fields(
    client: TestClient, make_admin, make_application
):
    make_application()
    resp = client.get(_LIST, headers=_auth(make_admin()))
    item = resp.json()["items"][0]
    assert set(item.keys()) == {
        "id",
        "business_name",
        "business_type",
        "owner_full_name",
        "owner_email",
        "status",
        "location_count",
        "estimated_weekly_orders",
        "city",
        "state",
        "submitted_at",
        "reviewed_at",
        "created_at",
    }
    # No sensitive/internal-only fields leaked in the list projection.
    assert "public_lookup_token" not in item
    assert "provisioned_store_id" not in item


def test_admin_can_fetch_detail(
    client: TestClient, make_admin, make_application
):
    app_row = make_application()
    resp = client.get(
        f"{_LIST}/{app_row.id}", headers=_auth(make_admin())
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(app_row.id)
    assert body["business_name"] == "Acme Vapes"
    assert body["owner_phone"] == "+1 555 0100"
    assert "audit_logs" in body


def test_detail_includes_audit_logs(
    client: TestClient, db_session: Session, make_admin, make_application
):
    app_row = make_application()
    db_session.add(
        StoreApplicationAuditLog(
            application_id=app_row.id,
            event_type="application_created",
            payload={"source": "public_intake"},
        )
    )
    db_session.commit()
    resp = client.get(f"{_LIST}/{app_row.id}", headers=_auth(make_admin()))
    assert resp.status_code == 200, resp.text
    logs = resp.json()["audit_logs"]
    assert len(logs) == 1
    assert logs[0]["event_type"] == "application_created"


def test_detail_audit_logs_ordered_chronologically(
    client: TestClient, db_session: Session, make_admin, make_application
):
    from datetime import UTC
    from datetime import datetime
    from datetime import timedelta

    app_row = make_application()
    base = datetime(2026, 5, 1, 12, 0, 0, tzinfo=UTC)
    # Insert OUT of chronological order: the later event is added first.
    db_session.add(
        StoreApplicationAuditLog(
            application_id=app_row.id,
            event_type="application_rejected",
            created_at=base + timedelta(hours=1),
        )
    )
    db_session.add(
        StoreApplicationAuditLog(
            application_id=app_row.id,
            event_type="application_created",
            created_at=base,
        )
    )
    db_session.commit()

    resp = client.get(f"{_LIST}/{app_row.id}", headers=_auth(make_admin()))
    assert resp.status_code == 200, resp.text
    events = [log["event_type"] for log in resp.json()["audit_logs"]]
    # Deterministic chronological order regardless of insertion order.
    assert events == ["application_created", "application_rejected"]


def test_detail_missing_returns_404(client: TestClient, make_admin):
    resp = client.get(f"{_LIST}/{uuid.uuid4()}", headers=_auth(make_admin()))
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------- #
# Permissions
# --------------------------------------------------------------------- #


def _endpoints(app_id) -> list[tuple[str, str, dict]]:
    return [
        ("get", _LIST, {}),
        ("get", f"{_LIST}/{app_id}", {}),
        ("post", f"{_LIST}/{app_id}/approve", {}),
        ("post", f"{_LIST}/{app_id}/reject", {"json": {"rejection_reason": "x"}}),
    ]


@pytest.mark.parametrize("method, path, kw", _endpoints(uuid.uuid4()))
def test_unauthenticated_is_rejected(
    client: TestClient, method: str, path: str, kw: dict
):
    resp = getattr(client, method)(path, **kw)
    assert resp.status_code == 401, resp.text


@pytest.mark.parametrize(
    "role", [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver]
)
@pytest.mark.parametrize("method, path, kw", _endpoints(uuid.uuid4()))
def test_non_admin_is_forbidden(
    client: TestClient,
    db_session: Session,
    make_store,
    role: UserRole,
    method: str,
    path: str,
    kw: dict,
):
    store = make_store()
    sid = None if role == UserRole.admin else store.id
    user = central_make_user(db_session, role=role, store_id=sid)
    resp = getattr(client, method)(path, headers=_auth(user), **kw)
    assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------- #
# Reject
# --------------------------------------------------------------------- #


def test_admin_can_reject_pending_application(
    client: TestClient, db_session: Session, make_admin, make_application
):
    admin = make_admin()
    app_row = make_application()
    resp = client.post(
        f"{_LIST}/{app_row.id}/reject",
        json={"rejection_reason": "  incomplete license  "},
        headers=_auth(admin),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "rejected"
    assert body["rejection_reason"] == "incomplete license"  # trimmed

    db_session.expire_all()
    refreshed = db_session.get(StoreApplication, app_row.id)
    assert refreshed.status is StoreApplicationStatus.rejected
    assert refreshed.rejection_reason == "incomplete license"
    assert refreshed.reviewed_by_user_id == admin.id
    assert refreshed.reviewed_at is not None


def test_reject_requires_non_blank_reason(
    client: TestClient, make_admin, make_application
):
    app_row = make_application()
    for bad in ({"rejection_reason": ""}, {"rejection_reason": "   "}, {}):
        resp = client.post(
            f"{_LIST}/{app_row.id}/reject",
            json=bad,
            headers=_auth(make_admin()),
        )
        assert resp.status_code == 422, resp.text


def test_reject_writes_application_rejected_audit(
    client: TestClient, db_session: Session, make_admin, make_application
):
    admin = make_admin()
    app_row = make_application()
    resp = client.post(
        f"{_LIST}/{app_row.id}/reject",
        json={"rejection_reason": "spam"},
        headers=_auth(admin),
    )
    assert resp.status_code == 200, resp.text
    logs = db_session.scalars(
        select(StoreApplicationAuditLog).where(
            StoreApplicationAuditLog.application_id == app_row.id,
            StoreApplicationAuditLog.event_type == "application_rejected",
        )
    ).all()
    assert len(logs) == 1
    assert logs[0].actor_user_id == admin.id


def test_reject_creates_no_store_user_or_auth(
    client: TestClient,
    db_session: Session,
    make_admin,
    make_application,
    supabase_admin_fake,
):
    stores_before = db_session.scalar(select(func.count()).select_from(Store))
    users_before = db_session.scalar(select(func.count()).select_from(User))
    app_row = make_application()
    resp = client.post(
        f"{_LIST}/{app_row.id}/reject",
        json={"rejection_reason": "x"},
        headers=_auth(make_admin()),
    )
    assert resp.status_code == 200, resp.text
    assert (
        db_session.scalar(select(func.count()).select_from(Store))
        == stores_before
    )
    # make_admin + nothing else; no NEW user beyond the admin.
    assert (
        db_session.scalar(select(func.count()).select_from(User))
        == users_before + 1
    )
    assert supabase_admin_fake.created == []


@pytest.mark.parametrize(
    "status",
    [
        StoreApplicationStatus.draft,
        StoreApplicationStatus.submitted,
        StoreApplicationStatus.rejected,
    ],
)
def test_reject_rejects_non_pending_application(
    client: TestClient, make_admin, make_application, status
):
    app_row = make_application(status=status)
    resp = client.post(
        f"{_LIST}/{app_row.id}/reject",
        json={"rejection_reason": "x"},
        headers=_auth(make_admin()),
    )
    assert resp.status_code == 409, resp.text


def test_reject_missing_returns_404(client: TestClient, make_admin):
    resp = client.post(
        f"{_LIST}/{uuid.uuid4()}/reject",
        json={"rejection_reason": "x"},
        headers=_auth(make_admin()),
    )
    assert resp.status_code == 404, resp.text


# --------------------------------------------------------------------- #
# Approve — atomic provisioning (C4)
# --------------------------------------------------------------------- #


def test_admin_can_approve_pending_application(
    client: TestClient, db_session: Session, make_admin, make_application
):
    admin = make_admin()
    app_row = make_application(owner_email="owner@acme.test")
    resp = client.post(f"{_LIST}/{app_row.id}/approve", headers=_auth(admin))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "approved"
    assert body["reviewed_by_user_id"] == str(admin.id)
    assert body["provisioned_store_id"] is not None
    assert body["provisioned_owner_user_id"] is not None

    db_session.expire_all()
    refreshed = db_session.get(StoreApplication, app_row.id)
    assert refreshed.status is StoreApplicationStatus.approved
    assert refreshed.reviewed_by_user_id == admin.id
    assert refreshed.reviewed_at is not None
    assert refreshed.provisioned_store_id is not None
    assert refreshed.provisioned_owner_user_id is not None
    assert refreshed.rejection_reason is None


def test_approve_provisions_one_store_and_owner_linked(
    client: TestClient,
    db_session: Session,
    make_admin,
    make_application,
    supabase_admin_fake,
):
    stores_before = db_session.scalar(select(func.count()).select_from(Store))
    users_before = db_session.scalar(select(func.count()).select_from(User))

    app_row = make_application(
        owner_email="owner2@acme.test", owner_full_name="Olive Owner"
    )
    resp = client.post(f"{_LIST}/{app_row.id}/approve", headers=_auth(make_admin()))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Exactly one new store and one new owner user.
    assert (
        db_session.scalar(select(func.count()).select_from(Store))
        == stores_before + 1
    )
    # +1 admin (make_admin) +1 owner = +2 users.
    assert (
        db_session.scalar(select(func.count()).select_from(User))
        == users_before + 2
    )

    store = db_session.get(Store, uuid.UUID(body["provisioned_store_id"]))
    owner = db_session.get(User, uuid.UUID(body["provisioned_owner_user_id"]))
    assert store is not None and store.name == "Acme Vapes"
    assert owner is not None
    assert owner.role is UserRole.owner  # role hardcoded, never injected
    assert owner.store_id == store.id
    assert owner.email == "owner2@acme.test"  # normalized
    assert owner.auth_user_id is not None

    # Exactly one Supabase Auth user created, for the owner email.
    assert len(supabase_admin_fake.created) == 1
    assert supabase_admin_fake.created[0]["email"] == "owner2@acme.test"
    assert supabase_admin_fake.deleted == []


def test_approve_writes_three_audit_logs_in_order(
    client: TestClient, db_session: Session, make_admin, make_application
):
    admin = make_admin()
    app_row = make_application(owner_email="owner3@acme.test")
    resp = client.post(f"{_LIST}/{app_row.id}/approve", headers=_auth(admin))
    assert resp.status_code == 200, resp.text

    logs = db_session.scalars(
        select(StoreApplicationAuditLog)
        .where(StoreApplicationAuditLog.application_id == app_row.id)
        .order_by(
            StoreApplicationAuditLog.created_at,
            StoreApplicationAuditLog.id,
        )
    ).all()
    assert [log.event_type for log in logs] == [
        "store_provisioned",
        "owner_provisioned",
        "application_approved",
    ]
    assert all(log.actor_user_id == admin.id for log in logs)


def test_approve_response_exposes_only_safe_fields(
    client: TestClient, make_admin, make_application
):
    app_row = make_application(owner_email="owner4@acme.test")
    resp = client.post(f"{_LIST}/{app_row.id}/approve", headers=_auth(make_admin()))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == {
        "id",
        "status",
        "reviewed_by_user_id",
        "reviewed_at",
        "provisioned_store_id",
        "provisioned_owner_user_id",
        "rejection_reason",
        "message",
    }
    assert "public_lookup_token" not in body
    assert "password" not in body


def test_approve_rejects_existing_owner_email_account(
    client: TestClient,
    db_session: Session,
    make_admin,
    make_application,
    make_store,
    supabase_admin_fake,
):
    # An existing user already owns this email.
    store = make_store()
    central_make_user(
        db_session,
        role=UserRole.owner,
        store_id=store.id,
        email="taken@acme.test",
    )
    app_row = make_application(owner_email="taken@acme.test")
    stores_before = db_session.scalar(select(func.count()).select_from(Store))

    resp = client.post(f"{_LIST}/{app_row.id}/approve", headers=_auth(make_admin()))
    assert resp.status_code == 409, resp.text
    # No store provisioned, no auth user created, application still pending.
    assert (
        db_session.scalar(select(func.count()).select_from(Store))
        == stores_before
    )
    assert supabase_admin_fake.created == []
    db_session.expire_all()
    assert (
        db_session.get(StoreApplication, app_row.id).status
        is StoreApplicationStatus.pending_review
    )


def test_double_approval_second_is_conflict_no_duplicates(
    client: TestClient,
    db_session: Session,
    make_admin,
    make_application,
    supabase_admin_fake,
):
    admin = make_admin()
    app_row = make_application(owner_email="dup-owner@acme.test")
    first = client.post(f"{_LIST}/{app_row.id}/approve", headers=_auth(admin))
    assert first.status_code == 200, first.text

    # Second approval: the application is now `approved`, not pending → 409.
    second = client.post(f"{_LIST}/{app_row.id}/approve", headers=_auth(admin))
    assert second.status_code == 409, second.text

    # No duplicate store / owner / auth user.
    owners = db_session.scalars(
        select(User).where(User.email == "dup-owner@acme.test")
    ).all()
    assert len(owners) == 1
    assert len(supabase_admin_fake.created) == 1


def test_approve_supabase_failure_rolls_back_everything(
    client: TestClient,
    db_session: Session,
    make_admin,
    make_application,
    supabase_admin_fake,
):
    supabase_admin_fake.create_should_fail = True
    stores_before = db_session.scalar(select(func.count()).select_from(Store))
    app_row = make_application(owner_email="fail@acme.test")

    resp = client.post(f"{_LIST}/{app_row.id}/approve", headers=_auth(make_admin()))
    assert resp.status_code == 502, resp.text

    db_session.expire_all()
    # Application untouched; no store committed; no orphan auth cleanup needed.
    assert (
        db_session.get(StoreApplication, app_row.id).status
        is StoreApplicationStatus.pending_review
    )
    assert (
        db_session.scalar(select(func.count()).select_from(Store))
        == stores_before
    )
    # No success audit logs.
    assert (
        db_session.scalar(
            select(func.count())
            .select_from(StoreApplicationAuditLog)
            .where(StoreApplicationAuditLog.application_id == app_row.id)
        )
        == 0
    )


def test_approve_db_failure_after_auth_cleans_up_auth_user(
    client: TestClient,
    db_session: Session,
    make_admin,
    make_application,
    supabase_admin_fake,
):
    # Pin the auth id the fake will return, then pre-seed a DIFFERENT-email
    # user already holding that auth_user_id. The owner insert then violates
    # the unique auth_user_id index AFTER the auth user is created, forcing
    # the post-auth rollback + cleanup path.
    pinned = uuid.uuid4()
    supabase_admin_fake.next_auth_user_id = pinned
    central_make_user(
        db_session,
        role=UserRole.admin,
        store_id=None,
        email="other@acme.test",
        auth_user_id=pinned,
    )
    app_row = make_application(owner_email="collide@acme.test")
    stores_before = db_session.scalar(select(func.count()).select_from(Store))

    resp = client.post(f"{_LIST}/{app_row.id}/approve", headers=_auth(make_admin()))
    assert resp.status_code == 409, resp.text

    db_session.expire_all()
    # Application not approved; no store committed; orphaned auth user deleted.
    assert (
        db_session.get(StoreApplication, app_row.id).status
        is StoreApplicationStatus.pending_review
    )
    assert (
        db_session.scalar(select(func.count()).select_from(Store))
        == stores_before
    )
    assert supabase_admin_fake.deleted == [pinned]


def test_approve_non_integrity_db_failure_cleans_up_auth_user(
    client: TestClient,
    db_session: Session,
    make_admin,
    make_application,
    supabase_admin_fake,
    monkeypatch,
):
    # A non-IntegrityError DB failure (e.g. deadlock / OperationalError) AFTER
    # the auth user is created must still roll back and delete the orphaned
    # auth.users row — never a raw 500 with a dangling identity.
    from sqlalchemy.exc import OperationalError

    admin = make_admin()
    app_row = make_application(owner_email="op-fail@acme.test")

    def boom():
        raise OperationalError("simulated deadlock", None, Exception("deadlock"))

    monkeypatch.setattr(db_session, "commit", boom)
    resp = client.post(f"{_LIST}/{app_row.id}/approve", headers=_auth(admin))
    assert resp.status_code == 500, resp.text
    # The auth user was created, then cleaned up.
    assert len(supabase_admin_fake.created) == 1
    assert supabase_admin_fake.deleted == [supabase_admin_fake.created[0]["id"]]


def test_approve_long_business_name_is_truncated_not_500(
    client: TestClient, db_session: Session, make_admin, make_application
):
    # business_name up to 200 chars is valid on the application, but
    # Store.name is VARCHAR(150) — approval must truncate, not 500.
    long_name = "V" * 200
    app_row = make_application(
        owner_email="longname@acme.test", business_name=long_name
    )
    resp = client.post(f"{_LIST}/{app_row.id}/approve", headers=_auth(make_admin()))
    assert resp.status_code == 200, resp.text
    store = db_session.get(
        Store, uuid.UUID(resp.json()["provisioned_store_id"])
    )
    assert store is not None
    assert len(store.name) == 150
    assert store.name == long_name[:150]


def test_approve_missing_returns_404(client: TestClient, make_admin):
    resp = client.post(
        f"{_LIST}/{uuid.uuid4()}/approve", headers=_auth(make_admin())
    )
    assert resp.status_code == 404, resp.text


@pytest.mark.parametrize(
    "status",
    [
        StoreApplicationStatus.draft,
        StoreApplicationStatus.submitted,
        StoreApplicationStatus.rejected,
    ],
)
def test_approve_non_pending_returns_409(
    client: TestClient,
    db_session: Session,
    make_admin,
    make_application,
    supabase_admin_fake,
    status,
):
    app_row = make_application(status=status)
    resp = client.post(
        f"{_LIST}/{app_row.id}/approve", headers=_auth(make_admin())
    )
    assert resp.status_code == 409, resp.text
    # Non-pending guard runs before any provisioning.
    assert supabase_admin_fake.created == []


# --------------------------------------------------------------------- #
# Regression boundary
# --------------------------------------------------------------------- #


def test_public_intake_still_works(client: TestClient):
    resp = client.post(
        "/public/store-applications",
        json={
            "business_name": "Acme Vapes",
            "business_type": "vape_shop",
            "owner_full_name": "Jane Owner",
            "owner_email": "regress@example.com",
            "owner_phone": "+1 555 0100",
            "business_phone": "+1 555 0199",
            "address_line_1": "1 Test Way",
            "city": "Miami",
            "state": "FL",
            "postal_code": "33101",
            "country": "US",
            "location_count": 1,
            "estimated_weekly_orders": 10,
            "hours_of_operation": "Mon-Fri 9-5",
            "terms_accepted": True,
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["status"] == "pending_review"
