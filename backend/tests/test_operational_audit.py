"""Direct tests for the operational audit writer helper (F2.26.1.B).

Scope: the writer helper only. No users/stores/routes/feed integration is
exercised here — those land in later subphases.
"""

from __future__ import annotations

import json
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import OperationalAuditLog
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.stores import StoreCreate
from app.schemas.stores import StoreUpdate
from app.schemas.users import UserRoleChangeRequest
from app.schemas.users import UserStoreAssignmentRequest
from app.schemas.users import UserUpdateRequest
from app.services import stores as stores_svc
from app.services import users as users_svc
from app.services.operational_audit import write_operational_audit_log
from tests.helpers.auth import auth_headers_for
from tests.helpers.auth import make_user as make_auth_user


# --------------------------------------------------------------------- #
# Local helpers — build committed parent rows so FK constraints
# (actor_user_id -> users.id, store_id -> stores.id) are satisfied.
# --------------------------------------------------------------------- #


def _make_store(db: Session) -> Store:
    store = Store(
        name="Audit Test Store",
        code=f"audit-{uuid.uuid4().hex[:10]}",
    )
    db.add(store)
    db.flush()
    return store


def _make_user(db: Session, *, store_id: uuid.UUID | None) -> User:
    user = User(
        full_name="Audit Actor",
        email=f"actor-{uuid.uuid4().hex[:10]}@example.com",
        role=UserRole.staff,
        store_id=store_id,
    )
    db.add(user)
    db.flush()
    return user


def _fetch(db: Session, target_id: uuid.UUID) -> OperationalAuditLog | None:
    return db.scalar(
        select(OperationalAuditLog).where(
            OperationalAuditLog.target_id == target_id
        )
    )


# --------------------------------------------------------------------- #
# A. Happy path — user
# --------------------------------------------------------------------- #


def test_happy_path_user(db_session: Session) -> None:
    store = _make_store(db_session)
    actor = _make_user(db_session, store_id=store.id)
    target_id = uuid.uuid4()

    log = write_operational_audit_log(
        db_session,
        actor_user_id=actor.id,
        target_type="user",
        target_id=target_id,
        action="user_updated",
        store_id=store.id,
        before={"full_name": "Old Name"},
        after={"full_name": "New Name"},
    )

    # Returned object is the model instance.
    assert isinstance(log, OperationalAuditLog)

    db_session.flush()
    fetched = _fetch(db_session, target_id)
    assert fetched is not None
    assert fetched.actor_user_id == actor.id
    assert fetched.target_type == "user"
    assert fetched.target_id == target_id
    assert fetched.action == "user_updated"
    assert fetched.store_id == store.id
    assert fetched.before == {"full_name": "Old Name"}
    assert fetched.after == {"full_name": "New Name"}


# --------------------------------------------------------------------- #
# B. Happy path — store
# --------------------------------------------------------------------- #


def test_happy_path_store(db_session: Session) -> None:
    store = _make_store(db_session)
    actor = _make_user(db_session, store_id=store.id)

    write_operational_audit_log(
        db_session,
        actor_user_id=actor.id,
        target_type="store",
        target_id=store.id,
        action="store_updated",
        store_id=store.id,
        before={"name": "Old Store"},
        after={"name": "New Store"},
    )

    db_session.flush()
    fetched = _fetch(db_session, store.id)
    assert fetched is not None
    assert fetched.target_type == "store"
    assert fetched.action == "store_updated"
    assert fetched.target_id == store.id
    assert fetched.store_id == store.id
    assert fetched.actor_user_id == actor.id
    assert fetched.before == {"name": "Old Store"}
    assert fetched.after == {"name": "New Store"}


# --------------------------------------------------------------------- #
# C. The helper does not commit by itself
# --------------------------------------------------------------------- #


def test_helper_does_not_commit(db_session: Session) -> None:
    store = _make_store(db_session)
    actor = _make_user(db_session, store_id=store.id)
    target_id = uuid.uuid4()

    write_operational_audit_log(
        db_session,
        actor_user_id=actor.id,
        target_type="store",
        target_id=target_id,
        action="store_activated",
        store_id=store.id,
    )

    # No commit happened inside the helper, so a rollback must discard the
    # pending row entirely.
    db_session.rollback()

    assert _fetch(db_session, target_id) is None


# --------------------------------------------------------------------- #
# D / E / F. Taxonomy validation
# --------------------------------------------------------------------- #


def test_invalid_target_type_raises(db_session: Session) -> None:
    with pytest.raises(ValueError, match="target_type"):
        write_operational_audit_log(
            db_session,
            actor_user_id=None,
            target_type="product",
            target_id=uuid.uuid4(),
            action="user_updated",
        )


def test_invalid_action_raises(db_session: Session) -> None:
    with pytest.raises(ValueError, match="action"):
        write_operational_audit_log(
            db_session,
            actor_user_id=None,
            target_type="user",
            target_id=uuid.uuid4(),
            action="user_frobnicated",
        )


def test_action_target_mismatch_raises(db_session: Session) -> None:
    with pytest.raises(ValueError, match="does not belong"):
        write_operational_audit_log(
            db_session,
            actor_user_id=None,
            target_type="user",
            target_id=uuid.uuid4(),
            action="store_updated",
        )


# --------------------------------------------------------------------- #
# G. before/after allow-list
# --------------------------------------------------------------------- #


def test_before_after_allow_list_filters_unknown_and_sensitive(
    db_session: Session,
) -> None:
    log = write_operational_audit_log(
        db_session,
        actor_user_id=None,
        target_type="user",
        target_id=uuid.uuid4(),
        action="user_updated",
        before={
            "role": "staff",          # allowed
            "is_active": True,        # allowed
            "email": "a@b.com",       # NOT in allow-list -> dropped
            "password": "hunter2",    # sensitive -> dropped
            "auth_user_id": str(uuid.uuid4()),  # not allowed -> dropped
        },
        after={
            "role": "manager",
            "full_name": "Jane",
            "reset_token": "abc",     # sensitive -> dropped
        },
    )

    assert log.before == {"role": "staff", "is_active": True}
    assert log.after == {"role": "manager", "full_name": "Jane"}


def test_store_allow_list_uses_real_columns_only(
    db_session: Session,
) -> None:
    log = write_operational_audit_log(
        db_session,
        actor_user_id=None,
        target_type="store",
        target_id=uuid.uuid4(),
        action="store_updated",
        before={
            "name": "Old",
            "code": "abc-123",
            "is_active": True,
            "timezone": "America/New_York",
            "slug": "made-up",        # not a real column -> dropped
            "address": "123 St",      # not a real column -> dropped
        },
    )
    assert log.before == {
        "name": "Old",
        "code": "abc-123",
        "is_active": True,
        "timezone": "America/New_York",
    }


# --------------------------------------------------------------------- #
# H. metadata redaction
# --------------------------------------------------------------------- #


def test_metadata_redaction_drops_sensitive_keys(
    db_session: Session,
) -> None:
    log = write_operational_audit_log(
        db_session,
        actor_user_id=None,
        target_type="user",
        target_id=uuid.uuid4(),
        action="user_role_changed",
        metadata={
            "reason": "promotion",          # safe
            "source": "admin_panel",        # safe
            "password": "hunter2",          # sensitive
            "access_token": "tok",          # sensitive
            "api_key": "k",                 # sensitive
            "Authorization": "Bearer x",    # sensitive
            "supabase_url": "https://x",    # sensitive (contains 'supabase')
            "nested": {                     # nested scrub
                "ok": 1,
                "jwt": "e.y.z",             # sensitive nested
            },
        },
    )

    assert log.event_metadata == {
        "reason": "promotion",
        "source": "admin_panel",
        "nested": {"ok": 1},
    }


# --------------------------------------------------------------------- #
# I. No sensitive data survives serialization anywhere
# --------------------------------------------------------------------- #


def test_no_sensitive_values_in_serialized_payload(
    db_session: Session,
) -> None:
    log = write_operational_audit_log(
        db_session,
        actor_user_id=None,
        target_type="user",
        target_id=uuid.uuid4(),
        action="user_updated",
        before={"password": "TOPSECRETPW", "role": "staff"},
        after={"refresh_token": "RTVALUE", "full_name": "Jane"},
        metadata={
            "secret": "SECRETVALUE",
            "jwt": "JWTVALUE",
            "reason": "ok",
        },
    )

    blob = json.dumps(
        {
            "before": log.before,
            "after": log.after,
            "metadata": log.event_metadata,
        }
    )
    for needle in (
        "TOPSECRETPW",
        "RTVALUE",
        "SECRETVALUE",
        "JWTVALUE",
        "password",
        "refresh_token",
        "secret",
        "jwt",
    ):
        assert needle not in blob, f"sensitive token leaked: {needle}"

    # Safe values survive.
    assert log.before == {"role": "staff"}
    assert log.after == {"full_name": "Jane"}
    assert log.event_metadata == {"reason": "ok"}


# --------------------------------------------------------------------- #
# J. No feed integration: the writer module must not depend on the
# unified audit feed module or its schemas.
# --------------------------------------------------------------------- #


def test_writer_does_not_import_audit_feed() -> None:
    import ast

    import app.services.operational_audit as mod

    with open(mod.__file__, "r", encoding="utf-8") as fh:
        tree = ast.parse(fh.read())

    # Collect every imported module path (import X / from X import ...).
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)

    # The writer must not depend on the unified feed or its schemas.
    assert "app.services.audit" not in imported
    assert "app.schemas.audit" not in imported
    # And the feed enums must not be referenced as runtime names.
    assert not hasattr(mod, "AuditSource")
    assert not hasattr(mod, "AuditEntityType")


# ===================================================================== #
# F2.26.1.C — User mutation audit hooks (integration with users service
# + the create_user route). Each test drives a real mutation and asserts
# the operational_audit_logs row it must leave (same transaction).
# ===================================================================== #


def _fetch_event(
    db: Session, target_id: uuid.UUID, action: str
) -> OperationalAuditLog | None:
    return db.scalar(
        select(OperationalAuditLog).where(
            OperationalAuditLog.target_id == target_id,
            OperationalAuditLog.action == action,
        )
    )


def _assert_no_sensitive(log: OperationalAuditLog) -> None:
    blob = json.dumps(
        {
            "before": log.before,
            "after": log.after,
            "metadata": log.event_metadata,
        }
    )
    for needle in (
        "password",
        "token",
        "secret",
        "auth_user_id",
        "@",  # email addresses must never appear in the snapshots
    ):
        assert needle not in blob, f"sensitive/PII leaked: {needle}"


# --------------------------------------------------------------------- #
# B. update user
# --------------------------------------------------------------------- #


def test_update_user_writes_audit(db_session: Session) -> None:
    store = _make_store(db_session)
    admin = make_auth_user(db_session, role=UserRole.admin)
    target = make_auth_user(
        db_session, role=UserRole.staff, store_id=store.id,
        full_name="Old Name",
    )

    users_svc.update_user(
        db_session,
        target.id,
        UserUpdateRequest(full_name="New Name"),
        actor=admin,
    )

    log = _fetch_event(db_session, target.id, "user_updated")
    assert log is not None
    assert log.target_type == "user"
    assert log.actor_user_id == admin.id
    assert log.store_id == store.id
    assert log.before["full_name"] == "Old Name"
    assert log.after["full_name"] == "New Name"
    _assert_no_sensitive(log)


# --------------------------------------------------------------------- #
# C. change role
# --------------------------------------------------------------------- #


def test_change_role_store_bound_writes_audit(db_session: Session) -> None:
    store = _make_store(db_session)
    admin = make_auth_user(db_session, role=UserRole.admin)
    target = make_auth_user(
        db_session, role=UserRole.staff, store_id=store.id
    )

    users_svc.change_user_role(
        db_session,
        target.id,
        UserRoleChangeRequest(role=UserRole.manager),
        actor=admin,
    )

    log = _fetch_event(db_session, target.id, "user_role_changed")
    assert log is not None
    assert log.before["role"] == "staff"
    assert log.after["role"] == "manager"
    # store-bound: event scoped to the (unchanged) store.
    assert log.store_id == store.id
    _assert_no_sensitive(log)


def test_change_role_to_admin_clears_store_and_audits_global(
    db_session: Session,
) -> None:
    store = _make_store(db_session)
    admin = make_auth_user(db_session, role=UserRole.admin)
    # Promotion to admin requires a @nuberush.com identity.
    target = make_auth_user(
        db_session,
        role=UserRole.manager,
        store_id=store.id,
        email=f"promote-{uuid.uuid4().hex[:8]}@nuberush.com",
    )

    users_svc.change_user_role(
        db_session,
        target.id,
        UserRoleChangeRequest(role=UserRole.admin),
        actor=admin,
    )

    log = _fetch_event(db_session, target.id, "user_role_changed")
    assert log is not None
    assert log.before["role"] == "manager"
    assert log.before["store_id"] == str(store.id)
    assert log.after["role"] == "admin"
    assert log.after["store_id"] is None
    # admin/global: event store_id is NULL.
    assert log.store_id is None
    _assert_no_sensitive(log)


# --------------------------------------------------------------------- #
# D. assign store
# --------------------------------------------------------------------- #


def test_assign_store_writes_assigned_audit(db_session: Session) -> None:
    store_a = _make_store(db_session)
    store_b = _make_store(db_session)
    admin = make_auth_user(db_session, role=UserRole.admin)
    target = make_auth_user(
        db_session, role=UserRole.staff, store_id=store_a.id
    )

    users_svc.assign_user_store(
        db_session,
        target.id,
        UserStoreAssignmentRequest(store_id=store_b.id),
        actor=admin,
    )

    log = _fetch_event(db_session, target.id, "user_store_assigned")
    assert log is not None
    assert log.before["store_id"] == str(store_a.id)
    assert log.after["store_id"] == str(store_b.id)
    # assigned: scoped to the store the user now belongs to.
    assert log.store_id == store_b.id
    _assert_no_sensitive(log)


# --------------------------------------------------------------------- #
# E. remove store (store_id -> None). Reachable via assign on an
# admin-role target; we construct an admin that still carries a store so
# the removal records a real previous store.
# --------------------------------------------------------------------- #


def test_remove_store_writes_removed_audit(db_session: Session) -> None:
    store = _make_store(db_session)
    admin = make_auth_user(db_session, role=UserRole.admin)
    # An admin row that still carries a store_id (the model column is
    # nullable; the invariant is service-enforced). Clearing it exercises
    # the "removed" branch with a real previous store.
    target = make_auth_user(
        db_session,
        role=UserRole.admin,
        store_id=store.id,
        email=f"adm-{uuid.uuid4().hex[:8]}@nuberush.com",
    )

    users_svc.assign_user_store(
        db_session,
        target.id,
        UserStoreAssignmentRequest(store_id=None),
        actor=admin,
    )

    log = _fetch_event(db_session, target.id, "user_store_removed")
    assert log is not None
    assert log.before["store_id"] == str(store.id)
    assert log.after["store_id"] is None
    # removed: scoped to the store the user was removed FROM.
    assert log.store_id == store.id
    _assert_no_sensitive(log)


# --------------------------------------------------------------------- #
# F. deactivate user
# --------------------------------------------------------------------- #


def test_deactivate_user_writes_audit(db_session: Session) -> None:
    store = _make_store(db_session)
    admin = make_auth_user(db_session, role=UserRole.admin)
    target = make_auth_user(
        db_session, role=UserRole.staff, store_id=store.id
    )

    users_svc.deactivate_user(db_session, target.id, actor=admin)

    log = _fetch_event(db_session, target.id, "user_deactivated")
    assert log is not None
    assert log.before["is_active"] is True
    assert log.after["is_active"] is False
    assert log.store_id == store.id
    _assert_no_sensitive(log)


# --------------------------------------------------------------------- #
# G. reactivate user
# --------------------------------------------------------------------- #


def test_reactivate_user_writes_audit(db_session: Session) -> None:
    store = _make_store(db_session)
    admin = make_auth_user(db_session, role=UserRole.admin)
    target = make_auth_user(
        db_session,
        role=UserRole.staff,
        store_id=store.id,
        is_active=False,
    )

    users_svc.reactivate_user(db_session, target.id, actor=admin)

    log = _fetch_event(db_session, target.id, "user_activated")
    assert log is not None
    assert log.before["is_active"] is False
    assert log.after["is_active"] is True
    assert log.store_id == store.id
    _assert_no_sensitive(log)


# --------------------------------------------------------------------- #
# A. create user (HTTP route) writes audit
# --------------------------------------------------------------------- #


def test_create_user_writes_audit(
    client: TestClient, db_session: Session
) -> None:
    store = _make_store(db_session)
    admin = make_auth_user(db_session, role=UserRole.admin)

    resp = client.post(
        "/auth/users",
        headers=auth_headers_for(admin),
        json={
            "full_name": "Created Staff",
            "email": f"created-{uuid.uuid4().hex[:8]}@example.com",
            "password": "sup3rsecret-pw",
            "role": "staff",
            "store_id": str(store.id),
        },
    )
    assert resp.status_code == 201, resp.text
    created_id = uuid.UUID(resp.json()["id"])

    log = _fetch_event(db_session, created_id, "user_created")
    assert log is not None
    assert log.target_type == "user"
    assert log.actor_user_id == admin.id
    assert log.store_id == store.id
    assert log.before is None
    assert log.after["role"] == "staff"
    assert log.after["full_name"] == "Created Staff"
    # No password / email / auth_user_id captured.
    _assert_no_sensitive(log)


# --------------------------------------------------------------------- #
# H. Failed mutation does not write an audit row (guard fails before the
# audit write; transaction leaves no event).
# --------------------------------------------------------------------- #


def test_failed_mutation_writes_no_audit(db_session: Session) -> None:
    admin = make_auth_user(db_session, role=UserRole.admin)

    # Self-deactivation is rejected (422) before any snapshot/audit write.
    with pytest.raises(Exception):
        users_svc.deactivate_user(db_session, admin.id, actor=admin)

    assert _fetch_event(db_session, admin.id, "user_deactivated") is None


# --------------------------------------------------------------------- #
# I. create_user rollback leaves no audit row: if anything in the
# flush/audit/commit block fails, neither the user nor its audit persists.
# --------------------------------------------------------------------- #


def test_create_user_rollback_leaves_no_audit(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _make_store(db_session)
    admin = make_auth_user(db_session, role=UserRole.admin)
    email = f"rollback-{uuid.uuid4().hex[:8]}@example.com"

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated audit write failure")

    # Force the in-transaction audit write to fail after the user flush.
    monkeypatch.setattr(
        "app.api.routes.auth.write_operational_audit_log", _boom
    )

    resp = client.post(
        "/auth/users",
        headers=auth_headers_for(admin),
        json={
            "full_name": "Rolled Back",
            "email": email,
            "password": "sup3rsecret-pw",
            "role": "staff",
            "store_id": str(store.id),
        },
    )
    assert resp.status_code == 500

    # Neither the user nor any operational audit row persisted.
    assert db_session.scalar(
        select(User).where(User.email == email)
    ) is None
    assert db_session.scalar(
        select(OperationalAuditLog).where(
            OperationalAuditLog.action == "user_created"
        )
    ) is None


# ===================================================================== #
# F2.26.1.D — Store mutation audit hooks (integration with the stores
# service). Each test drives a real store mutation and asserts the
# operational_audit_logs row it must leave (same transaction).
# ===================================================================== #


# --------------------------------------------------------------------- #
# A. create store
# --------------------------------------------------------------------- #


def test_create_store_writes_audit(db_session: Session) -> None:
    admin = make_auth_user(db_session, role=UserRole.admin)

    created = stores_svc.create_store(
        db_session,
        actor=admin,
        payload=StoreCreate(
            name="Created Store", code=f"cs-{uuid.uuid4().hex[:8]}"
        ),
    )

    log = _fetch_event(db_session, created.id, "store_created")
    assert log is not None
    assert log.target_type == "store"
    assert log.actor_user_id == admin.id
    assert log.target_id == created.id
    assert log.store_id == created.id
    assert log.before is None
    assert log.after["name"] == "Created Store"
    assert log.after["is_active"] is True
    _assert_no_sensitive(log)


# --------------------------------------------------------------------- #
# B. update store
# --------------------------------------------------------------------- #


def test_update_store_writes_audit(db_session: Session) -> None:
    admin = make_auth_user(db_session, role=UserRole.admin)
    store = _make_store(db_session)
    original_name = store.name

    stores_svc.update_store(
        db_session,
        store.id,
        StoreUpdate(name="Renamed Store"),
        actor=admin,
    )

    log = _fetch_event(db_session, store.id, "store_updated")
    assert log is not None
    assert log.target_type == "store"
    assert log.actor_user_id == admin.id
    assert log.store_id == store.id
    assert log.before["name"] == original_name
    assert log.after["name"] == "Renamed Store"
    _assert_no_sensitive(log)


# --------------------------------------------------------------------- #
# C. deactivate store
# --------------------------------------------------------------------- #


def test_deactivate_store_writes_audit(db_session: Session) -> None:
    admin = make_auth_user(db_session, role=UserRole.admin)
    store = _make_store(db_session)  # active by default

    stores_svc.deactivate_store(db_session, actor=admin, store_id=store.id)

    log = _fetch_event(db_session, store.id, "store_deactivated")
    assert log is not None
    assert log.actor_user_id == admin.id
    assert log.store_id == store.id
    assert log.before["is_active"] is True
    assert log.after["is_active"] is False
    _assert_no_sensitive(log)


# --------------------------------------------------------------------- #
# D. reactivate store
# --------------------------------------------------------------------- #


def test_reactivate_store_writes_audit(db_session: Session) -> None:
    admin = make_auth_user(db_session, role=UserRole.admin)
    store = Store(
        name="Inactive Store",
        code=f"is-{uuid.uuid4().hex[:8]}",
        is_active=False,
    )
    db_session.add(store)
    db_session.flush()

    stores_svc.reactivate_store(db_session, actor=admin, store_id=store.id)

    log = _fetch_event(db_session, store.id, "store_activated")
    assert log is not None
    assert log.actor_user_id == admin.id
    assert log.store_id == store.id
    assert log.before["is_active"] is False
    assert log.after["is_active"] is True
    _assert_no_sensitive(log)


# --------------------------------------------------------------------- #
# E. Failed store mutation does not write an audit row. Deactivating an
# already-inactive store is rejected (422) before any audit write.
# --------------------------------------------------------------------- #


def test_failed_store_mutation_writes_no_audit(db_session: Session) -> None:
    admin = make_auth_user(db_session, role=UserRole.admin)
    store = Store(
        name="Already Inactive",
        code=f"ai-{uuid.uuid4().hex[:8]}",
        is_active=False,
    )
    db_session.add(store)
    db_session.flush()

    with pytest.raises(Exception):
        stores_svc.deactivate_store(
            db_session, actor=admin, store_id=store.id
        )

    assert _fetch_event(db_session, store.id, "store_deactivated") is None


def test_create_store_duplicate_code_leaves_no_orphan_audit(
    db_session: Session,
) -> None:
    admin = make_auth_user(db_session, role=UserRole.admin)
    code = f"dup-{uuid.uuid4().hex[:8]}"

    first = stores_svc.create_store(
        db_session, actor=admin, payload=StoreCreate(name="First", code=code)
    )
    with pytest.raises(Exception):
        stores_svc.create_store(
            db_session,
            actor=admin,
            payload=StoreCreate(name="Second", code=code),
        )

    # Exactly one store_created audit exists (the successful first create);
    # the rolled-back duplicate left no orphan row.
    rows = list(
        db_session.scalars(
            select(OperationalAuditLog).where(
                OperationalAuditLog.action == "store_created"
            )
        )
    )
    assert len(rows) == 1
    assert rows[0].target_id == first.id
