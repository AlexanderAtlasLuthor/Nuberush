"""Service-layer tests for the stores module (F2.14.2).

Exercises `app.services.stores` against the real test DB via the
`db_session` fixture from conftest. Covers:

  - `get_store` returns existing rows and 404s on unknown UUIDs.
  - `update_store` mutates only the fields the caller sent
    (`name`, `timezone`) and leaves the read-only / non-editable
    columns intact (`id`, `code`, `is_active`, `created_at`,
    `updated_at`).
  - Empty PATCH payloads are a no-op against the editable fields.
  - Changes are committed (visible in a fresh fetch from the DB).
  - 404 path on `update_store` for a missing store id.

API-level matrices (RBAC, tenancy via TestClient) live in F2.14.3
by design — see prompt's "Do not duplicate router/API tests here".

Style mirrors tests/test_inventory_services.py.
"""

import uuid
from typing import Callable

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Store
from app.schemas.stores import StoreUpdate
from app.services import stores as svc


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    """Create a Store row and return it.

    Defaults work for every assertion in this file. Callers may
    override fields when a test needs a specific starting point.
    """

    def _create(
        *,
        name: str = "Stores-Svc",
        code: str | None = None,
        timezone: str | None = None,
        is_active: bool = True,
    ) -> Store:
        kwargs: dict = {
            "name": name,
            "code": code or f"ss-{uuid.uuid4().hex[:8]}",
            "is_active": is_active,
        }
        if timezone is not None:
            kwargs["timezone"] = timezone
        store = Store(**kwargs)
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


# --------------------------------------------------------------------- #
# get_store
# --------------------------------------------------------------------- #


def test_get_store_returns_existing_store(
    db_session: Session, make_store: Callable[..., Store]
) -> None:
    store = make_store()

    fetched = svc.get_store(db_session, store.id)

    assert fetched.id == store.id
    assert fetched.name == store.name
    assert fetched.code == store.code


def test_get_store_raises_404_for_unknown_store(db_session: Session) -> None:
    with pytest.raises(HTTPException) as exc_info:
        svc.get_store(db_session, uuid.uuid4())

    assert exc_info.value.status_code == 404


# --------------------------------------------------------------------- #
# update_store — happy path
# --------------------------------------------------------------------- #


def test_update_store_updates_name(
    db_session: Session, make_store: Callable[..., Store]
) -> None:
    store = make_store(name="Old Name", timezone="America/New_York")
    original_timezone = store.timezone

    updated = svc.update_store(
        db_session, store.id, StoreUpdate(name="New Name")
    )

    assert updated.name == "New Name"
    assert updated.timezone == original_timezone


def test_update_store_updates_timezone(
    db_session: Session, make_store: Callable[..., Store]
) -> None:
    store = make_store(name="Stable Name", timezone="America/New_York")
    original_name = store.name

    updated = svc.update_store(
        db_session, store.id, StoreUpdate(timezone="America/Chicago")
    )

    assert updated.timezone == "America/Chicago"
    assert updated.name == original_name


def test_update_store_updates_name_and_timezone(
    db_session: Session, make_store: Callable[..., Store]
) -> None:
    store = make_store(name="Old Name", timezone="America/New_York")

    updated = svc.update_store(
        db_session,
        store.id,
        StoreUpdate(name="Both Updated", timezone="America/Chicago"),
    )

    assert updated.name == "Both Updated"
    assert updated.timezone == "America/Chicago"


def test_update_store_allows_empty_payload_without_changing_fields(
    db_session: Session, make_store: Callable[..., Store]
) -> None:
    store = make_store(name="Untouched", timezone="America/New_York")
    original_name = store.name
    original_timezone = store.timezone
    original_code = store.code
    original_is_active = store.is_active

    updated = svc.update_store(db_session, store.id, StoreUpdate())

    assert updated.name == original_name
    assert updated.timezone == original_timezone
    assert updated.code == original_code
    assert updated.is_active == original_is_active


# --------------------------------------------------------------------- #
# update_store — protected fields
# --------------------------------------------------------------------- #


def test_update_store_does_not_change_code(
    db_session: Session, make_store: Callable[..., Store]
) -> None:
    store = make_store()
    original_code = store.code

    updated = svc.update_store(
        db_session,
        store.id,
        StoreUpdate(name="Anything", timezone="America/Chicago"),
    )

    assert updated.code == original_code


def test_update_store_does_not_change_is_active(
    db_session: Session, make_store: Callable[..., Store]
) -> None:
    store = make_store(is_active=True)
    original_is_active = store.is_active

    updated = svc.update_store(
        db_session,
        store.id,
        StoreUpdate(name="Anything", timezone="America/Chicago"),
    )

    assert updated.is_active is original_is_active


# --------------------------------------------------------------------- #
# update_store — persistence + 404
# --------------------------------------------------------------------- #


def test_update_store_persists_changes(
    db_session: Session, make_store: Callable[..., Store]
) -> None:
    store = make_store(name="Before", timezone="America/New_York")
    target_id = store.id

    svc.update_store(
        db_session,
        target_id,
        StoreUpdate(name="After", timezone="America/Chicago"),
    )

    # Drop the in-session identity-map copy and re-read from the DB
    # so the assertions cannot be satisfied by stale ORM state.
    db_session.expire_all()
    fresh = db_session.scalar(select(Store).where(Store.id == target_id))
    assert fresh is not None
    assert fresh.name == "After"
    assert fresh.timezone == "America/Chicago"


def test_update_store_raises_404_for_unknown_store(
    db_session: Session,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        svc.update_store(
            db_session, uuid.uuid4(), StoreUpdate(name="Whatever")
        )

    assert exc_info.value.status_code == 404
