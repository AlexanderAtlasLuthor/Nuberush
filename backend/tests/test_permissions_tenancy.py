import uuid
from typing import Callable

import pytest
from fastapi import APIRouter
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import require_admin
from app.api.deps import require_driver_or_above
from app.api.deps import require_manager_or_above
from app.api.deps import require_owner_or_admin
from app.api.deps import require_staff_or_above
from app.api.deps import require_store_member
from app.core.permissions import resolve_store_scope
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user


# ---------------------------------------------------------------------------
# Test-only routes mounted on the real app (idempotent)
# ---------------------------------------------------------------------------


def _ensure_test_routes_mounted() -> None:
    from app.main import app

    if any(
        getattr(r, "path", "").startswith("/_test")
        for r in app.router.routes
    ):
        return

    router = APIRouter(prefix="/_test", tags=["_test"])

    @router.get("/admin")
    def _admin(u: User = Depends(require_admin)):
        return {"role": u.role.value}

    @router.get("/owner-or-admin")
    def _owner_or_admin(u: User = Depends(require_owner_or_admin)):
        return {"role": u.role.value}

    @router.get("/manager-or-above")
    def _manager_or_above(u: User = Depends(require_manager_or_above)):
        return {"role": u.role.value}

    @router.get("/staff-or-above")
    def _staff_or_above(u: User = Depends(require_staff_or_above)):
        return {"role": u.role.value}

    @router.get("/driver-or-above")
    def _driver_or_above(u: User = Depends(require_driver_or_above)):
        return {"role": u.role.value}

    @router.get("/stores/{store_id}/access")
    def _store_access(
        store_id: uuid.UUID,
        u: User = Depends(require_store_member),
    ):
        return {"store_id": str(store_id), "user_id": str(u.id)}

    app.include_router(router)


_ensure_test_routes_mounted()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(
        name: str = "Tenancy Store",
        code: str | None = None,
        is_active: bool = True,
    ) -> Store:
        store = Store(
            name=name,
            code=code or f"ten-{uuid.uuid4().hex[:8]}",
            is_active=is_active,
        )
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
        is_active: bool = True,
    ) -> User:
        return central_make_user(
            db_session,
            role=role,
            store_id=store_id,
            is_active=is_active,
            full_name=f"Tenancy {role.value}",
            password="irrelevant-pw-1234",
        )

    return _create


# ---------------------------------------------------------------------------
# Role aliases
# ---------------------------------------------------------------------------


class TestRequireAdmin:
    def test_admin_passes(self, client: TestClient, make_user):
        admin = make_user(UserRole.admin, store_id=None)
        resp = client.get("/_test/admin", headers=_auth(admin))
        assert resp.status_code == 200
        assert resp.json()["role"] == "admin"

    @pytest.mark.parametrize(
        "role", [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver]
    )
    def test_non_admin_fails(
        self, client: TestClient, make_store, make_user, role: UserRole
    ):
        store = make_store()
        store_id = store.id if role != UserRole.admin else None
        user = make_user(role, store_id=store_id)
        resp = client.get("/_test/admin", headers=_auth(user))
        assert resp.status_code == 403


class TestRequireOwnerOrAdmin:
    @pytest.mark.parametrize("role", [UserRole.admin, UserRole.owner])
    def test_admin_and_owner_pass(
        self, client: TestClient, make_store, make_user, role: UserRole
    ):
        store_id = None if role == UserRole.admin else make_store().id
        user = make_user(role, store_id=store_id)
        resp = client.get("/_test/owner-or-admin", headers=_auth(user))
        assert resp.status_code == 200

    @pytest.mark.parametrize(
        "role", [UserRole.manager, UserRole.staff, UserRole.driver]
    )
    def test_others_fail(
        self, client: TestClient, make_store, make_user, role: UserRole
    ):
        store = make_store()
        user = make_user(role, store_id=store.id)
        resp = client.get("/_test/owner-or-admin", headers=_auth(user))
        assert resp.status_code == 403


class TestRequireManagerOrAbove:
    @pytest.mark.parametrize(
        "role", [UserRole.admin, UserRole.owner, UserRole.manager]
    )
    def test_management_passes(
        self, client: TestClient, make_store, make_user, role: UserRole
    ):
        store_id = None if role == UserRole.admin else make_store().id
        user = make_user(role, store_id=store_id)
        resp = client.get("/_test/manager-or-above", headers=_auth(user))
        assert resp.status_code == 200

    @pytest.mark.parametrize("role", [UserRole.staff, UserRole.driver])
    def test_below_management_fails(
        self, client: TestClient, make_store, make_user, role: UserRole
    ):
        store = make_store()
        user = make_user(role, store_id=store.id)
        resp = client.get("/_test/manager-or-above", headers=_auth(user))
        assert resp.status_code == 403


class TestRequireStaffOrAbove:
    @pytest.mark.parametrize(
        "role",
        [UserRole.admin, UserRole.owner, UserRole.manager, UserRole.staff],
    )
    def test_staff_and_management_pass(
        self, client: TestClient, make_store, make_user, role: UserRole
    ):
        store_id = None if role == UserRole.admin else make_store().id
        user = make_user(role, store_id=store_id)
        resp = client.get("/_test/staff-or-above", headers=_auth(user))
        assert resp.status_code == 200

    def test_driver_does_not_pass_staff_gate(
        self, client: TestClient, make_store, make_user
    ):
        # Decision: driver is a sibling operational role, not below staff.
        # Endpoints meant for in-store staff must NOT be reachable by drivers.
        store = make_store()
        driver = make_user(UserRole.driver, store_id=store.id)
        resp = client.get("/_test/staff-or-above", headers=_auth(driver))
        assert resp.status_code == 403


class TestRequireDriverOrAbove:
    @pytest.mark.parametrize(
        "role",
        [UserRole.admin, UserRole.owner, UserRole.manager, UserRole.driver],
    )
    def test_driver_and_management_pass(
        self, client: TestClient, make_store, make_user, role: UserRole
    ):
        store_id = None if role == UserRole.admin else make_store().id
        user = make_user(role, store_id=store_id)
        resp = client.get("/_test/driver-or-above", headers=_auth(user))
        assert resp.status_code == 200

    def test_staff_does_not_pass_driver_gate(
        self, client: TestClient, make_store, make_user
    ):
        # Mirror of the staff/driver decision: delivery endpoints must not
        # admit in-store staff.
        store = make_store()
        staff = make_user(UserRole.staff, store_id=store.id)
        resp = client.get("/_test/driver-or-above", headers=_auth(staff))
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Store membership
# ---------------------------------------------------------------------------


class TestStoreMembershipAccessOwnStore:
    @pytest.mark.parametrize(
        "role",
        [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver],
    )
    def test_role_accesses_own_store(
        self, client: TestClient, make_store, make_user, role: UserRole
    ):
        store = make_store()
        user = make_user(role, store_id=store.id)
        resp = client.get(
            f"/_test/stores/{store.id}/access", headers=_auth(user)
        )
        assert resp.status_code == 200
        assert resp.json()["store_id"] == str(store.id)

    def test_admin_accesses_any_active_store(
        self, client: TestClient, make_store, make_user
    ):
        admin = make_user(UserRole.admin, store_id=None)
        store_a = make_store(code="store-a")
        store_b = make_store(code="store-b")
        for store in (store_a, store_b):
            resp = client.get(
                f"/_test/stores/{store.id}/access", headers=_auth(admin)
            )
            assert resp.status_code == 200


class TestStoreMembershipCrossStore:
    @pytest.mark.parametrize(
        "role", [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver]
    )
    def test_role_cannot_access_another_store(
        self, client: TestClient, make_store, make_user, role: UserRole
    ):
        own = make_store(code="own")
        other = make_store(code="other")
        user = make_user(role, store_id=own.id)
        resp = client.get(
            f"/_test/stores/{other.id}/access", headers=_auth(user)
        )
        assert resp.status_code == 403
        assert "access" in resp.json()["detail"].lower()

    def test_user_without_store_is_rejected(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        # Manager rows must have a store in production, but the column is
        # nullable in the schema so we can simulate an inconsistent state.
        rogue = make_user(UserRole.manager, store_id=None)
        resp = client.get(
            f"/_test/stores/{store.id}/access", headers=_auth(rogue)
        )
        assert resp.status_code == 403
        assert "not bound to a store" in resp.json()["detail"].lower()


class TestStoreMembershipExistenceAndState:
    def test_admin_gets_404_for_unknown_store(
        self, client: TestClient, make_user
    ):
        admin = make_user(UserRole.admin, store_id=None)
        resp = client.get(
            f"/_test/stores/{uuid.uuid4()}/access", headers=_auth(admin)
        )
        assert resp.status_code == 404

    def test_non_admin_gets_403_not_404_for_unknown_store(
        self, client: TestClient, make_store, make_user
    ):
        # Defensive: non-admin should not be able to probe store existence
        # via 404 vs 403. Both unknown-store and cross-store yield 403.
        own = make_store()
        owner = make_user(UserRole.owner, store_id=own.id)
        resp = client.get(
            f"/_test/stores/{uuid.uuid4()}/access", headers=_auth(owner)
        )
        assert resp.status_code == 403

    def test_admin_gets_400_for_inactive_store(
        self, client: TestClient, make_store, make_user
    ):
        admin = make_user(UserRole.admin, store_id=None)
        store = make_store(is_active=False, code="inactive-a")
        resp = client.get(
            f"/_test/stores/{store.id}/access", headers=_auth(admin)
        )
        assert resp.status_code == 400
        assert "inactive" in resp.json()["detail"].lower()

    def test_owner_gets_400_when_their_own_store_is_inactive(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store(is_active=False, code="inactive-b")
        owner = make_user(UserRole.owner, store_id=store.id)
        resp = client.get(
            f"/_test/stores/{store.id}/access", headers=_auth(owner)
        )
        assert resp.status_code == 400
        assert "inactive" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# resolve_store_scope (pure helper)
# ---------------------------------------------------------------------------


class TestResolveStoreScope:
    def _user(
        self, role: UserRole, store_id: uuid.UUID | None = None
    ) -> User:
        return User(
            full_name="x",
            email=f"{role.value}-{uuid.uuid4().hex[:6]}@example.com",
            password_hash="x",
            role=role,
            store_id=store_id,
        )

    def test_admin_with_requested_returns_requested(self):
        admin = self._user(UserRole.admin)
        target = uuid.uuid4()
        assert resolve_store_scope(admin, target) == target

    def test_admin_without_requested_returns_none(self):
        admin = self._user(UserRole.admin)
        assert resolve_store_scope(admin, None) is None

    @pytest.mark.parametrize(
        "role",
        [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver],
    )
    def test_non_admin_without_requested_returns_own_store(
        self, role: UserRole
    ):
        own = uuid.uuid4()
        user = self._user(role, store_id=own)
        assert resolve_store_scope(user, None) == own

    @pytest.mark.parametrize(
        "role",
        [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver],
    )
    def test_non_admin_with_matching_requested_returns_own_store(
        self, role: UserRole
    ):
        own = uuid.uuid4()
        user = self._user(role, store_id=own)
        assert resolve_store_scope(user, own) == own

    @pytest.mark.parametrize(
        "role",
        [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver],
    )
    def test_non_admin_with_mismatched_requested_raises_403(
        self, role: UserRole
    ):
        user = self._user(role, store_id=uuid.uuid4())
        with pytest.raises(Exception) as excinfo:
            resolve_store_scope(user, uuid.uuid4())
        assert excinfo.value.status_code == 403  # type: ignore[attr-defined]
        assert "access" in excinfo.value.detail.lower()  # type: ignore[attr-defined]

    @pytest.mark.parametrize(
        "role",
        [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver],
    )
    def test_non_admin_without_store_raises_403(self, role: UserRole):
        user = self._user(role, store_id=None)
        with pytest.raises(Exception) as excinfo:
            resolve_store_scope(user, uuid.uuid4())
        assert excinfo.value.status_code == 403  # type: ignore[attr-defined]
        assert "not bound to a store" in excinfo.value.detail.lower()  # type: ignore[attr-defined]
