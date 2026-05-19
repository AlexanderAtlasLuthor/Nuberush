"""Tests pinning the S2.4 RBAC contract on real auth endpoints.

These complement the matrix tests in test_register_security.py: they don't
re-run the full creation matrix, they only verify which alias actually gates
each endpoint. If someone in a future session swaps require_manager_or_above
for a different alias on /auth/users, these tests fail loudly.
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(code: str | None = None) -> Store:
        store = Store(name="S24", code=code or f"s24-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


# Thin adapter over tests.helpers.auth.make_user (F2.22.2.C2).
@pytest.fixture
def make_user(db_session: Session) -> Callable[..., User]:
    def _create(
        role: UserRole,
        store_id: uuid.UUID | None = None,
        email: str | None = None,
    ) -> User:
        return central_make_user(
            db_session,
            role=role,
            store_id=store_id,
            email=email,
            full_name=f"S24 {role.value}",
        )

    return _create


def _create_user_body(
    role: UserRole, store_id: uuid.UUID | None = None
) -> dict:
    return {
        "full_name": f"target-{role.value}",
        "email": f"target-{uuid.uuid4().hex[:8]}@example.com",
        "password": "supersecret123",
        "role": role.value,
        "store_id": str(store_id) if store_id else None,
    }


# ---------------------------------------------------------------------------
# /auth/users — gate is require_manager_or_above
# ---------------------------------------------------------------------------


class TestCreateUserGate:
    def test_anonymous_returns_401(self, client: TestClient):
        resp = client.post(
            "/auth/users", json=_create_user_body(UserRole.staff)
        )
        assert resp.status_code == 401
        assert resp.headers.get("www-authenticate", "").lower() == "bearer"

    def test_staff_is_blocked_by_alias(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        staff = make_user(UserRole.staff, store_id=store.id)
        resp = client.post(
            "/auth/users",
            json=_create_user_body(UserRole.staff, store.id),
            headers=_auth(staff),
        )
        assert resp.status_code == 403

    def test_driver_is_blocked_by_alias(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        driver = make_user(UserRole.driver, store_id=store.id)
        resp = client.post(
            "/auth/users",
            json=_create_user_body(UserRole.staff, store.id),
            headers=_auth(driver),
        )
        assert resp.status_code == 403


class TestCreateUserMatrixStillEnforced:
    """Sanity check: the alias gate didn't replace the fine-grained matrix."""

    def test_admin_still_blocked_from_creating_admin(
        self, client: TestClient, make_store, make_user
    ):
        admin = make_user(UserRole.admin, store_id=None)
        resp = client.post(
            "/auth/users",
            json=_create_user_body(UserRole.admin, None),
            headers=_auth(admin),
        )
        assert resp.status_code == 403
        assert "admin" in resp.json()["detail"].lower()

    def test_owner_still_blocked_from_creating_owner(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)
        resp = client.post(
            "/auth/users",
            json=_create_user_body(UserRole.owner, store.id),
            headers=_auth(owner),
        )
        assert resp.status_code == 403

    def test_manager_still_blocked_from_creating_manager(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        manager = make_user(UserRole.manager, store_id=store.id)
        resp = client.post(
            "/auth/users",
            json=_create_user_body(UserRole.manager, store.id),
            headers=_auth(manager),
        )
        assert resp.status_code == 403

    @pytest.mark.parametrize(
        "creator_role,target_role",
        [
            (UserRole.admin, UserRole.driver),
            (UserRole.owner, UserRole.driver),
            (UserRole.manager, UserRole.driver),
        ],
    )
    def test_drivers_can_be_created_by_management(
        self,
        client: TestClient,
        make_store,
        make_user,
        creator_role: UserRole,
        target_role: UserRole,
    ):
        store = make_store(code=f"drv-{creator_role.value}")
        creator_store_id = None if creator_role == UserRole.admin else store.id
        creator = make_user(creator_role, store_id=creator_store_id)
        resp = client.post(
            "/auth/users",
            json=_create_user_body(target_role, store.id),
            headers=_auth(creator),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["role"] == "driver"


# ---------------------------------------------------------------------------
# /auth/me — must remain accessible for ANY authenticated active user,
# including driver (driver must be able to read its own identity).
# ---------------------------------------------------------------------------


class TestMeIsNotGatedByRole:
    @pytest.mark.parametrize(
        "role",
        [
            UserRole.admin,
            UserRole.owner,
            UserRole.manager,
            UserRole.staff,
            UserRole.driver,
        ],
    )
    def test_each_role_can_read_me(
        self, client: TestClient, make_store, make_user, role: UserRole
    ):
        store_id = None if role == UserRole.admin else make_store().id
        user = make_user(role, store_id=store_id)
        resp = client.get("/auth/me", headers=_auth(user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == str(user.id)
        assert body["role"] == role.value
        assert "password_hash" not in body


# ---------------------------------------------------------------------------
# Public endpoints stay public
# ---------------------------------------------------------------------------


class TestPublicEndpointsStayPublic:
    def test_register_is_reachable_without_auth_and_returns_403(
        self, client: TestClient
    ):
        # No Authorization header at all. The endpoint must still respond
        # with the disabled-403, never a 401, because it must remain
        # discoverable to clients that haven't authenticated yet.
        resp = client.post(
            "/auth/register",
            json={
                "full_name": "x",
                "email": "x@example.com",
                "password": "supersecret123",
                "role": "admin",
            },
        )
        assert resp.status_code == 403
        assert "disabled" in resp.json()["detail"].lower()
        assert "/auth/users" in resp.json()["detail"]
