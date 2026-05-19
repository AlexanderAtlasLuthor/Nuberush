"""Service-layer tests for the stores module (F2.14.2 + F2.17.2).

Exercises `app.services.stores` against the real test DB via the
`db_session` fixture from conftest.

F2.14.2 (kept intact):
  - `get_store` returns existing rows and 404s on unknown UUIDs.
  - `update_store` mutates only the fields the caller sent
    (`name`, `timezone`) and leaves the read-only / non-editable
    columns intact (`id`, `code`, `is_active`, `created_at`,
    `updated_at`).
  - Empty PATCH payloads are a no-op against the editable fields.
  - Changes are committed (visible in a fresh fetch from the DB).
  - 404 path on `update_store` for a missing store id.

F2.17.2 additions:
  - `list_stores`: admin-only, filters (is_active, q), pagination
    bounds, sort (`created_at DESC`, `id ASC` tie-breaker).
  - `create_store`: admin-only, persists name/code/timezone,
    `is_active=True` on creation, duplicate-code path returns 422.
  - `deactivate_store` / `reactivate_store`: admin-only, NOT
    idempotent (already-inactive / already-active → 422), unknown
    store → 404.

API-level matrices (RBAC, tenancy via TestClient) live in F2.17.3
by design — see prompt's "Do not duplicate router/API tests here".

Style mirrors tests/test_users_service.py and
tests/test_inventory_services.py.
"""

import uuid
from typing import Callable
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.stores import StoreCreate
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


@pytest.fixture
def make_user(db_session: Session) -> Callable[..., User]:
    """Create a User row for actor-based RBAC tests.

    Admin users default to `store_id=None` (the platform invariant).
    Non-admin roles must be given a `store_id`; the F2.17.2 service
    rules under test do not consult the store anyway, but we attach
    one to keep test users plausible against the production schema.
    """

    def _create(
        *,
        role: UserRole,
        store_id: UUID | None = None,
        is_active: bool = True,
        full_name: str | None = None,
        email: str | None = None,
    ) -> User:
        user = User(
            full_name=full_name or f"User {role.value}",
            email=email or f"{role.value}-{uuid.uuid4().hex[:10]}@example.com",
            role=role,
            store_id=store_id,
            is_active=is_active,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


@pytest.fixture
def admin_user(make_user: Callable[..., User]) -> User:
    return make_user(role=UserRole.admin, store_id=None)


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


# --------------------------------------------------------------------- #
# list_stores — RBAC
# --------------------------------------------------------------------- #


_NON_ADMIN_ROLES = (
    UserRole.owner,
    UserRole.manager,
    UserRole.staff,
    UserRole.driver,
)


def test_list_stores_admin_can_list(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    make_store(name="Store A")
    make_store(name="Store B")
    make_store(name="Store C")

    result = svc.list_stores(db_session, actor=admin_user)

    assert result.total >= 3
    listed_names = {s.name for s in result.items}
    assert {"Store A", "Store B", "Store C"} <= listed_names


@pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
def test_list_stores_non_admin_forbidden(
    db_session: Session,
    make_store: Callable[..., Store],
    make_user: Callable[..., User],
    role: UserRole,
) -> None:
    store = make_store()
    actor = make_user(role=role, store_id=store.id)

    with pytest.raises(HTTPException) as exc_info:
        svc.list_stores(db_session, actor=actor)

    assert exc_info.value.status_code == 403


# --------------------------------------------------------------------- #
# list_stores — pagination
# --------------------------------------------------------------------- #


def test_list_stores_pagination_returns_correct_slice(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    # Wipe pre-existing rows so the slice math is deterministic.
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    for i in range(5):
        make_store(name=f"Paginated {i}", code=f"pag-{i:04d}")

    page = svc.list_stores(db_session, actor=admin_user, limit=2, offset=2)

    assert page.limit == 2
    assert page.offset == 2
    assert len(page.items) == 2


def test_list_stores_total_is_pre_pagination(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    for i in range(5):
        make_store(name=f"Total {i}", code=f"tot-{i:04d}")

    page = svc.list_stores(db_session, actor=admin_user, limit=2, offset=0)

    assert page.total == 5
    assert len(page.items) == 2


def test_list_stores_limit_one_works(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    make_store()
    make_store()

    page = svc.list_stores(db_session, actor=admin_user, limit=1, offset=0)

    assert len(page.items) == 1
    assert page.limit == 1


def test_list_stores_limit_one_hundred_works(
    db_session: Session,
    admin_user: User,
) -> None:
    page = svc.list_stores(db_session, actor=admin_user, limit=100, offset=0)

    assert page.limit == 100


def test_list_stores_rejects_limit_zero(
    db_session: Session,
    admin_user: User,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        svc.list_stores(db_session, actor=admin_user, limit=0)

    assert exc_info.value.status_code == 422


def test_list_stores_rejects_limit_above_max(
    db_session: Session,
    admin_user: User,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        svc.list_stores(db_session, actor=admin_user, limit=101)

    assert exc_info.value.status_code == 422


def test_list_stores_rejects_negative_offset(
    db_session: Session,
    admin_user: User,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        svc.list_stores(db_session, actor=admin_user, offset=-1)

    assert exc_info.value.status_code == 422


# --------------------------------------------------------------------- #
# list_stores — filters
# --------------------------------------------------------------------- #


def test_list_stores_filters_by_is_active_true(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    make_store(name="Active 1", is_active=True)
    make_store(name="Active 2", is_active=True)
    make_store(name="Inactive 1", is_active=False)

    page = svc.list_stores(db_session, actor=admin_user, is_active=True)

    assert page.total == 2
    assert all(item.is_active for item in page.items)


def test_list_stores_filters_by_is_active_false(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    make_store(name="Active 1", is_active=True)
    make_store(name="Inactive 1", is_active=False)
    make_store(name="Inactive 2", is_active=False)

    page = svc.list_stores(db_session, actor=admin_user, is_active=False)

    assert page.total == 2
    assert all(not item.is_active for item in page.items)


def test_list_stores_q_filters_by_name(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    target = make_store(name="Unique-Search-Name", code="ucode-aaa")
    make_store(name="Other", code="ucode-bbb")

    page = svc.list_stores(
        db_session, actor=admin_user, q="Unique-Search-Name"
    )

    assert page.total == 1
    assert page.items[0].id == target.id


def test_list_stores_q_filters_by_code(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    target = make_store(name="Plain-Name", code="search-target-zz")
    make_store(name="Plain-Other", code="other-yy")

    page = svc.list_stores(
        db_session, actor=admin_user, q="search-target-zz"
    )

    assert page.total == 1
    assert page.items[0].id == target.id


def test_list_stores_q_is_trimmed(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    target = make_store(name="Trim-Test-Match", code="trimcode-aa")
    make_store(name="No-Match", code="trimcode-bb")

    page = svc.list_stores(
        db_session, actor=admin_user, q="  Trim-Test-Match  "
    )

    assert page.total == 1
    assert page.items[0].id == target.id


def test_list_stores_whitespace_only_q_disables_filter(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    make_store(name="A", code="wsq-aa")
    make_store(name="B", code="wsq-bb")

    page = svc.list_stores(db_session, actor=admin_user, q="   ")

    assert page.total == 2


# --------------------------------------------------------------------- #
# list_stores — sorting
# --------------------------------------------------------------------- #


def test_list_stores_sort_created_at_desc(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    from datetime import UTC, datetime, timedelta

    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    older = make_store(name="Older", code="sort-aa")
    middle = make_store(name="Middle", code="sort-bb")
    newest = make_store(name="Newest", code="sort-cc")

    # Force distinct timestamps so the sort is exercised on
    # `created_at` rather than the id-asc tie-breaker. Insert order
    # otherwise lands within sub-microsecond DB granularity on fast
    # local hardware.
    base = datetime.now(UTC) - timedelta(minutes=10)
    older.created_at = base
    middle.created_at = base + timedelta(minutes=1)
    newest.created_at = base + timedelta(minutes=2)
    db_session.commit()
    for store in (older, middle, newest):
        db_session.refresh(store)

    page = svc.list_stores(db_session, actor=admin_user)

    ids = [item.id for item in page.items]
    assert ids.index(newest.id) < ids.index(middle.id)
    assert ids.index(middle.id) < ids.index(older.id)


def test_list_stores_id_asc_tie_breaker(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    a = make_store(name="Tie A", code="tie-aa")
    b = make_store(name="Tie B", code="tie-bb")

    shared_ts = a.created_at
    b.created_at = shared_ts
    db_session.commit()
    db_session.refresh(a)
    db_session.refresh(b)

    page = svc.list_stores(db_session, actor=admin_user)
    ids_in_order = [item.id for item in page.items]

    a_idx = ids_in_order.index(a.id)
    b_idx = ids_in_order.index(b.id)
    # With matching created_at, the row with the smaller id must come first.
    expected_first = min(a.id, b.id)
    assert ids_in_order[min(a_idx, b_idx)] == expected_first


# --------------------------------------------------------------------- #
# create_store — happy path
# --------------------------------------------------------------------- #


def test_create_store_admin_happy_path(
    db_session: Session,
    admin_user: User,
) -> None:
    payload = StoreCreate(
        name="Brand New",
        code=f"new-{uuid.uuid4().hex[:8]}",
        timezone="America/Chicago",
    )

    created = svc.create_store(db_session, actor=admin_user, payload=payload)

    assert created.id is not None
    assert created.name == "Brand New"
    assert created.code == payload.code
    assert created.timezone == "America/Chicago"


def test_create_store_persists_as_active(
    db_session: Session,
    admin_user: User,
) -> None:
    payload = StoreCreate(name="Active Newcomer", code=f"act-{uuid.uuid4().hex[:8]}")

    created = svc.create_store(db_session, actor=admin_user, payload=payload)

    assert created.is_active is True

    db_session.expire_all()
    fresh = db_session.scalar(select(Store).where(Store.id == created.id))
    assert fresh is not None
    assert fresh.is_active is True


def test_create_store_persists_name_code_timezone(
    db_session: Session,
    admin_user: User,
) -> None:
    code = f"persist-{uuid.uuid4().hex[:8]}"
    payload = StoreCreate(name="Persist Me", code=code, timezone="America/Chicago")

    created = svc.create_store(db_session, actor=admin_user, payload=payload)

    db_session.expire_all()
    fresh = db_session.scalar(select(Store).where(Store.id == created.id))
    assert fresh is not None
    assert fresh.name == "Persist Me"
    assert fresh.code == code
    assert fresh.timezone == "America/Chicago"


def test_create_store_applies_default_timezone(
    db_session: Session,
    admin_user: User,
) -> None:
    payload = StoreCreate(name="Default TZ", code=f"deftz-{uuid.uuid4().hex[:8]}")

    created = svc.create_store(db_session, actor=admin_user, payload=payload)

    assert created.timezone == "America/New_York"


# --------------------------------------------------------------------- #
# create_store — duplicate code
# --------------------------------------------------------------------- #


def test_create_store_duplicate_code_returns_422(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    existing = make_store(name="First", code="duplicate-code")
    payload = StoreCreate(name="Second", code=existing.code)

    with pytest.raises(HTTPException) as exc_info:
        svc.create_store(db_session, actor=admin_user, payload=payload)

    assert exc_info.value.status_code == 422


def test_create_store_duplicate_code_rolls_back(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    existing = make_store(name="Original", code="rollback-code")
    payload = StoreCreate(name="Twin Attempt", code=existing.code)

    with pytest.raises(HTTPException):
        svc.create_store(db_session, actor=admin_user, payload=payload)

    # The failed attempt must not leave an orphan with the duplicate name.
    db_session.expire_all()
    rows = db_session.scalars(
        select(Store).where(Store.name == "Twin Attempt")
    ).all()
    assert rows == []

    # Session still usable: a new create succeeds afterwards.
    follow_up = svc.create_store(
        db_session,
        actor=admin_user,
        payload=StoreCreate(name="Recovered", code="rollback-code-2"),
    )
    assert follow_up.name == "Recovered"


# --------------------------------------------------------------------- #
# create_store — RBAC
# --------------------------------------------------------------------- #


@pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
def test_create_store_non_admin_forbidden(
    db_session: Session,
    make_store: Callable[..., Store],
    make_user: Callable[..., User],
    role: UserRole,
) -> None:
    store = make_store()
    actor = make_user(role=role, store_id=store.id)
    payload = StoreCreate(name="Should Not Persist", code=f"nope-{uuid.uuid4().hex[:8]}")

    with pytest.raises(HTTPException) as exc_info:
        svc.create_store(db_session, actor=actor, payload=payload)

    assert exc_info.value.status_code == 403

    db_session.expire_all()
    rows = db_session.scalars(
        select(Store).where(Store.name == "Should Not Persist")
    ).all()
    assert rows == []


# --------------------------------------------------------------------- #
# deactivate_store
# --------------------------------------------------------------------- #


def test_deactivate_store_admin_happy_path(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    store = make_store(is_active=True)

    result = svc.deactivate_store(
        db_session, actor=admin_user, store_id=store.id
    )

    assert result.id == store.id
    assert result.is_active is False


def test_deactivate_store_persists(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    store = make_store(is_active=True)

    svc.deactivate_store(db_session, actor=admin_user, store_id=store.id)

    db_session.expire_all()
    fresh = db_session.scalar(select(Store).where(Store.id == store.id))
    assert fresh is not None
    assert fresh.is_active is False


def test_deactivate_store_already_inactive_returns_422(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    store = make_store(is_active=False)

    with pytest.raises(HTTPException) as exc_info:
        svc.deactivate_store(
            db_session, actor=admin_user, store_id=store.id
        )

    assert exc_info.value.status_code == 422


def test_deactivate_store_unknown_store_returns_404(
    db_session: Session,
    admin_user: User,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        svc.deactivate_store(
            db_session, actor=admin_user, store_id=uuid.uuid4()
        )

    assert exc_info.value.status_code == 404


@pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
def test_deactivate_store_non_admin_forbidden(
    db_session: Session,
    make_store: Callable[..., Store],
    make_user: Callable[..., User],
    role: UserRole,
) -> None:
    store = make_store(is_active=True)
    actor = make_user(role=role, store_id=store.id)

    with pytest.raises(HTTPException) as exc_info:
        svc.deactivate_store(db_session, actor=actor, store_id=store.id)

    assert exc_info.value.status_code == 403

    db_session.expire_all()
    fresh = db_session.scalar(select(Store).where(Store.id == store.id))
    assert fresh is not None
    assert fresh.is_active is True


# --------------------------------------------------------------------- #
# reactivate_store
# --------------------------------------------------------------------- #


def test_reactivate_store_admin_happy_path(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    store = make_store(is_active=False)

    result = svc.reactivate_store(
        db_session, actor=admin_user, store_id=store.id
    )

    assert result.id == store.id
    assert result.is_active is True


def test_reactivate_store_persists(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    store = make_store(is_active=False)

    svc.reactivate_store(db_session, actor=admin_user, store_id=store.id)

    db_session.expire_all()
    fresh = db_session.scalar(select(Store).where(Store.id == store.id))
    assert fresh is not None
    assert fresh.is_active is True


def test_reactivate_store_already_active_returns_422(
    db_session: Session,
    make_store: Callable[..., Store],
    admin_user: User,
) -> None:
    store = make_store(is_active=True)

    with pytest.raises(HTTPException) as exc_info:
        svc.reactivate_store(
            db_session, actor=admin_user, store_id=store.id
        )

    assert exc_info.value.status_code == 422


def test_reactivate_store_unknown_store_returns_404(
    db_session: Session,
    admin_user: User,
) -> None:
    with pytest.raises(HTTPException) as exc_info:
        svc.reactivate_store(
            db_session, actor=admin_user, store_id=uuid.uuid4()
        )

    assert exc_info.value.status_code == 404


@pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
def test_reactivate_store_non_admin_forbidden(
    db_session: Session,
    make_store: Callable[..., Store],
    make_user: Callable[..., User],
    role: UserRole,
) -> None:
    inactive_store = make_store(is_active=False)
    # Non-admin actors need a separate store to be plausible — attaching
    # them to the inactive target would itself violate non-admin
    # invariants in some fixtures. We use a second active store.
    home_store = make_store(is_active=True)
    actor = make_user(role=role, store_id=home_store.id)

    with pytest.raises(HTTPException) as exc_info:
        svc.reactivate_store(
            db_session, actor=actor, store_id=inactive_store.id
        )

    assert exc_info.value.status_code == 403

    db_session.expire_all()
    fresh = db_session.scalar(
        select(Store).where(Store.id == inactive_store.id)
    )
    assert fresh is not None
    assert fresh.is_active is False
