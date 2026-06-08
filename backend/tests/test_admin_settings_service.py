"""Service-layer tests for writable admin settings (F2.27.10).

Exercises `app.services.admin_settings` directly against the test DB:
get-or-create of the singleton `platform_settings` row, the editable block in
the snapshot, the partial-update write path, the dedicated
`platform_settings_audit_logs` trail, and the no-op short-circuit.

Style mirrors test_admin_dashboard_service.py: a local `make_user` fixture
seeds real users; the service is called with `actor=` directly.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PlatformSettings
from app.db.models import PlatformSettingsAuditLog
from app.db.models import User
from app.db.models import UserRole
from app.schemas.admin_settings import AdminSettingsUpdate
from app.services import admin_settings as svc


@pytest.fixture
def make_user(db_session: Session) -> Callable[..., User]:
    def _create(*, role: UserRole = UserRole.admin) -> User:
        user = User(
            full_name=f"SetSvc {role.value}",
            email=f"{role.value}-{uuid.uuid4().hex[:10]}@example.com",
            role=role,
            store_id=None,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


@pytest.fixture
def admin(make_user) -> User:
    return make_user(role=UserRole.admin)


def _audit_count(db: Session) -> int:
    return int(
        db.scalar(select(func.count()).select_from(PlatformSettingsAuditLog))
        or 0
    )


def _settings_count(db: Session) -> int:
    return int(
        db.scalar(select(func.count()).select_from(PlatformSettings)) or 0
    )


# --------------------------------------------------------------------- #
# get-or-create + read path
# --------------------------------------------------------------------- #


def test_get_or_create_seeds_defaults_once(db_session: Session):
    assert _settings_count(db_session) == 0
    s1 = svc._get_or_create_platform_settings(db_session)
    assert s1.platform_name == "NubeRush"
    assert s1.support_email is None
    assert s1.default_locale == "en-US"
    assert s1.default_timezone == "America/New_York"
    # Second call reuses the same singleton — no second row.
    s2 = svc._get_or_create_platform_settings(db_session)
    assert s2.id == s1.id
    assert _settings_count(db_session) == 1
    # Bootstrap create writes NO audit row.
    assert _audit_count(db_session) == 0


def test_snapshot_includes_editable_and_creates_no_audit(
    db_session: Session, admin: User
):
    snap = svc.get_admin_settings_snapshot(db_session, actor=admin)
    assert snap.editable.platform_name == "NubeRush"
    assert snap.editable.support_email is None
    # Existing read-only sections still present.
    for section in (
        "platform",
        "billing",
        "compliance",
        "operations",
        "notifications",
        "admin_preferences",
    ):
        assert getattr(snap, section) is not None
    assert _audit_count(db_session) == 0


def test_snapshot_non_admin_forbidden(db_session: Session, make_user):
    owner = make_user(role=UserRole.owner)
    with pytest.raises(HTTPException) as exc:
        svc.get_admin_settings_snapshot(db_session, actor=owner)
    assert exc.value.status_code == 403


# --------------------------------------------------------------------- #
# update write path
# --------------------------------------------------------------------- #


def test_update_single_field_persists_and_audits(
    db_session: Session, admin: User
):
    result = svc.update_admin_settings(
        db_session,
        AdminSettingsUpdate(platform_name="Acme Co"),
        actor=admin,
    )
    assert result.editable.platform_name == "Acme Co"

    # Persisted.
    row = db_session.scalars(select(PlatformSettings)).one()
    assert row.platform_name == "Acme Co"

    # Exactly one audit row with correct shape.
    audits = list(db_session.scalars(select(PlatformSettingsAuditLog)).all())
    assert len(audits) == 1
    a = audits[0]
    assert a.action == "platform_settings_updated"
    assert a.actor_user_id == admin.id
    assert a.platform_settings_id == row.id
    assert a.before["platform_name"] == "NubeRush"
    assert a.after["platform_name"] == "Acme Co"
    # before/after contain ONLY the four editable fields — no secrets.
    assert set(a.before.keys()) == {
        "platform_name",
        "support_email",
        "default_locale",
        "default_timezone",
    }
    assert set(a.after.keys()) == set(a.before.keys())


def test_update_partial_leaves_other_fields(db_session: Session, admin: User):
    svc.update_admin_settings(
        db_session,
        AdminSettingsUpdate(support_email="ops@example.com"),
        actor=admin,
    )
    svc.update_admin_settings(
        db_session,
        AdminSettingsUpdate(platform_name="Only Name"),
        actor=admin,
    )
    snap = svc.get_admin_settings_snapshot(db_session, actor=admin)
    assert snap.editable.platform_name == "Only Name"
    assert snap.editable.support_email == "ops@example.com"
    # Two real changes → two audit rows.
    assert _audit_count(db_session) == 2


def test_update_then_snapshot_reflects_new_values(
    db_session: Session, admin: User
):
    svc.update_admin_settings(
        db_session,
        AdminSettingsUpdate(
            platform_name="Reflected",
            default_locale="es-MX",
            default_timezone="America/Chicago",
        ),
        actor=admin,
    )
    snap = svc.get_admin_settings_snapshot(db_session, actor=admin)
    assert snap.editable.platform_name == "Reflected"
    assert snap.editable.default_locale == "es-MX"
    assert snap.editable.default_timezone == "America/Chicago"


def test_empty_payload_is_noop_no_audit(db_session: Session, admin: User):
    svc.update_admin_settings(db_session, AdminSettingsUpdate(), actor=admin)
    assert _audit_count(db_session) == 0


def test_same_value_payload_is_noop_no_audit(db_session: Session, admin: User):
    # Set a known value first (1 audit), then PATCH the identical value.
    svc.update_admin_settings(
        db_session, AdminSettingsUpdate(platform_name="Stable"), actor=admin
    )
    assert _audit_count(db_session) == 1
    svc.update_admin_settings(
        db_session, AdminSettingsUpdate(platform_name="Stable"), actor=admin
    )
    # No new audit row for a no-op.
    assert _audit_count(db_session) == 1


def test_clear_support_email_audits(db_session: Session, admin: User):
    svc.update_admin_settings(
        db_session,
        AdminSettingsUpdate(support_email="ops@example.com"),
        actor=admin,
    )
    # Clearing it is a real change (ops@... -> None).
    result = svc.update_admin_settings(
        db_session,
        AdminSettingsUpdate.model_validate({"support_email": ""}),
        actor=admin,
    )
    assert result.editable.support_email is None
    audits = list(
        db_session.scalars(
            select(PlatformSettingsAuditLog).order_by(
                PlatformSettingsAuditLog.created_at.asc()
            )
        ).all()
    )
    assert len(audits) == 2
    assert audits[-1].before["support_email"] == "ops@example.com"
    assert audits[-1].after["support_email"] is None


def test_update_non_admin_forbidden(db_session: Session, make_user):
    staff = make_user(role=UserRole.staff)
    with pytest.raises(HTTPException) as exc:
        svc.update_admin_settings(
            db_session,
            AdminSettingsUpdate(platform_name="Nope"),
            actor=staff,
        )
    assert exc.value.status_code == 403
    # No row mutated, no audit written.
    assert _audit_count(db_session) == 0
