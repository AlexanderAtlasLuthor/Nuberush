"""Dr.1.1.D — driver eligibility service tests.

Exercises `evaluate_driver_eligibility`: the eligible path, every blocker
code (including the service-only `user_inactive`), blocker accumulation, the
403 hard errors, and the no-mutation guarantee.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import DriverProfile
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.services.driver import evaluate_driver_eligibility
from tests.helpers.auth import make_user as central_make_user
from tests.helpers.driver import make_driver_profile


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "DP-Elig", is_active: bool = True) -> Store:
        store = Store(
            name=name,
            code=f"dpe-{uuid.uuid4().hex[:8]}",
            is_active=is_active,
        )
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


def _driver(
    db_session: Session, store: Store, is_active: bool = True
) -> User:
    return central_make_user(
        db_session,
        role=UserRole.driver,
        store_id=store.id,
        is_active=is_active,
    )


def _codes(result) -> set[str]:
    return {b.code.value for b in result.blockers}


def test_eligible_driver(db_session: Session, make_store) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(
        db_session,
        user=user,
        store=store,
        status="active",
        approval_status="approved",
    )

    result = evaluate_driver_eligibility(db_session, user)
    assert result.can_go_online is True
    assert result.blockers == []
    assert result.driver_status == "active"
    assert result.driver_approval_status == "approved"
    assert result.user_active is True
    assert result.store_active is True
    assert result.evaluated_at is not None


def test_missing_profile(db_session: Session, make_store) -> None:
    store = make_store()
    user = _driver(db_session, store)

    result = evaluate_driver_eligibility(db_session, user)
    assert result.can_go_online is False
    assert "driver_profile_missing" in _codes(result)
    assert result.driver_status is None
    assert result.driver_approval_status is None
    assert result.store_active is None


def test_inactive_profile(db_session: Session, make_store) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(
        db_session,
        user=user,
        store=store,
        status="inactive",
        approval_status="approved",
    )

    result = evaluate_driver_eligibility(db_session, user)
    assert result.can_go_online is False
    assert "driver_profile_inactive" in _codes(result)


def test_approval_pending(db_session: Session, make_store) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(
        db_session,
        user=user,
        store=store,
        status="active",
        approval_status="pending",
    )

    result = evaluate_driver_eligibility(db_session, user)
    assert result.can_go_online is False
    assert "driver_approval_pending" in _codes(result)


def test_approval_rejected(db_session: Session, make_store) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(
        db_session,
        user=user,
        store=store,
        status="active",
        approval_status="rejected",
    )

    result = evaluate_driver_eligibility(db_session, user)
    assert result.can_go_online is False
    assert "driver_approval_rejected" in _codes(result)


def test_inactive_store(db_session: Session, make_store) -> None:
    store = make_store(is_active=False)
    user = _driver(db_session, store)
    make_driver_profile(
        db_session,
        user=user,
        store=store,
        status="active",
        approval_status="approved",
    )

    result = evaluate_driver_eligibility(db_session, user)
    assert result.can_go_online is False
    assert "store_inactive" in _codes(result)
    assert result.store_active is False


def test_inactive_user_service_level_only(
    db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store, is_active=False)
    make_driver_profile(
        db_session,
        user=user,
        store=store,
        status="active",
        approval_status="approved",
    )

    result = evaluate_driver_eligibility(db_session, user)
    assert result.can_go_online is False
    assert "user_inactive" in _codes(result)
    assert result.user_active is False


def test_multiple_blockers_accumulated(
    db_session: Session, make_store
) -> None:
    store = make_store(is_active=False)
    user = _driver(db_session, store)
    make_driver_profile(
        db_session,
        user=user,
        store=store,
        status="inactive",
        approval_status="pending",
    )

    result = evaluate_driver_eligibility(db_session, user)
    assert result.can_go_online is False
    codes = _codes(result)
    assert {
        "store_inactive",
        "driver_profile_inactive",
        "driver_approval_pending",
    } <= codes


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
        evaluate_driver_eligibility(db_session, user)
    assert exc.value.status_code == 403


def test_driver_without_store_raises_403(db_session: Session) -> None:
    user = central_make_user(
        db_session, role=UserRole.driver, store_id=None
    )
    with pytest.raises(HTTPException) as exc:
        evaluate_driver_eligibility(db_session, user)
    assert exc.value.status_code == 403


def test_store_mismatch_raises_403(
    db_session: Session, make_store
) -> None:
    profile_store = make_store("profile-store")
    user = _driver(db_session, profile_store)
    make_driver_profile(db_session, user=user, store=profile_store)

    other_store = make_store("other-store")
    user.store_id = other_store.id
    db_session.commit()

    with pytest.raises(HTTPException) as exc:
        evaluate_driver_eligibility(db_session, user)
    assert exc.value.status_code == 403


def test_no_mutation_on_missing_profile(
    db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)

    evaluate_driver_eligibility(db_session, user)

    count = db_session.scalar(
        select(func.count()).select_from(DriverProfile)
    )
    assert count == 0


def test_no_mutation_on_existing_profile(
    db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    profile = make_driver_profile(
        db_session,
        user=user,
        store=store,
        status="active",
        approval_status="approved",
    )
    before_updated_at = profile.updated_at

    evaluate_driver_eligibility(db_session, user)

    db_session.refresh(profile)
    assert profile.status == "active"
    assert profile.approval_status == "approved"
    assert profile.updated_at == before_updated_at
