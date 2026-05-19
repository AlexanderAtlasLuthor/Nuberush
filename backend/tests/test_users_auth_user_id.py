"""DB-level coverage for the F2.22.2 `users.auth_user_id` identity bridge.

Verifies the additive guarantees of the
`b7e3a1f04c9d_add_users_auth_user_id` migration:

- a `users` row may exist with `auth_user_id` NULL (existing rows,
  pre-Supabase identity);
- a `users` row may carry an explicit `auth_user_id` UUID;
- `auth_user_id` is unique — one Supabase identity maps to at most
  one `public.users` row;
- multiple rows may keep `auth_user_id` NULL simultaneously, since
  Postgres treats NULLs as distinct under a unique index.

Scope note: this suite covers only the `auth_user_id` column. As of
F2.22.2.F there is no local `password_hash` column — authentication is
exclusively via Supabase JWT and `auth_user_id` is the sole bridge.

User construction is routed through `tests.helpers.auth` so the
identity mechanism stays defined in one place.
"""

import uuid

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Store
from app.db.models import UserRole
from tests.helpers.auth import make_user


def _make_store(db: Session) -> Store:
    store = Store(name="Auth Bridge Store", code=f"auth-{uuid.uuid4().hex[:8]}")
    db.add(store)
    db.commit()
    db.refresh(store)
    return store


def test_user_persists_with_null_auth_user_id(db_session: Session) -> None:
    store = _make_store(db_session)
    # `make_user` auto-assigns an auth_user_id since F2.22.2.D; pass None
    # explicitly to exercise the still-nullable column.
    user = make_user(
        db_session, role=UserRole.staff, store_id=store.id, auth_user_id=None
    )
    assert user.auth_user_id is None


def test_user_persists_with_explicit_auth_user_id(db_session: Session) -> None:
    store = _make_store(db_session)
    auth_id = uuid.uuid4()
    user = make_user(
        db_session,
        role=UserRole.staff,
        store_id=store.id,
        auth_user_id=auth_id,
    )
    assert user.auth_user_id == auth_id


def test_duplicate_auth_user_id_is_rejected(db_session: Session) -> None:
    store = _make_store(db_session)
    auth_id = uuid.uuid4()
    make_user(
        db_session,
        role=UserRole.staff,
        store_id=store.id,
        auth_user_id=auth_id,
    )
    with pytest.raises(IntegrityError):
        make_user(
            db_session,
            role=UserRole.staff,
            store_id=store.id,
            auth_user_id=auth_id,
        )
    db_session.rollback()


def test_multiple_null_auth_user_ids_are_allowed(db_session: Session) -> None:
    store = _make_store(db_session)
    # No IntegrityError: a unique index treats NULLs as distinct.
    # `auth_user_id=None` is passed explicitly — `make_user` would
    # otherwise auto-assign a UUID since F2.22.2.D.
    make_user(
        db_session, role=UserRole.staff, store_id=store.id, auth_user_id=None
    )
    make_user(
        db_session, role=UserRole.staff, store_id=store.id, auth_user_id=None
    )
