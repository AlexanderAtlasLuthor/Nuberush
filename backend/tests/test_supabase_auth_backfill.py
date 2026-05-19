"""Tests for the Supabase Auth backfill tool (F2.22.2.E2).

Exercises `scripts.backfill_supabase_auth_users.run_backfill` — the
testable core of the operator CLI — fully offline. The Supabase Admin
API is the autouse `supabase_admin_fake` fixture (tests/conftest.py);
`run_backfill` takes the create/delete callables as parameters, so the
tests inject the fake's methods directly. No real Supabase, no
service-role key.
"""

import uuid

import pytest
from sqlalchemy.orm import Session

from app.db.models import Store
from app.db.models import UserRole
from scripts.backfill_supabase_auth_users import BackfillError
from scripts.backfill_supabase_auth_users import run_backfill
from tests.helpers.auth import make_user as central_make_user


TEMP_PW = "Temp-Backfill-Pw-1234"


def _store(db: Session) -> Store:
    store = Store(name="Backfill Store", code=f"bf-{uuid.uuid4().hex[:8]}")
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


def _unmapped_user(db: Session, store_id: uuid.UUID, *, email: str | None = None):
    """Create a pre-F2.22.2-style user: persisted, auth_user_id NULL."""
    return central_make_user(
        db,
        role=UserRole.staff,
        store_id=store_id,
        email=email,
        auth_user_id=None,
    )


def test_dry_run_makes_no_changes(
    db_session: Session, supabase_admin_fake, capsys
) -> None:
    store = _store(db_session)
    user = _unmapped_user(db_session, store.id)

    summary = run_backfill(
        db_session,
        create_auth_user=supabase_admin_fake.create_auth_user,
        delete_auth_user=supabase_admin_fake.delete_auth_user,
        apply=False,
    )

    assert summary.scanned == 1
    assert summary.created == 0
    # Dry-run calls no Supabase API and writes nothing.
    assert supabase_admin_fake.created == []
    db_session.refresh(user)
    assert user.auth_user_id is None


def test_apply_creates_supabase_user_and_maps_auth_user_id(
    db_session: Session, supabase_admin_fake
) -> None:
    store = _store(db_session)
    user = _unmapped_user(db_session, store.id)

    summary = run_backfill(
        db_session,
        create_auth_user=supabase_admin_fake.create_auth_user,
        delete_auth_user=supabase_admin_fake.delete_auth_user,
        apply=True,
        temp_password=TEMP_PW,
    )

    assert summary.created == 1
    assert summary.failed == 0
    db_session.refresh(user)
    assert user.auth_user_id is not None
    assert len(supabase_admin_fake.created) == 1
    created = supabase_admin_fake.created[0]
    assert created["email"] == user.email
    assert created["password"] == TEMP_PW
    # auth_user_id on the row matches the UUID Supabase returned.
    assert user.auth_user_id == created["id"]


def test_already_mapped_user_is_skipped(
    db_session: Session, supabase_admin_fake
) -> None:
    store = _store(db_session)
    central_make_user(
        db_session,
        role=UserRole.staff,
        store_id=store.id,
        auth_user_id=uuid.uuid4(),
    )

    summary = run_backfill(
        db_session,
        create_auth_user=supabase_admin_fake.create_auth_user,
        delete_auth_user=supabase_admin_fake.delete_auth_user,
        apply=True,
        temp_password=TEMP_PW,
    )

    assert summary.scanned == 1
    assert summary.skipped_already_mapped == 1
    assert summary.created == 0
    assert supabase_admin_fake.created == []


def test_email_filter_limits_scope(
    db_session: Session, supabase_admin_fake
) -> None:
    store = _store(db_session)
    target = _unmapped_user(db_session, store.id, email="target@example.com")
    other = _unmapped_user(db_session, store.id, email="other@example.com")

    summary = run_backfill(
        db_session,
        create_auth_user=supabase_admin_fake.create_auth_user,
        delete_auth_user=supabase_admin_fake.delete_auth_user,
        apply=True,
        temp_password=TEMP_PW,
        email="target@example.com",
    )

    assert summary.scanned == 1
    assert summary.created == 1
    db_session.refresh(target)
    db_session.refresh(other)
    assert target.auth_user_id is not None
    assert other.auth_user_id is None


def test_supabase_create_failure_leaves_user_unmapped(
    db_session: Session, supabase_admin_fake
) -> None:
    store = _store(db_session)
    user = _unmapped_user(db_session, store.id)
    supabase_admin_fake.create_should_fail = True

    summary = run_backfill(
        db_session,
        create_auth_user=supabase_admin_fake.create_auth_user,
        delete_auth_user=supabase_admin_fake.delete_auth_user,
        apply=True,
        temp_password=TEMP_PW,
    )

    assert summary.failed == 1
    assert summary.created == 0
    db_session.refresh(user)
    assert user.auth_user_id is None


def test_db_failure_after_create_triggers_cleanup(
    db_session: Session, supabase_admin_fake
) -> None:
    store = _store(db_session)
    # An existing user already owns this auth_user_id, so the unmapped
    # user's public.users update will hit the unique index and fail
    # AFTER its Supabase identity was created.
    collision = uuid.uuid4()
    central_make_user(
        db_session,
        role=UserRole.staff,
        store_id=store.id,
        auth_user_id=collision,
    )
    user = _unmapped_user(db_session, store.id)
    supabase_admin_fake.next_auth_user_id = collision

    summary = run_backfill(
        db_session,
        create_auth_user=supabase_admin_fake.create_auth_user,
        delete_auth_user=supabase_admin_fake.delete_auth_user,
        apply=True,
        temp_password=TEMP_PW,
    )

    assert summary.skipped_already_mapped == 1
    assert summary.failed == 1
    assert summary.created == 0
    # The orphaned Supabase identity was rolled back.
    assert supabase_admin_fake.deleted == [collision]
    db_session.refresh(user)
    assert user.auth_user_id is None


def test_apply_without_password_is_refused(
    db_session: Session, supabase_admin_fake
) -> None:
    store = _store(db_session)
    _unmapped_user(db_session, store.id)

    with pytest.raises(BackfillError):
        run_backfill(
            db_session,
            create_auth_user=supabase_admin_fake.create_auth_user,
            delete_auth_user=supabase_admin_fake.delete_auth_user,
            apply=True,
            temp_password=None,
        )

    # Nothing was created.
    assert supabase_admin_fake.created == []


def test_output_never_contains_the_temporary_password(
    db_session: Session, supabase_admin_fake, capsys
) -> None:
    store = _store(db_session)
    _unmapped_user(db_session, store.id)
    secret = "UltraSecret-Temp-Pw-9999"

    run_backfill(
        db_session,
        create_auth_user=supabase_admin_fake.create_auth_user,
        delete_auth_user=supabase_admin_fake.delete_auth_user,
        apply=True,
        temp_password=secret,
    )

    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err


def test_rerun_is_idempotent(
    db_session: Session, supabase_admin_fake
) -> None:
    store = _store(db_session)
    _unmapped_user(db_session, store.id)
    _unmapped_user(db_session, store.id)

    first = run_backfill(
        db_session,
        create_auth_user=supabase_admin_fake.create_auth_user,
        delete_auth_user=supabase_admin_fake.delete_auth_user,
        apply=True,
        temp_password=TEMP_PW,
    )
    assert first.created == 2

    # A second run finds every user already mapped — no-op.
    second = run_backfill(
        db_session,
        create_auth_user=supabase_admin_fake.create_auth_user,
        delete_auth_user=supabase_admin_fake.delete_auth_user,
        apply=True,
        temp_password=TEMP_PW,
    )
    assert second.scanned == 2
    assert second.skipped_already_mapped == 2
    assert second.created == 0
