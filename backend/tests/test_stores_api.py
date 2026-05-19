"""API-level tests for the stores module (F2.14.3 + F2.17.3).

Exercises the FastAPI router via TestClient.

F2.14.3 coverage (kept intact):
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

F2.17.3 additions:
  - `GET /stores`: admin list with filters and pagination; non-admin
    forbidden; query-param bounds validated at the FastAPI layer.
  - `POST /stores`: admin create (201); duplicate code → 422;
    schema `extra="forbid"` rejection of `is_active` / unknown
    fields; non-admin forbidden.
  - `POST /stores/{store_id}/deactivate`,
    `POST /stores/{store_id}/reactivate`: admin-only lifecycle; NOT
    idempotent (already-inactive / already-active → 422); unknown
    store → 404; non-admin → 403.

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

from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user


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


# Thin adapter over tests.helpers.auth.make_user (F2.22.2.C2).
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
        return central_make_user(
            db_session,
            role=role,
            store_id=sid,
            full_name=f"Stores-API {role.value}",
            is_active=True,
            password="supersecret123",
        )

    return _create


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


# --------------------------------------------------------------------- #
# F2.17.3 helpers
# --------------------------------------------------------------------- #


_NON_ADMIN_ROLES = (
    UserRole.owner,
    UserRole.manager,
    UserRole.staff,
    UserRole.driver,
)


STORE_LIST_KEYS = {"items", "total", "limit", "offset"}


# --------------------------------------------------------------------- #
# GET /stores
# --------------------------------------------------------------------- #


def test_list_stores_anonymous_unauthorized(client: TestClient) -> None:
    resp = client.get("/stores")
    assert resp.status_code == 401, resp.text


def test_list_stores_admin_happy_path(
    client: TestClient,
    db_session: Session,
    make_store,
    make_user,
) -> None:
    # Clean slate so the envelope counts are deterministic across runs.
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    make_store(name="List A", code="list-aa")
    make_store(name="List B", code="list-bb")
    admin = make_user(UserRole.admin)

    resp = client.get("/stores", headers=_auth(admin))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == STORE_LIST_KEYS
    assert body["total"] == 2
    assert len(body["items"]) == 2
    for item in body["items"]:
        assert set(item.keys()) == STORE_READ_KEYS


@pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
def test_list_stores_non_admin_forbidden(
    client: TestClient, make_user, role: UserRole
) -> None:
    actor = make_user(role)

    resp = client.get("/stores", headers=_auth(actor))

    assert resp.status_code == 403, resp.text


def test_list_stores_response_envelope_shape(
    client: TestClient,
    db_session: Session,
    make_store,
    make_user,
) -> None:
    make_store()
    admin = make_user(UserRole.admin)

    resp = client.get("/stores", headers=_auth(admin))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body.keys()) == STORE_LIST_KEYS
    assert isinstance(body["items"], list)
    assert isinstance(body["total"], int)
    assert isinstance(body["limit"], int)
    assert isinstance(body["offset"], int)


def test_list_stores_pagination_limit_offset(
    client: TestClient,
    db_session: Session,
    make_store,
    make_user,
) -> None:
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    for i in range(5):
        make_store(name=f"Pag {i}", code=f"pagapi-{i:04d}")
    admin = make_user(UserRole.admin)

    resp = client.get(
        "/stores?limit=2&offset=2", headers=_auth(admin)
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["limit"] == 2
    assert body["offset"] == 2
    assert len(body["items"]) == 2


def test_list_stores_total_is_pre_pagination(
    client: TestClient,
    db_session: Session,
    make_store,
    make_user,
) -> None:
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    for i in range(5):
        make_store(name=f"Tot {i}", code=f"totapi-{i:04d}")
    admin = make_user(UserRole.admin)

    resp = client.get("/stores?limit=2", headers=_auth(admin))

    body = resp.json()
    assert body["total"] == 5
    assert len(body["items"]) == 2


def test_list_stores_filter_is_active_true(
    client: TestClient,
    db_session: Session,
    make_store,
    make_user,
) -> None:
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    make_store(name="API Active", is_active=True)
    make_store(name="API Inactive", is_active=False)
    admin = make_user(UserRole.admin)

    resp = client.get("/stores?is_active=true", headers=_auth(admin))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["is_active"] is True


def test_list_stores_filter_is_active_false(
    client: TestClient,
    db_session: Session,
    make_store,
    make_user,
) -> None:
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    make_store(name="API Active", is_active=True)
    make_store(name="API Inactive", is_active=False)
    admin = make_user(UserRole.admin)

    resp = client.get("/stores?is_active=false", headers=_auth(admin))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["is_active"] is False


def test_list_stores_q_filters_by_name(
    client: TestClient,
    db_session: Session,
    make_store,
    make_user,
) -> None:
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    target = make_store(name="Unique-API-Search", code="api-qq-aaa")
    make_store(name="Other API", code="api-qq-bbb")
    admin = make_user(UserRole.admin)

    resp = client.get(
        "/stores?q=Unique-API-Search", headers=_auth(admin)
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(target.id)


def test_list_stores_q_filters_by_code(
    client: TestClient,
    db_session: Session,
    make_store,
    make_user,
) -> None:
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    target = make_store(name="Plain", code="api-target-zz")
    make_store(name="Other Plain", code="api-other-yy")
    admin = make_user(UserRole.admin)

    resp = client.get(
        "/stores?q=api-target-zz", headers=_auth(admin)
    )

    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["id"] == str(target.id)


def test_list_stores_invalid_limit_zero(
    client: TestClient, make_user
) -> None:
    admin = make_user(UserRole.admin)
    resp = client.get("/stores?limit=0", headers=_auth(admin))
    assert resp.status_code == 422, resp.text


def test_list_stores_invalid_limit_above_max(
    client: TestClient, make_user
) -> None:
    admin = make_user(UserRole.admin)
    resp = client.get("/stores?limit=101", headers=_auth(admin))
    assert resp.status_code == 422, resp.text


def test_list_stores_invalid_negative_offset(
    client: TestClient, make_user
) -> None:
    admin = make_user(UserRole.admin)
    resp = client.get("/stores?offset=-1", headers=_auth(admin))
    assert resp.status_code == 422, resp.text


# --------------------------------------------------------------------- #
# POST /stores
# --------------------------------------------------------------------- #


def test_create_store_anonymous_unauthorized(client: TestClient) -> None:
    resp = client.post(
        "/stores",
        json={"name": "Anon Try", "code": "anon-code"},
    )
    assert resp.status_code == 401, resp.text


def test_create_store_admin_happy_path(
    client: TestClient, make_user
) -> None:
    admin = make_user(UserRole.admin)
    payload = {
        "name": "Brand New API",
        "code": f"api-new-{uuid.uuid4().hex[:6]}",
        "timezone": "America/Chicago",
    }

    resp = client.post("/stores", headers=_auth(admin), json=payload)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["name"] == payload["name"]
    assert body["code"] == payload["code"]
    assert body["timezone"] == "America/Chicago"


def test_create_store_response_shape_is_store_read(
    client: TestClient, make_user
) -> None:
    admin = make_user(UserRole.admin)
    payload = {
        "name": "Shape Check",
        "code": f"api-shape-{uuid.uuid4().hex[:6]}",
    }

    resp = client.post("/stores", headers=_auth(admin), json=payload)

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert set(body.keys()) == STORE_READ_KEYS


def test_create_store_persists_as_active(
    client: TestClient,
    db_session: Session,
    make_user,
) -> None:
    admin = make_user(UserRole.admin)
    code = f"api-active-{uuid.uuid4().hex[:6]}"

    resp = client.post(
        "/stores",
        headers=_auth(admin),
        json={"name": "Active New", "code": code},
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["is_active"] is True

    db_session.expire_all()
    fresh = (
        db_session.query(Store).filter(Store.code == code).one_or_none()
    )
    assert fresh is not None
    assert fresh.is_active is True


def test_create_store_persists_name_code_timezone(
    client: TestClient,
    db_session: Session,
    make_user,
) -> None:
    admin = make_user(UserRole.admin)
    code = f"api-persist-{uuid.uuid4().hex[:6]}"

    client.post(
        "/stores",
        headers=_auth(admin),
        json={
            "name": "Persisted Name",
            "code": code,
            "timezone": "America/Chicago",
        },
    )

    db_session.expire_all()
    fresh = (
        db_session.query(Store).filter(Store.code == code).one_or_none()
    )
    assert fresh is not None
    assert fresh.name == "Persisted Name"
    assert fresh.timezone == "America/Chicago"


def test_create_store_default_timezone(
    client: TestClient, make_user
) -> None:
    admin = make_user(UserRole.admin)

    resp = client.post(
        "/stores",
        headers=_auth(admin),
        json={
            "name": "Default TZ",
            "code": f"api-deftz-{uuid.uuid4().hex[:6]}",
        },
    )

    assert resp.status_code == 201, resp.text
    assert resp.json()["timezone"] == "America/New_York"


def test_create_store_duplicate_code_returns_422(
    client: TestClient,
    make_store,
    make_user,
) -> None:
    existing = make_store(name="First", code="api-dup-code")
    admin = make_user(UserRole.admin)

    resp = client.post(
        "/stores",
        headers=_auth(admin),
        json={"name": "Second", "code": existing.code},
    )

    assert resp.status_code == 422, resp.text


def test_create_store_rejects_unknown_extra(
    client: TestClient, make_user
) -> None:
    admin = make_user(UserRole.admin)

    resp = client.post(
        "/stores",
        headers=_auth(admin),
        json={
            "name": "Stowaway",
            "code": f"api-extra-{uuid.uuid4().hex[:6]}",
            "foo": "bar",
        },
    )

    assert resp.status_code == 422, resp.text


def test_create_store_rejects_is_active_field(
    client: TestClient, make_user
) -> None:
    admin = make_user(UserRole.admin)

    resp = client.post(
        "/stores",
        headers=_auth(admin),
        json={
            "name": "Force Inactive",
            "code": f"api-isactive-{uuid.uuid4().hex[:6]}",
            "is_active": False,
        },
    )

    assert resp.status_code == 422, resp.text


@pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
def test_create_store_non_admin_forbidden(
    client: TestClient,
    db_session: Session,
    make_user,
    role: UserRole,
) -> None:
    actor = make_user(role)

    resp = client.post(
        "/stores",
        headers=_auth(actor),
        json={
            "name": "Should Not Persist",
            "code": f"api-nope-{uuid.uuid4().hex[:6]}",
        },
    )

    assert resp.status_code == 403, resp.text

    db_session.expire_all()
    leaked = (
        db_session.query(Store)
        .filter(Store.name == "Should Not Persist")
        .one_or_none()
    )
    assert leaked is None


# --------------------------------------------------------------------- #
# POST /stores/{store_id}/deactivate
# --------------------------------------------------------------------- #


def test_deactivate_store_anonymous_unauthorized(
    client: TestClient, make_store
) -> None:
    store = make_store()
    resp = client.post(f"/stores/{store.id}/deactivate")
    assert resp.status_code == 401, resp.text


def test_deactivate_store_admin_happy_path(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store(is_active=True)
    admin = make_user(UserRole.admin)

    resp = client.post(
        f"/stores/{store.id}/deactivate", headers=_auth(admin)
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(store.id)
    assert body["is_active"] is False


def test_deactivate_store_response_is_active_false(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store(is_active=True)
    admin = make_user(UserRole.admin)

    resp = client.post(
        f"/stores/{store.id}/deactivate", headers=_auth(admin)
    )

    assert resp.status_code == 200
    assert resp.json()["is_active"] is False


def test_deactivate_store_db_persists(
    client: TestClient,
    db_session: Session,
    make_store,
    make_user,
) -> None:
    store = make_store(is_active=True)
    admin = make_user(UserRole.admin)

    client.post(
        f"/stores/{store.id}/deactivate", headers=_auth(admin)
    )

    db_session.expire_all()
    fresh = db_session.get(Store, store.id)
    assert fresh is not None
    assert fresh.is_active is False


def test_deactivate_store_already_inactive_returns_422(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store(is_active=False)
    admin = make_user(UserRole.admin)

    resp = client.post(
        f"/stores/{store.id}/deactivate", headers=_auth(admin)
    )

    assert resp.status_code == 422, resp.text


def test_deactivate_store_unknown_returns_404(
    client: TestClient, make_user
) -> None:
    admin = make_user(UserRole.admin)

    resp = client.post(
        f"/stores/{uuid.uuid4()}/deactivate", headers=_auth(admin)
    )

    assert resp.status_code == 404, resp.text


@pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
def test_deactivate_store_non_admin_forbidden(
    client: TestClient,
    db_session: Session,
    make_store,
    make_user,
    role: UserRole,
) -> None:
    store = make_store(is_active=True)
    actor = make_user(role, store_id=store.id)

    resp = client.post(
        f"/stores/{store.id}/deactivate", headers=_auth(actor)
    )

    assert resp.status_code == 403, resp.text

    db_session.expire_all()
    fresh = db_session.get(Store, store.id)
    assert fresh is not None
    assert fresh.is_active is True


# --------------------------------------------------------------------- #
# POST /stores/{store_id}/reactivate
# --------------------------------------------------------------------- #


def test_reactivate_store_anonymous_unauthorized(
    client: TestClient, make_store
) -> None:
    store = make_store(is_active=False)
    resp = client.post(f"/stores/{store.id}/reactivate")
    assert resp.status_code == 401, resp.text


def test_reactivate_store_admin_happy_path(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store(is_active=False)
    admin = make_user(UserRole.admin)

    resp = client.post(
        f"/stores/{store.id}/reactivate", headers=_auth(admin)
    )

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == str(store.id)
    assert body["is_active"] is True


def test_reactivate_store_response_is_active_true(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store(is_active=False)
    admin = make_user(UserRole.admin)

    resp = client.post(
        f"/stores/{store.id}/reactivate", headers=_auth(admin)
    )

    assert resp.status_code == 200
    assert resp.json()["is_active"] is True


def test_reactivate_store_db_persists(
    client: TestClient,
    db_session: Session,
    make_store,
    make_user,
) -> None:
    store = make_store(is_active=False)
    admin = make_user(UserRole.admin)

    client.post(
        f"/stores/{store.id}/reactivate", headers=_auth(admin)
    )

    db_session.expire_all()
    fresh = db_session.get(Store, store.id)
    assert fresh is not None
    assert fresh.is_active is True


def test_reactivate_store_already_active_returns_422(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store(is_active=True)
    admin = make_user(UserRole.admin)

    resp = client.post(
        f"/stores/{store.id}/reactivate", headers=_auth(admin)
    )

    assert resp.status_code == 422, resp.text


def test_reactivate_store_unknown_returns_404(
    client: TestClient, make_user
) -> None:
    admin = make_user(UserRole.admin)

    resp = client.post(
        f"/stores/{uuid.uuid4()}/reactivate", headers=_auth(admin)
    )

    assert resp.status_code == 404, resp.text


@pytest.mark.parametrize("role", _NON_ADMIN_ROLES)
def test_reactivate_store_non_admin_forbidden(
    client: TestClient,
    db_session: Session,
    make_store,
    make_user,
    role: UserRole,
) -> None:
    inactive_store = make_store(is_active=False)
    home_store = make_store(is_active=True)
    actor = make_user(role, store_id=home_store.id)

    resp = client.post(
        f"/stores/{inactive_store.id}/reactivate", headers=_auth(actor)
    )

    assert resp.status_code == 403, resp.text

    db_session.expire_all()
    fresh = db_session.get(Store, inactive_store.id)
    assert fresh is not None
    assert fresh.is_active is False


# --------------------------------------------------------------------- #
# Route collision regression (F2.17.3)
# --------------------------------------------------------------------- #


def test_route_get_stores_does_not_collide_with_get_by_id(
    client: TestClient,
    db_session: Session,
    make_store,
    make_user,
) -> None:
    """`GET /stores` must resolve to the admin list endpoint, not be
    misinterpreted as `GET /stores/{store_id}` with `store_id="stores"`.
    """
    db_session.query(User).delete()
    db_session.query(Store).delete()
    db_session.commit()

    make_store()
    admin = make_user(UserRole.admin)

    resp = client.get("/stores", headers=_auth(admin))

    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Envelope shape, not a single StoreRead.
    assert set(body.keys()) == STORE_LIST_KEYS
    assert "id" not in body  # would indicate misroute to /{store_id}


def test_route_post_deactivate_does_not_collide_with_item_routes(
    client: TestClient, make_store, make_user
) -> None:
    """`POST /stores/{id}/deactivate` must resolve to the lifecycle
    endpoint, not GET/PATCH the store. Asserted by verifying the
    side-effect (is_active flipped) only the lifecycle endpoint
    produces — a mis-routed PATCH would return 405 or attempt the
    detail handler, neither of which flips the flag.
    """
    store = make_store(is_active=True)
    admin = make_user(UserRole.admin)

    resp = client.post(
        f"/stores/{store.id}/deactivate", headers=_auth(admin)
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["is_active"] is False

    # Companion: GET /stores/{id} still returns the (now inactive)
    # store via the admin path — the item endpoint exists and is
    # reachable, which proves the lifecycle path did not shadow it.
    # Inactive stores return 400 via require_store_member; that's
    # the documented item-endpoint behaviour.
    detail = client.get(f"/stores/{store.id}", headers=_auth(admin))
    assert detail.status_code == 400


def test_route_post_reactivate_does_not_collide_with_item_routes(
    client: TestClient, make_store, make_user
) -> None:
    store = make_store(is_active=False)
    admin = make_user(UserRole.admin)

    resp = client.post(
        f"/stores/{store.id}/reactivate", headers=_auth(admin)
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["is_active"] is True

    detail = client.get(f"/stores/{store.id}", headers=_auth(admin))
    assert detail.status_code == 200
