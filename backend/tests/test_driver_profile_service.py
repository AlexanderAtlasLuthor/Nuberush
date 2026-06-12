"""Dr.1.1.C — driver service tests.

Exercises `get_driver_profile_for_user`: self-scoped read, the 404/403
outcomes, and the rule that an inactive / pending / rejected profile is
returned (not blocked) since eligibility lives in Dr.1.1.D.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.services.driver import get_driver_profile_for_user
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_profile


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "DP-Svc") -> Store:
        store = Store(name=name, code=f"dps-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


def _driver(db_session: Session, store: Store) -> User:
    return central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )


def test_driver_with_profile_returns_profile(
    db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    profile = make_driver_profile(db_session, user=user, store=store)

    result = get_driver_profile_for_user(db_session, user)
    assert result.id == profile.id


def test_driver_without_profile_raises_404(
    db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)

    with pytest.raises(HTTPException) as exc:
        get_driver_profile_for_user(db_session, user)
    assert exc.value.status_code == 404


@pytest.mark.parametrize(
    "role",
    [UserRole.staff, UserRole.manager, UserRole.owner, UserRole.admin],
)
def test_non_driver_raises_403(
    db_session: Session, make_store, role: UserRole
) -> None:
    store_id = None if role == UserRole.admin else make_store().id
    user = central_make_user(db_session, role=role, store_id=store_id)

    with pytest.raises(HTTPException) as exc:
        get_driver_profile_for_user(db_session, user)
    assert exc.value.status_code == 403


def test_store_mismatch_raises_403(
    db_session: Session, make_store
) -> None:
    profile_store = make_store("profile-store")
    user = _driver(db_session, profile_store)
    make_driver_profile(db_session, user=user, store=profile_store)

    # Simulate a drifted user.store_id (integrity guard path).
    other_store = make_store("other-store")
    user.store_id = other_store.id
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        get_driver_profile_for_user(db_session, user)
    assert exc.value.status_code == 403


@pytest.mark.parametrize(
    ("status_value", "approval_value"),
    [
        ("inactive", "approved"),
        ("active", "pending"),
        ("active", "rejected"),
    ],
)
def test_non_blocking_states_are_returned(
    db_session: Session, make_store, status_value, approval_value
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    profile = make_driver_profile(
        db_session,
        user=user,
        store=store,
        status=status_value,
        approval_status=approval_value,
    )

    result = get_driver_profile_for_user(db_session, user)
    assert result.id == profile.id
    assert result.status == status_value
    assert result.approval_status == approval_value


def test_service_does_not_create_or_mutate(
    db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    # No profile exists -> 404, and crucially nothing is created.
    with pytest.raises(HTTPException):
        get_driver_profile_for_user(db_session, user)

    from app.db.models import DriverProfile
    from sqlalchemy import func, select

    count = db_session.scalar(
        select(func.count()).select_from(DriverProfile)
    )
    assert count == 0
