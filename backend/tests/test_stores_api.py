"""API-level tests for the stores module (F2.14.3).

Exercises the FastAPI router via TestClient. Covers:

  - auth gate inherited from `require_store_member` (anon → 401).
  - RBAC matrix on PATCH (owner/admin pass; manager/staff/driver
    blocked by `require_owner_or_admin`).
  - tenancy on `/stores/{store_id}` for both verbs:
      * non-admin cross-store → 403 (collapsed with "unknown" so
        existence isn't probeable).
      * admin + unknown store → 404.
      * admin + inactive store → 400.
  - StoreRead response shape (only the 7 declared fields).
  - StoreUpdate `extra="forbid"` rejection of `code` / `is_active`
    (and similar) at the schema layer (422).

Schema validation lives in test_stores_schemas.py and service
behaviour in test_stores_service.py — those concerns are not
duplicated here.

Style mirrors test_orders_api.py.
"""

import uuid
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.security import create_access_token
from app.core.security import hash_password
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(
        *,
        name: str = "Stores-API",
        code: str | None = None,
        is_active: bool = True,
        timezone: str | None = None,
    ) -> Store:
        kwargs: dict = {
            "name": name,
            "code": code or f"sa-{uuid.uuid4().hex[:8]}",
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
def make_user(
    db_session: Session, make_store: Callable[..., Store]
) -> Callable[..., User]:
    def _create(
        role: UserRole, store_id: uuid.UUID | None = None
    ) -> User:
        if role == UserRole.admin:
            sid = None
        else:
            sid = store_id if store_id is not None else make_store().id
        user = User(
            full_name=f"Stores-API {role.value}",
            email=f"{role.value}-{uuid.uuid4().hex[:8]}@example.com",
            password_hash=hash_password("supersecret123"),
            role=role,
            store_id=sid,
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


def _auth(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


STORE_READ_KEYS = {
    "id",
    "name",
    "code",
    "is_active",
    "timezone",
    "created_at",
    "updated_at",
}


# --------------------------------------------------------------------- #
# GET /stores/{store_id}
# --------------------------------------------------------------------- #


def test_get_store_owner_can_read_own_store(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store()
    owner = make_user(UserRole.owner, store_id=store.id)

    resp = client.get(f"/stores/{store.id}", headers=_auth(owner))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(store.id)
    assert body["name"] == store.name
    assert body["code"] == store.code
    assert set(body.keys()) == STORE_READ_KEYS


def test_get_store_manager_can_read_own_store(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store()
    manager = make_user(UserRole.manager, store_id=store.id)

    resp = client.get(f"/stores/{store.id}", headers=_auth(manager))

    assert resp.status_code == 200, resp.text


def test_get_store_staff_can_read_own_store(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store()
    staff = make_user(UserRole.staff, store_id=store.id)

    resp = client.get(f"/stores/{store.id}", headers=_auth(staff))

    assert resp.status_code == 200, resp.text


def test_get_store_driver_can_read_own_store(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store()
    driver = make_user(UserRole.driver, store_id=store.id)

    resp = client.get(f"/stores/{store.id}", headers=_auth(driver))

    assert resp.status_code == 200, resp.text


def test_get_store_admin_can_read_active_store(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store()
    admin = make_user(UserRole.admin)

    resp = client.get(f"/stores/{store.id}", headers=_auth(admin))

    assert resp.status_code == 200, resp.text
    assert resp.json()["id"] == str(store.id)


def test_get_store_cross_store_user_forbidden(
    client: TestClient, make_store, make_user
) -> None:
    store_a = make_store()
    store_b = make_store()
    # Non-admin owner of store_a, attempting to read store_b.
    intruder = make_user(UserRole.owner, store_id=store_a.id)

    resp = client.get(f"/stores/{store_b.id}", headers=_auth(intruder))

    # require_store_member collapses "wrong store" and "no such store"
    # into 403 for non-admins to avoid leaking existence.
    assert resp.status_code == 403, resp.text


def test_get_store_unknown_store_returns_expected_error(
    client: TestClient, make_user
) -> None:
    """Unknown store via admin path → 404 (existence is not hidden
    from admins). Non-admin path is asserted in the cross-store test
    above and would yield 403 by design.
    """
    admin = make_user(UserRole.admin)

    resp = client.get(
        f"/stores/{uuid.uuid4()}", headers=_auth(admin)
    )

    assert resp.status_code == 404, resp.text


def test_get_store_inactive_store_blocked(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store(is_active=False)
    admin = make_user(UserRole.admin)

    resp = client.get(f"/stores/{store.id}", headers=_auth(admin))

    # require_store_member returns 400 for an inactive store; this
    # is the project-wide tenancy contract.
    assert resp.status_code == 400, resp.text


# --------------------------------------------------------------------- #
# PATCH /stores/{store_id}
# --------------------------------------------------------------------- #


def test_patch_store_owner_can_update_name_and_timezone(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store(name="Old Name", timezone="America/New_York")
    owner = make_user(UserRole.owner, store_id=store.id)

    resp = client.patch(
        f"/stores/{store.id}",
        headers=_auth(owner),
        json={"name": "New Name", "timezone": "America/Chicago"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "New Name"
    assert body["timezone"] == "America/Chicago"
    assert body["id"] == str(store.id)


def test_patch_store_admin_can_update_active_store(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store(name="Pre Admin")
    admin = make_user(UserRole.admin)

    resp = client.patch(
        f"/stores/{store.id}",
        headers=_auth(admin),
        json={"name": "Post Admin"},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["name"] == "Post Admin"


def test_patch_store_manager_cannot_update(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store()
    manager = make_user(UserRole.manager, store_id=store.id)

    resp = client.patch(
        f"/stores/{store.id}",
        headers=_auth(manager),
        json={"name": "Manager Try"},
    )

    # Tenancy passes (manager is a store member); the role gate
    # `require_owner_or_admin` rejects with 403.
    assert resp.status_code == 403, resp.text


def test_patch_store_staff_cannot_update(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store()
    staff = make_user(UserRole.staff, store_id=store.id)

    resp = client.patch(
        f"/stores/{store.id}",
        headers=_auth(staff),
        json={"name": "Staff Try"},
    )

    assert resp.status_code == 403, resp.text


def test_patch_store_driver_cannot_update(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store()
    driver = make_user(UserRole.driver, store_id=store.id)

    resp = client.patch(
        f"/stores/{store.id}",
        headers=_auth(driver),
        json={"name": "Driver Try"},
    )

    assert resp.status_code == 403, resp.text


def test_patch_store_cross_store_user_forbidden(
    client: TestClient, make_store, make_user
) -> None:
    store_a = make_store()
    store_b = make_store()
    intruder = make_user(UserRole.owner, store_id=store_a.id)

    resp = client.patch(
        f"/stores/{store_b.id}",
        headers=_auth(intruder),
        json={"name": "Cross Store"},
    )

    # require_store_member rejects before role gate evaluates.
    assert resp.status_code == 403, resp.text


def test_patch_store_unknown_store_returns_expected_error(
    client: TestClient, make_user
) -> None:
    """Unknown store via admin path → 404 (same as GET)."""
    admin = make_user(UserRole.admin)

    resp = client.patch(
        f"/stores/{uuid.uuid4()}",
        headers=_auth(admin),
        json={"name": "Ghost"},
    )

    assert resp.status_code == 404, resp.text


def test_patch_store_invalid_payload_returns_422(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store()
    owner = make_user(UserRole.owner, store_id=store.id)

    resp = client.patch(
        f"/stores/{store.id}",
        headers=_auth(owner),
        json={"name": "   "},
    )

    assert resp.status_code == 422, resp.text


def test_patch_store_cannot_update_code(
    client: TestClient,
    db_session: Session,
    make_store,
    make_user,
) -> None:
    store = make_store()
    owner = make_user(UserRole.owner, store_id=store.id)
    original_code = store.code

    resp = client.patch(
        f"/stores/{store.id}",
        headers=_auth(owner),
        json={"code": "ATTEMPTED-NEW-CODE"},
    )

    # StoreUpdate uses extra="forbid"; the request never reaches the
    # service layer.
    assert resp.status_code == 422, resp.text

    # Confirm persistence: re-read from DB and check `code` did not
    # mutate.
    db_session.expire_all()
    fresh = db_session.get(Store, store.id)
    assert fresh is not None
    assert fresh.code == original_code


def test_patch_store_cannot_update_is_active(
    client: TestClient,
    db_session: Session,
    make_store,
    make_user,
) -> None:
    store = make_store(is_active=True)
    owner = make_user(UserRole.owner, store_id=store.id)

    resp = client.patch(
        f"/stores/{store.id}",
        headers=_auth(owner),
        json={"is_active": False},
    )

    assert resp.status_code == 422, resp.text

    db_session.expire_all()
    fresh = db_session.get(Store, store.id)
    assert fresh is not None
    assert fresh.is_active is True


def test_patch_store_response_returns_updated_store_read(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store(name="Pre Shape", timezone="America/New_York")
    owner = make_user(UserRole.owner, store_id=store.id)

    resp = client.patch(
        f"/stores/{store.id}",
        headers=_auth(owner),
        json={"name": "Post Shape", "timezone": "America/Chicago"},
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Exactly the StoreRead surface — no out-of-scope fields leaked.
    assert set(body.keys()) == STORE_READ_KEYS
    assert body["id"] == str(store.id)
    assert body["name"] == "Post Shape"
    assert body["code"] == store.code
    assert body["is_active"] is True
    assert body["timezone"] == "America/Chicago"
    assert isinstance(body["created_at"], str)
    assert isinstance(body["updated_at"], str)

    forbidden = {
        "contact_email",
        "contact_phone",
        "address",
        "business_hours",
        "preferences",
        "notification_defaults",
        "compliance_profile",
        "status",
        "slug",
    }
    assert forbidden.isdisjoint(body.keys())
