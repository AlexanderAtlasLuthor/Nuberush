"""Dr.1.1.B — Driver RBAC + Tenancy Foundation.

Consolidated, additive test net for the `driver` role. It locks in three
things without changing any existing behaviour:

  1. The two new exact gates added in Dr.1.1.B:
       - `require_driver`            (driver and nobody else)
       - `require_store_bound_driver`(exact driver + store_id present)
     are exercised through throwaway `/_drvtest/*` routes mounted on the
     real app (same pattern as `test_permissions_tenancy`).

  2. The full driver lockdown: a driver whose `store_id` MATCHES the target
     store is STILL 403 on every operational store surface and every
     admin/management surface. Using a same-store driver is deliberate — it
     proves the role gate (not tenancy) is what blocks them.

  3. The intentional read-only exceptions a driver keeps (Dr.1.1.A §12 +
     the Dr.1.1.B decision): own identity, own store record, product
     catalog. Cross-store reads and store/product mutations stay blocked.

No /driver/* route, DriverProfile, assignment model, or migration is
introduced here.
"""

from __future__ import annotations

import uuid
from typing import Callable

import pytest
from fastapi import APIRouter
from fastapi import Depends
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import require_driver
from app.api.deps import require_store_bound_driver
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for as _auth
from tests.helpers.auth import make_user as central_make_user


# --------------------------------------------------------------------- #
# Test-only routes for the two new exact gates (idempotent mount)
# --------------------------------------------------------------------- #


def _ensure_driver_test_routes_mounted() -> None:
    from app.main import app

    if any(
        getattr(r, "path", "").startswith("/_drvtest")
        for r in app.router.routes
    ):
        return

    router = APIRouter(prefix="/_drvtest", tags=["_drvtest"])

    @router.get("/driver-only")
    def _driver_only(u: User = Depends(require_driver)):
        return {"role": u.role.value}

    @router.get("/store-bound-driver")
    def _store_bound_driver(u: User = Depends(require_store_bound_driver)):
        return {"role": u.role.value, "store_id": str(u.store_id)}

    app.include_router(router)


_ensure_driver_test_routes_mounted()


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "Driver-RBAC", is_active: bool = True) -> Store:
        store = Store(
            name=name,
            code=f"drv-{uuid.uuid4().hex[:8]}",
            is_active=is_active,
        )
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


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
            full_name=f"DriverRBAC {role.value}",
        )

    return _create


# --------------------------------------------------------------------- #
# 1. require_driver — exact, NOT "driver or above"
# --------------------------------------------------------------------- #


class TestRequireDriverExact:
    def test_driver_passes(self, client: TestClient, make_store, make_user):
        store = make_store()
        driver = make_user(UserRole.driver, store_id=store.id)
        resp = client.get("/_drvtest/driver-only", headers=_auth(driver))
        assert resp.status_code == 200, resp.text
        assert resp.json()["role"] == "driver"

    @pytest.mark.parametrize(
        "role",
        [UserRole.staff, UserRole.manager, UserRole.owner, UserRole.admin],
    )
    def test_non_driver_is_blocked(
        self, client: TestClient, make_store, make_user, role: UserRole
    ):
        # admin is global (store_id=None); everyone else is store-bound.
        store_id = None if role == UserRole.admin else make_store().id
        user = make_user(role, store_id=store_id)
        resp = client.get("/_drvtest/driver-only", headers=_auth(user))
        assert resp.status_code == 403, resp.text

    def test_anonymous_is_unauthenticated(self, client: TestClient):
        resp = client.get("/_drvtest/driver-only")
        assert resp.status_code == 401


# --------------------------------------------------------------------- #
# 2. require_store_bound_driver — exact driver + store_id present
# --------------------------------------------------------------------- #


class TestRequireStoreBoundDriver:
    def test_store_bound_driver_passes(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        driver = make_user(UserRole.driver, store_id=store.id)
        resp = client.get(
            "/_drvtest/store-bound-driver", headers=_auth(driver)
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["store_id"] == str(store.id)

    def test_driver_without_store_is_blocked(
        self, client: TestClient, make_user
    ):
        # The DB column is nullable, so the test helper can mint a
        # storeless driver directly (bypassing the service invariant).
        driver = make_user(UserRole.driver, store_id=None)
        resp = client.get(
            "/_drvtest/store-bound-driver", headers=_auth(driver)
        )
        assert resp.status_code == 403, resp.text

    @pytest.mark.parametrize(
        "role",
        [UserRole.staff, UserRole.manager, UserRole.owner, UserRole.admin],
    )
    def test_non_driver_is_blocked(
        self, client: TestClient, make_store, make_user, role: UserRole
    ):
        store_id = None if role == UserRole.admin else make_store().id
        user = make_user(role, store_id=store_id)
        resp = client.get(
            "/_drvtest/store-bound-driver", headers=_auth(user)
        )
        assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------- #
# 3. Driver lockdown on operational store surfaces (same-store driver)
# --------------------------------------------------------------------- #

# GET surfaces whose role gate must reject a driver even when the driver's
# store_id equals the path store_id (so tenancy passes, role gate blocks).
_STORE_SURFACE_TEMPLATES = [
    "/stores/{store_id}/orders",
    "/stores/{store_id}/inventory",
    "/stores/{store_id}/audit",
    "/stores/{store_id}/dashboard",
    "/stores/{store_id}/earnings",
    "/stores/{store_id}/regulatory/alerts",
]


class TestDriverBlockedOnStoreSurfaces:
    @pytest.mark.parametrize("path_tmpl", _STORE_SURFACE_TEMPLATES)
    def test_same_store_driver_is_403(
        self,
        client: TestClient,
        make_store,
        make_user,
        path_tmpl: str,
    ):
        store = make_store()
        driver = make_user(UserRole.driver, store_id=store.id)
        resp = client.get(
            path_tmpl.format(store_id=store.id), headers=_auth(driver)
        )
        assert resp.status_code == 403, f"{path_tmpl} -> {resp.status_code}"


# --------------------------------------------------------------------- #
# 4. Driver lockdown on admin / global / management surfaces
# --------------------------------------------------------------------- #


class TestDriverBlockedOnAdminAndManagement:
    def test_admin_dashboard_is_403(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        driver = make_user(UserRole.driver, store_id=store.id)
        resp = client.get("/admin/dashboard", headers=_auth(driver))
        assert resp.status_code == 403, resp.text

    def test_user_management_list_is_403(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        driver = make_user(UserRole.driver, store_id=store.id)
        resp = client.get("/auth/users", headers=_auth(driver))
        assert resp.status_code == 403, resp.text


# --------------------------------------------------------------------- #
# 5. Intentional read-only exceptions the driver keeps (test-locked)
# --------------------------------------------------------------------- #


class TestDriverReadOnlyExceptions:
    def test_driver_can_read_own_identity(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        driver = make_user(UserRole.driver, store_id=store.id)
        resp = client.get("/auth/me", headers=_auth(driver))
        assert resp.status_code == 200, resp.text
        assert resp.json()["role"] == "driver"

    def test_driver_can_read_own_store_record(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        driver = make_user(UserRole.driver, store_id=store.id)
        resp = client.get(f"/stores/{store.id}", headers=_auth(driver))
        assert resp.status_code == 200, resp.text

    def test_driver_can_read_product_catalog(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        driver = make_user(UserRole.driver, store_id=store.id)
        resp = client.get("/products", headers=_auth(driver))
        assert resp.status_code == 200, resp.text

    def test_driver_cannot_read_another_store_record(
        self, client: TestClient, make_store, make_user
    ):
        own_store = make_store("own")
        other_store = make_store("other")
        driver = make_user(UserRole.driver, store_id=own_store.id)
        resp = client.get(
            f"/stores/{other_store.id}", headers=_auth(driver)
        )
        assert resp.status_code == 403, resp.text

    def test_driver_cannot_mutate_store(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        driver = make_user(UserRole.driver, store_id=store.id)
        resp = client.patch(
            f"/stores/{store.id}",
            json={"name": "Renamed By Driver"},
            headers=_auth(driver),
        )
        assert resp.status_code == 403, resp.text
