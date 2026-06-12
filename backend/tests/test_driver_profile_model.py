"""Dr.1.1.C — DriverProfile model / DB constraint tests.

Exercises the `driver_profiles` table directly through the ORM: creation,
the UNIQUE(user_id) one-to-one rule, the status / approval_status CHECK
constraints, FK integrity, timestamps, and the User/Store relationships.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import DriverProfile
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_profile


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "DP-Model") -> Store:
        store = Store(name=name, code=f"dpm-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def driver_user(db_session: Session, make_store) -> tuple[User, Store]:
    store = make_store()
    user = central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )
    return user, store


def test_driver_profile_is_created(
    db_session: Session, driver_user
) -> None:
    user, store = driver_user
    profile = make_driver_profile(db_session, user=user, store=store)

    assert profile.id is not None
    assert profile.user_id == user.id
    assert profile.store_id == store.id
    assert profile.status == "active"
    assert profile.approval_status == "approved"


def test_created_and_updated_at_are_populated(
    db_session: Session, driver_user
) -> None:
    user, store = driver_user
    profile = make_driver_profile(db_session, user=user, store=store)

    assert profile.created_at is not None
    assert profile.updated_at is not None
    # Optional lifecycle stamps default to NULL in Dr.1.1.C.
    assert profile.activated_at is None
    assert profile.deactivated_at is None
    assert profile.approved_at is None


def test_user_id_unique_rejects_second_profile(
    db_session: Session, driver_user
) -> None:
    user, store = driver_user
    make_driver_profile(db_session, user=user, store=store)

    with pytest.raises(IntegrityError):
        # Bypass the helper's commit-per-row so we hit the UNIQUE on flush.
        db_session.add(
            DriverProfile(
                user_id=user.id,
                store_id=store.id,
                status="active",
                approval_status="approved",
            )
        )
        db_session.commit()
    db_session.rollback()


def test_invalid_status_violates_check(
    db_session: Session, driver_user
) -> None:
    user, store = driver_user
    with pytest.raises(IntegrityError):
        db_session.add(
            DriverProfile(
                user_id=user.id,
                store_id=store.id,
                status="suspended",  # not allowed in Dr.1.1.C
                approval_status="approved",
            )
        )
        db_session.commit()
    db_session.rollback()


def test_invalid_approval_status_violates_check(
    db_session: Session, driver_user
) -> None:
    user, store = driver_user
    with pytest.raises(IntegrityError):
        db_session.add(
            DriverProfile(
                user_id=user.id,
                store_id=store.id,
                status="active",
                approval_status="suspended",  # not a valid approval value
            )
        )
        db_session.commit()
    db_session.rollback()


def test_invalid_user_fk_rejected(
    db_session: Session, make_store
) -> None:
    store = make_store()
    with pytest.raises(IntegrityError):
        db_session.add(
            DriverProfile(
                user_id=uuid.uuid4(),  # no such user
                store_id=store.id,
                status="active",
                approval_status="approved",
            )
        )
        db_session.commit()
    db_session.rollback()


def test_invalid_store_fk_rejected(
    db_session: Session, driver_user
) -> None:
    user, _store = driver_user
    with pytest.raises(IntegrityError):
        db_session.add(
            DriverProfile(
                user_id=user.id,
                store_id=uuid.uuid4(),  # no such store
                status="active",
                approval_status="approved",
            )
        )
        db_session.commit()
    db_session.rollback()


def test_user_driver_profile_relationship(
    db_session: Session, driver_user
) -> None:
    user, store = driver_user
    profile = make_driver_profile(db_session, user=user, store=store)

    db_session.refresh(user)
    assert user.driver_profile is not None
    assert user.driver_profile.id == profile.id


def test_store_driver_profiles_relationship(
    db_session: Session, driver_user
) -> None:
    user, store = driver_user
    profile = make_driver_profile(db_session, user=user, store=store)

    db_session.refresh(store)
    assert profile.id in {p.id for p in store.driver_profiles}
