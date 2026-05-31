"""Service-layer tests for users management (F2.15.2).

Exercises `app.services.users` and the new helpers in
`app.core.permissions` against the real test DB via the `db_session`
fixture from conftest. Covers:

  - `list_users` RBAC + tenancy + filtering + pagination.
  - `get_user` RBAC + tenancy.
  - `update_user` partial mutation, RBAC, tenancy, schema-locked
    fields untouched.
  - `deactivate_user` RBAC + self-target + last-admin guard.
  - `reactivate_user` RBAC + non-admin store invariant.
  - `change_user_role` RBAC matrix + privilege escalation + self
    guard + admin/store invariants.
  - `assign_user_store` admin-only + admin/non-admin invariants +
    inactive store rejection.

Style mirrors tests/test_stores_service.py and
test_permissions_tenancy.py: real DB, helper fixtures for stores and
users, pytest.raises(HTTPException) with status_code asserts on
negative paths.
"""

from __future__ import annotations

import uuid
from typing import Callable
from uuid import UUID

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import USER_ROLE_UPDATE_MATRIX
from app.core.permissions import can_caller_assign_role
from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from app.schemas.users import UserRoleChangeRequest
from app.schemas.users import UserStoreAssignmentRequest
from app.schemas.users import UserUpdateRequest
from app.services import users as svc


# --------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------- #


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(
        *,
        name: str = "Users-Svc",
        code: str | None = None,
        is_active: bool = True,
    ) -> Store:
        store = Store(
            name=name,
            code=code or f"usrsvc-{uuid.uuid4().hex[:8]}",
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
        *,
        role: UserRole,
        store_id: UUID | None = None,
        is_active: bool = True,
        full_name: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> User:
        user = User(
            full_name=full_name or f"User {role.value}",
            email=email or f"{role.value}-{uuid.uuid4().hex[:10]}@example.com",
            phone=phone,
            role=role,
            store_id=store_id,
            is_active=is_active,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _create


# --------------------------------------------------------------------- #
# Permission matrix sanity (cheap pure tests)
# --------------------------------------------------------------------- #


class TestUserRoleUpdateMatrix:
    def test_admin_can_assign_every_role(self):
        for role in UserRole:
            assert can_caller_assign_role(UserRole.admin, role) is True

    def test_owner_can_assign_manager_staff_driver(self):
        assert can_caller_assign_role(UserRole.owner, UserRole.manager)
        assert can_caller_assign_role(UserRole.owner, UserRole.staff)
        assert can_caller_assign_role(UserRole.owner, UserRole.driver)

    def test_owner_cannot_assign_admin_or_owner(self):
        assert not can_caller_assign_role(UserRole.owner, UserRole.admin)
        assert not can_caller_assign_role(UserRole.owner, UserRole.owner)

    def test_manager_can_assign_staff_driver_only(self):
        assert can_caller_assign_role(UserRole.manager, UserRole.staff)
        assert can_caller_assign_role(UserRole.manager, UserRole.driver)
        for forbidden in (UserRole.admin, UserRole.owner, UserRole.manager):
            assert not can_caller_assign_role(UserRole.manager, forbidden)

    def test_staff_and_driver_assign_nothing(self):
        for role in UserRole:
            assert not can_caller_assign_role(UserRole.staff, role)
            assert not can_caller_assign_role(UserRole.driver, role)

    def test_matrix_keys_cover_every_role(self):
        assert set(USER_ROLE_UPDATE_MATRIX.keys()) == set(UserRole)


# --------------------------------------------------------------------- #
# list_users
# --------------------------------------------------------------------- #


class TestListUsers:
    def test_admin_lists_globally(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store_a = make_store(code="lst-a")
        store_b = make_store(code="lst-b")
        make_user(role=UserRole.owner, store_id=store_a.id)
        make_user(role=UserRole.staff, store_id=store_b.id)

        result = svc.list_users(db_session, actor=admin)

        # admin + owner + staff = 3 users in this isolated test
        # transaction. Other test artifacts could exist from earlier
        # in the same SAVEPOINT, so we assert the >= 3 floor and
        # presence of the IDs we just created.
        ids = {u.id for u in result["items"]}
        assert admin.id in ids
        assert result["total"] >= 3

    def test_admin_filters_by_store_id(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store_a = make_store(code="lst-fa")
        store_b = make_store(code="lst-fb")
        owner_a = make_user(role=UserRole.owner, store_id=store_a.id)
        make_user(role=UserRole.owner, store_id=store_b.id)

        result = svc.list_users(
            db_session, actor=admin, store_id=store_a.id
        )

        ids = {u.id for u in result["items"]}
        assert owner_a.id in ids
        for user in result["items"]:
            assert user.store_id == store_a.id

    def test_owner_lists_only_own_store(
        self, db_session: Session, make_store, make_user
    ):
        store_a = make_store(code="lst-oa")
        store_b = make_store(code="lst-ob")
        owner = make_user(role=UserRole.owner, store_id=store_a.id)
        own_staff = make_user(
            role=UserRole.staff, store_id=store_a.id
        )
        other_owner = make_user(role=UserRole.owner, store_id=store_b.id)

        result = svc.list_users(db_session, actor=owner)

        ids = {u.id for u in result["items"]}
        assert owner.id in ids
        assert own_staff.id in ids
        assert other_owner.id not in ids
        for user in result["items"]:
            assert user.store_id == store_a.id

    def test_manager_lists_only_own_store(
        self, db_session: Session, make_store, make_user
    ):
        store_a = make_store(code="lst-ma")
        store_b = make_store(code="lst-mb")
        manager = make_user(role=UserRole.manager, store_id=store_a.id)
        make_user(role=UserRole.driver, store_id=store_b.id)

        result = svc.list_users(db_session, actor=manager)

        for user in result["items"]:
            assert user.store_id == store_a.id

    def test_staff_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="lst-s")
        staff = make_user(role=UserRole.staff, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_users(db_session, actor=staff)
        assert excinfo.value.status_code == 403

    def test_driver_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="lst-d")
        driver = make_user(role=UserRole.driver, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_users(db_session, actor=driver)
        assert excinfo.value.status_code == 403

    def test_owner_cross_store_filter_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        own = make_store(code="lst-co")
        other = make_store(code="lst-cother")
        owner = make_user(role=UserRole.owner, store_id=own.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_users(db_session, actor=owner, store_id=other.id)
        assert excinfo.value.status_code == 403

    def test_manager_cross_store_filter_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        own = make_store(code="lst-cm")
        other = make_store(code="lst-cmother")
        manager = make_user(role=UserRole.manager, store_id=own.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.list_users(db_session, actor=manager, store_id=other.id)
        assert excinfo.value.status_code == 403

    def test_filters_by_role(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store(code="lst-fr")
        make_user(role=UserRole.owner, store_id=store.id)
        make_user(role=UserRole.staff, store_id=store.id)
        make_user(role=UserRole.driver, store_id=store.id)

        result = svc.list_users(
            db_session,
            actor=admin,
            role=UserRole.staff,
            store_id=store.id,
        )

        for user in result["items"]:
            assert user.role == UserRole.staff
        assert result["total"] == 1

    def test_filters_by_is_active(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store(code="lst-act")
        make_user(role=UserRole.staff, store_id=store.id, is_active=True)
        make_user(role=UserRole.staff, store_id=store.id, is_active=False)

        active = svc.list_users(
            db_session, actor=admin, is_active=True, store_id=store.id
        )
        inactive = svc.list_users(
            db_session, actor=admin, is_active=False, store_id=store.id
        )

        for user in active["items"]:
            assert user.is_active is True
        for user in inactive["items"]:
            assert user.is_active is False
        assert active["total"] >= 1
        assert inactive["total"] == 1

    def test_q_searches_full_name(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store(code="lst-q1")
        make_user(
            role=UserRole.staff,
            store_id=store.id,
            full_name="Alice Wonderland",
        )
        make_user(
            role=UserRole.staff,
            store_id=store.id,
            full_name="Bob Builder",
        )

        result = svc.list_users(
            db_session, actor=admin, q="alice", store_id=store.id
        )

        names = [u.full_name for u in result["items"]]
        assert "Alice Wonderland" in names
        assert "Bob Builder" not in names

    def test_q_searches_email(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store(code="lst-q2")
        make_user(
            role=UserRole.staff,
            store_id=store.id,
            email=f"unique-{uuid.uuid4().hex[:6]}@spot.example",
        )

        result = svc.list_users(
            db_session, actor=admin, q="spot.example", store_id=store.id
        )

        for user in result["items"]:
            assert "spot.example" in user.email

    def test_pagination_limit_offset_total(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store(code="lst-pg")
        for _ in range(5):
            make_user(role=UserRole.staff, store_id=store.id)

        page = svc.list_users(
            db_session,
            actor=admin,
            store_id=store.id,
            limit=2,
            offset=0,
        )

        assert len(page["items"]) == 2
        assert page["limit"] == 2
        assert page["offset"] == 0
        assert page["total"] == 5

        next_page = svc.list_users(
            db_session,
            actor=admin,
            store_id=store.id,
            limit=2,
            offset=2,
        )
        assert len(next_page["items"]) == 2
        assert next_page["offset"] == 2


# --------------------------------------------------------------------- #
# get_user
# --------------------------------------------------------------------- #


class TestGetUser:
    def test_admin_sees_anyone(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store(code="get-a")
        target = make_user(role=UserRole.staff, store_id=store.id)
        result = svc.get_user(db_session, target.id, actor=admin)
        assert result.id == target.id

    def test_owner_sees_user_in_own_store(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="get-o")
        owner = make_user(role=UserRole.owner, store_id=store.id)
        target = make_user(role=UserRole.staff, store_id=store.id)
        result = svc.get_user(db_session, target.id, actor=owner)
        assert result.id == target.id

    def test_manager_sees_user_in_own_store(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="get-m")
        manager = make_user(role=UserRole.manager, store_id=store.id)
        target = make_user(role=UserRole.staff, store_id=store.id)
        result = svc.get_user(db_session, target.id, actor=manager)
        assert result.id == target.id

    def test_owner_cross_store_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        own = make_store(code="get-co")
        other = make_store(code="get-cother")
        owner = make_user(role=UserRole.owner, store_id=own.id)
        target = make_user(role=UserRole.staff, store_id=other.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.get_user(db_session, target.id, actor=owner)
        assert excinfo.value.status_code == 403

    def test_manager_cross_store_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        own = make_store(code="get-cm")
        other = make_store(code="get-cmother")
        manager = make_user(role=UserRole.manager, store_id=own.id)
        target = make_user(role=UserRole.staff, store_id=other.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.get_user(db_session, target.id, actor=manager)
        assert excinfo.value.status_code == 403

    def test_owner_cannot_see_admin(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="get-oa")
        owner = make_user(role=UserRole.owner, store_id=store.id)
        admin_target = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.get_user(db_session, admin_target.id, actor=owner)
        assert excinfo.value.status_code == 403

    def test_manager_cannot_see_admin(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="get-ma")
        manager = make_user(role=UserRole.manager, store_id=store.id)
        admin_target = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.get_user(db_session, admin_target.id, actor=manager)
        assert excinfo.value.status_code == 403

    def test_staff_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="get-sf")
        staff = make_user(role=UserRole.staff, store_id=store.id)
        target = make_user(role=UserRole.driver, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.get_user(db_session, target.id, actor=staff)
        assert excinfo.value.status_code == 403

    def test_driver_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="get-df")
        driver = make_user(role=UserRole.driver, store_id=store.id)
        target = make_user(role=UserRole.staff, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.get_user(db_session, target.id, actor=driver)
        assert excinfo.value.status_code == 403

    def test_unknown_user_404(
        self, db_session: Session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.get_user(db_session, uuid.uuid4(), actor=admin)
        assert excinfo.value.status_code == 404


# --------------------------------------------------------------------- #
# update_user
# --------------------------------------------------------------------- #


class TestUpdateUser:
    def test_admin_updates_full_name_and_phone(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store(code="upd-a")
        target = make_user(role=UserRole.staff, store_id=store.id)

        updated = svc.update_user(
            db_session,
            target.id,
            UserUpdateRequest(full_name="Updated Name", phone="+1-555-0100"),
            actor=admin,
        )

        assert updated.full_name == "Updated Name"
        assert updated.phone == "+1-555-0100"

    def test_owner_updates_user_in_own_store(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="upd-o")
        owner = make_user(role=UserRole.owner, store_id=store.id)
        target = make_user(role=UserRole.staff, store_id=store.id)

        updated = svc.update_user(
            db_session,
            target.id,
            UserUpdateRequest(full_name="By Owner"),
            actor=owner,
        )

        assert updated.full_name == "By Owner"

    def test_manager_updates_staff_in_own_store(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="upd-m")
        manager = make_user(role=UserRole.manager, store_id=store.id)
        target = make_user(role=UserRole.staff, store_id=store.id)

        updated = svc.update_user(
            db_session,
            target.id,
            UserUpdateRequest(full_name="By Manager"),
            actor=manager,
        )

        assert updated.full_name == "By Manager"

    def test_manager_cannot_update_owner(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="upd-mo")
        manager = make_user(role=UserRole.manager, store_id=store.id)
        owner_target = make_user(role=UserRole.owner, store_id=store.id)

        with pytest.raises(HTTPException) as excinfo:
            svc.update_user(
                db_session,
                owner_target.id,
                UserUpdateRequest(full_name="Nope"),
                actor=manager,
            )
        assert excinfo.value.status_code == 403

    def test_owner_cannot_update_admin(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="upd-oa")
        owner = make_user(role=UserRole.owner, store_id=store.id)
        admin_target = make_user(role=UserRole.admin)

        with pytest.raises(HTTPException) as excinfo:
            svc.update_user(
                db_session,
                admin_target.id,
                UserUpdateRequest(full_name="Nope"),
                actor=owner,
            )
        assert excinfo.value.status_code == 403

    def test_staff_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="upd-sf")
        staff = make_user(role=UserRole.staff, store_id=store.id)
        target = make_user(role=UserRole.driver, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.update_user(
                db_session,
                target.id,
                UserUpdateRequest(full_name="x"),
                actor=staff,
            )
        assert excinfo.value.status_code == 403

    def test_driver_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="upd-df")
        driver = make_user(role=UserRole.driver, store_id=store.id)
        target = make_user(role=UserRole.staff, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.update_user(
                db_session,
                target.id,
                UserUpdateRequest(full_name="x"),
                actor=driver,
            )
        assert excinfo.value.status_code == 403

    def test_owner_cross_store_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        own = make_store(code="upd-cs")
        other = make_store(code="upd-csother")
        owner = make_user(role=UserRole.owner, store_id=own.id)
        target = make_user(role=UserRole.staff, store_id=other.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.update_user(
                db_session,
                target.id,
                UserUpdateRequest(full_name="x"),
                actor=owner,
            )
        assert excinfo.value.status_code == 403

    def test_unknown_user_404(self, db_session: Session, make_user):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.update_user(
                db_session,
                uuid.uuid4(),
                UserUpdateRequest(full_name="x"),
                actor=admin,
            )
        assert excinfo.value.status_code == 404

    def test_only_full_name_and_phone_change(
        self, db_session: Session, make_store, make_user
    ):
        """The schema's `extra="forbid"` blocks privileged keys at
        parse time, but we also confirm here that the service never
        touches them — defense in depth against future schema drift."""
        admin = make_user(role=UserRole.admin)
        store = make_store(code="upd-only")
        target = make_user(
            role=UserRole.staff,
            store_id=store.id,
            email="orig@example.com",
        )
        original_email = target.email
        original_role = target.role
        original_store_id = target.store_id
        original_is_active = target.is_active

        updated = svc.update_user(
            db_session,
            target.id,
            UserUpdateRequest(full_name="New", phone="+1-555-0200"),
            actor=admin,
        )

        assert updated.full_name == "New"
        assert updated.phone == "+1-555-0200"
        assert updated.email == original_email
        assert updated.role == original_role
        assert updated.store_id == original_store_id
        assert updated.is_active == original_is_active


# --------------------------------------------------------------------- #
# deactivate_user
# --------------------------------------------------------------------- #


class TestDeactivateUser:
    def test_admin_deactivates_target(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store(code="deact-a")
        target = make_user(role=UserRole.staff, store_id=store.id)

        result = svc.deactivate_user(db_session, target.id, actor=admin)
        assert result.is_active is False

    def test_owner_deactivates_in_own_store(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="deact-o")
        owner = make_user(role=UserRole.owner, store_id=store.id)
        target = make_user(role=UserRole.staff, store_id=store.id)

        result = svc.deactivate_user(db_session, target.id, actor=owner)
        assert result.is_active is False

    def test_manager_deactivates_staff(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="deact-m")
        manager = make_user(role=UserRole.manager, store_id=store.id)
        target = make_user(role=UserRole.staff, store_id=store.id)

        result = svc.deactivate_user(db_session, target.id, actor=manager)
        assert result.is_active is False

    def test_manager_cannot_deactivate_owner(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="deact-mo")
        manager = make_user(role=UserRole.manager, store_id=store.id)
        owner_target = make_user(role=UserRole.owner, store_id=store.id)

        with pytest.raises(HTTPException) as excinfo:
            svc.deactivate_user(
                db_session, owner_target.id, actor=manager
            )
        assert excinfo.value.status_code == 403

    def test_manager_cannot_deactivate_peer_manager(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="deact-mm")
        manager = make_user(role=UserRole.manager, store_id=store.id)
        peer = make_user(role=UserRole.manager, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.deactivate_user(db_session, peer.id, actor=manager)
        assert excinfo.value.status_code == 403

    def test_manager_cannot_deactivate_admin(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="deact-mad")
        manager = make_user(role=UserRole.manager, store_id=store.id)
        admin_target = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.deactivate_user(
                db_session, admin_target.id, actor=manager
            )
        assert excinfo.value.status_code == 403

    def test_staff_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="deact-sf")
        staff = make_user(role=UserRole.staff, store_id=store.id)
        target = make_user(role=UserRole.driver, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.deactivate_user(db_session, target.id, actor=staff)
        assert excinfo.value.status_code == 403

    def test_driver_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="deact-df")
        driver = make_user(role=UserRole.driver, store_id=store.id)
        target = make_user(role=UserRole.staff, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.deactivate_user(db_session, target.id, actor=driver)
        assert excinfo.value.status_code == 403

    def test_owner_cross_store_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        own = make_store(code="deact-cs")
        other = make_store(code="deact-csother")
        owner = make_user(role=UserRole.owner, store_id=own.id)
        target = make_user(role=UserRole.staff, store_id=other.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.deactivate_user(db_session, target.id, actor=owner)
        assert excinfo.value.status_code == 403

    def test_self_deactivate_blocked_422(
        self, db_session: Session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.deactivate_user(db_session, admin.id, actor=admin)
        assert excinfo.value.status_code == 422
        assert "yourself" in excinfo.value.detail.lower()

    def test_last_active_admin_blocked_422(
        self,
        db_session: Session,
        make_user,
    ):
        # Drop every pre-existing active admin so this transaction has
        # exactly two: actor + target. Deactivating the target leaves
        # one (actor); the next attempt would leave zero, so the guard
        # must trip. Note: we operate inside the SAVEPOINT-bound
        # session, so external state is unaffected.
        db_session.execute(
            select(User).where(
                User.role == UserRole.admin, User.is_active.is_(True)
            )
        )
        for existing in db_session.scalars(
            select(User).where(
                User.role == UserRole.admin, User.is_active.is_(True)
            )
        ).all():
            existing.is_active = False
        db_session.commit()

        actor = make_user(role=UserRole.admin)
        target = make_user(role=UserRole.admin)

        # First deactivation succeeds — two active admins left becomes one.
        svc.deactivate_user(db_session, target.id, actor=actor)

        # actor is now the last active admin; an owner trying to
        # deactivate them must be blocked with 422.
        store = db_session.scalar(select(Store)) or None
        if store is None:
            store = Store(name="last-admin", code=f"la-{uuid.uuid4().hex[:6]}")
            db_session.add(store)
            db_session.commit()
            db_session.refresh(store)
        # We need an admin actor since owners can't deactivate admins.
        # Spin up a temp admin row, deactivate `actor` through it, and
        # observe the 422 because that would leave zero active admins.
        ghost_admin = make_user(role=UserRole.admin)
        # ghost + actor are both active; deactivating actor through
        # ghost must succeed (still leaves ghost active).
        svc.deactivate_user(db_session, actor.id, actor=ghost_admin)
        # Now ghost is the last active admin. Self-target is blocked
        # by the self-target guard before we even check last-admin,
        # so use a second admin actor.
        another_admin = make_user(role=UserRole.admin)
        # With ghost deactivated by another, only `another_admin`
        # would remain. another_admin trying to deactivate ghost
        # (currently active) when ghost+another are the only two
        # actives — wait, another_admin is still active too — so
        # deactivating ghost just brings count to 1. That's allowed.
        # We need the count to GO DOWN TO 0, so deactivate the other
        # active admin from the perspective of itself? That's blocked
        # by self guard. The cleanest path: make `another_admin`
        # inactive directly, leaving ghost as the literal last
        # active admin, then attempt to deactivate ghost via a third
        # admin who is inactive — but the actor must be active
        # (login-time check is elsewhere) or rather, the service
        # guard simply forbids when leaving zero actives.
        another_admin.is_active = False
        db_session.commit()
        # Now ghost is the only active admin. Deactivating ghost
        # would leave zero. Use yet another admin actor (inactive
        # acts are blocked by /me but the service trusts its caller),
        # so create one and use it as the actor.
        deactivator = make_user(role=UserRole.admin, is_active=False)
        with pytest.raises(HTTPException) as excinfo:
            svc.deactivate_user(db_session, ghost_admin.id, actor=deactivator)
        assert excinfo.value.status_code == 422
        assert "last active admin" in excinfo.value.detail.lower()

    def test_unknown_user_404(self, db_session: Session, make_user):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.deactivate_user(
                db_session, uuid.uuid4(), actor=admin
            )
        assert excinfo.value.status_code == 404


# --------------------------------------------------------------------- #
# reactivate_user
# --------------------------------------------------------------------- #


class TestReactivateUser:
    def test_admin_reactivates_target(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store(code="ract-a")
        target = make_user(
            role=UserRole.staff, store_id=store.id, is_active=False
        )

        result = svc.reactivate_user(db_session, target.id, actor=admin)
        assert result.is_active is True

    def test_owner_reactivates_in_own_store(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="ract-o")
        owner = make_user(role=UserRole.owner, store_id=store.id)
        target = make_user(
            role=UserRole.staff, store_id=store.id, is_active=False
        )

        result = svc.reactivate_user(db_session, target.id, actor=owner)
        assert result.is_active is True

    def test_manager_reactivates_staff(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="ract-m")
        manager = make_user(role=UserRole.manager, store_id=store.id)
        target = make_user(
            role=UserRole.staff, store_id=store.id, is_active=False
        )

        result = svc.reactivate_user(db_session, target.id, actor=manager)
        assert result.is_active is True

    def test_staff_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="ract-sf")
        staff = make_user(role=UserRole.staff, store_id=store.id)
        target = make_user(
            role=UserRole.driver, store_id=store.id, is_active=False
        )
        with pytest.raises(HTTPException) as excinfo:
            svc.reactivate_user(db_session, target.id, actor=staff)
        assert excinfo.value.status_code == 403

    def test_driver_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="ract-df")
        driver = make_user(role=UserRole.driver, store_id=store.id)
        target = make_user(
            role=UserRole.staff, store_id=store.id, is_active=False
        )
        with pytest.raises(HTTPException) as excinfo:
            svc.reactivate_user(db_session, target.id, actor=driver)
        assert excinfo.value.status_code == 403

    def test_owner_cross_store_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        own = make_store(code="ract-cs")
        other = make_store(code="ract-csother")
        owner = make_user(role=UserRole.owner, store_id=own.id)
        target = make_user(
            role=UserRole.staff, store_id=other.id, is_active=False
        )
        with pytest.raises(HTTPException) as excinfo:
            svc.reactivate_user(db_session, target.id, actor=owner)
        assert excinfo.value.status_code == 403

    def test_non_admin_without_store_blocked(
        self, db_session: Session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        # Inconsistent state: a non-admin user with no store. The
        # service must refuse to reactivate them with 422 because
        # promoting to active would create a logically broken row.
        target = make_user(
            role=UserRole.staff, store_id=None, is_active=False
        )
        with pytest.raises(HTTPException) as excinfo:
            svc.reactivate_user(db_session, target.id, actor=admin)
        assert excinfo.value.status_code == 422
        assert "store" in excinfo.value.detail.lower()

    def test_unknown_user_404(self, db_session: Session, make_user):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.reactivate_user(
                db_session, uuid.uuid4(), actor=admin
            )
        assert excinfo.value.status_code == 404


# --------------------------------------------------------------------- #
# change_user_role
# --------------------------------------------------------------------- #


class TestChangeUserRole:
    def test_admin_assigns_owner(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store(code="role-aa")
        target = make_user(role=UserRole.staff, store_id=store.id)

        result = svc.change_user_role(
            db_session,
            target.id,
            UserRoleChangeRequest(role=UserRole.owner),
            actor=admin,
        )
        assert result.role == UserRole.owner
        assert result.store_id == store.id

    def test_admin_promotes_to_admin_clears_store(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store(code="role-toa")
        # F2.24.C5: a user may only be promoted to admin with an official
        # @nuberush.com address.
        target = make_user(
            role=UserRole.owner,
            store_id=store.id,
            email="promote@nuberush.com",
        )

        result = svc.change_user_role(
            db_session,
            target.id,
            UserRoleChangeRequest(role=UserRole.admin),
            actor=admin,
        )
        assert result.role == UserRole.admin
        assert result.store_id is None

    def test_demote_admin_without_store_blocked_422(
        self, db_session: Session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        target = make_user(role=UserRole.admin)

        with pytest.raises(HTTPException) as excinfo:
            svc.change_user_role(
                db_session,
                target.id,
                UserRoleChangeRequest(role=UserRole.owner),
                actor=admin,
            )
        assert excinfo.value.status_code == 422
        assert "store" in excinfo.value.detail.lower()

    def test_owner_assigns_manager(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="role-om")
        owner = make_user(role=UserRole.owner, store_id=store.id)
        target = make_user(role=UserRole.staff, store_id=store.id)

        result = svc.change_user_role(
            db_session,
            target.id,
            UserRoleChangeRequest(role=UserRole.manager),
            actor=owner,
        )
        assert result.role == UserRole.manager

    def test_owner_cannot_assign_owner(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="role-oo")
        owner = make_user(role=UserRole.owner, store_id=store.id)
        target = make_user(role=UserRole.staff, store_id=store.id)

        with pytest.raises(HTTPException) as excinfo:
            svc.change_user_role(
                db_session,
                target.id,
                UserRoleChangeRequest(role=UserRole.owner),
                actor=owner,
            )
        assert excinfo.value.status_code == 403

    def test_owner_cannot_assign_admin(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="role-oad")
        owner = make_user(role=UserRole.owner, store_id=store.id)
        target = make_user(role=UserRole.staff, store_id=store.id)

        with pytest.raises(HTTPException) as excinfo:
            svc.change_user_role(
                db_session,
                target.id,
                UserRoleChangeRequest(role=UserRole.admin),
                actor=owner,
            )
        assert excinfo.value.status_code == 403

    def test_manager_assigns_staff(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="role-ms")
        manager = make_user(role=UserRole.manager, store_id=store.id)
        target = make_user(role=UserRole.driver, store_id=store.id)

        result = svc.change_user_role(
            db_session,
            target.id,
            UserRoleChangeRequest(role=UserRole.staff),
            actor=manager,
        )
        assert result.role == UserRole.staff

    @pytest.mark.parametrize(
        "forbidden", [UserRole.manager, UserRole.owner, UserRole.admin]
    )
    def test_manager_cannot_escalate(
        self,
        db_session: Session,
        make_store,
        make_user,
        forbidden: UserRole,
    ):
        store = make_store(code=f"role-mesc-{forbidden.value}")
        manager = make_user(role=UserRole.manager, store_id=store.id)
        target = make_user(role=UserRole.staff, store_id=store.id)

        with pytest.raises(HTTPException) as excinfo:
            svc.change_user_role(
                db_session,
                target.id,
                UserRoleChangeRequest(role=forbidden),
                actor=manager,
            )
        assert excinfo.value.status_code == 403

    def test_staff_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="role-sf")
        staff = make_user(role=UserRole.staff, store_id=store.id)
        target = make_user(role=UserRole.driver, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.change_user_role(
                db_session,
                target.id,
                UserRoleChangeRequest(role=UserRole.staff),
                actor=staff,
            )
        assert excinfo.value.status_code == 403

    def test_driver_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        store = make_store(code="role-df")
        driver = make_user(role=UserRole.driver, store_id=store.id)
        target = make_user(role=UserRole.staff, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.change_user_role(
                db_session,
                target.id,
                UserRoleChangeRequest(role=UserRole.driver),
                actor=driver,
            )
        assert excinfo.value.status_code == 403

    def test_self_role_change_blocked_422(
        self, db_session: Session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.change_user_role(
                db_session,
                admin.id,
                UserRoleChangeRequest(role=UserRole.owner),
                actor=admin,
            )
        assert excinfo.value.status_code == 422

    def test_owner_cross_store_forbidden(
        self, db_session: Session, make_store, make_user
    ):
        own = make_store(code="role-cs")
        other = make_store(code="role-csother")
        owner = make_user(role=UserRole.owner, store_id=own.id)
        target = make_user(role=UserRole.staff, store_id=other.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.change_user_role(
                db_session,
                target.id,
                UserRoleChangeRequest(role=UserRole.driver),
                actor=owner,
            )
        assert excinfo.value.status_code == 403

    def test_unknown_user_404(self, db_session: Session, make_user):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.change_user_role(
                db_session,
                uuid.uuid4(),
                UserRoleChangeRequest(role=UserRole.owner),
                actor=admin,
            )
        assert excinfo.value.status_code == 404


# --------------------------------------------------------------------- #
# assign_user_store
# --------------------------------------------------------------------- #


class TestAssignUserStore:
    def test_admin_assigns_active_store_to_non_admin(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store_a = make_store(code="asn-a")
        store_b = make_store(code="asn-b")
        target = make_user(role=UserRole.staff, store_id=store_a.id)

        result = svc.assign_user_store(
            db_session,
            target.id,
            UserStoreAssignmentRequest(store_id=store_b.id),
            actor=admin,
        )
        assert result.store_id == store_b.id

    def test_admin_clears_store_for_admin_target(
        self, db_session: Session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        admin_target = make_user(role=UserRole.admin)
        result = svc.assign_user_store(
            db_session,
            admin_target.id,
            UserStoreAssignmentRequest(store_id=None),
            actor=admin,
        )
        assert result.store_id is None

    def test_assigning_store_to_admin_blocked_422(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        admin_target = make_user(role=UserRole.admin)
        store = make_store(code="asn-aa")
        with pytest.raises(HTTPException) as excinfo:
            svc.assign_user_store(
                db_session,
                admin_target.id,
                UserStoreAssignmentRequest(store_id=store.id),
                actor=admin,
            )
        assert excinfo.value.status_code == 422

    def test_clearing_store_for_non_admin_blocked_422(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store(code="asn-cn")
        target = make_user(role=UserRole.staff, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.assign_user_store(
                db_session,
                target.id,
                UserStoreAssignmentRequest(store_id=None),
                actor=admin,
            )
        assert excinfo.value.status_code == 422

    def test_inactive_store_assignment_blocked_400(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        active = make_store(code="asn-act")
        inactive = make_store(code="asn-inact", is_active=False)
        target = make_user(role=UserRole.staff, store_id=active.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.assign_user_store(
                db_session,
                target.id,
                UserStoreAssignmentRequest(store_id=inactive.id),
                actor=admin,
            )
        assert excinfo.value.status_code == 400
        assert "inactive" in excinfo.value.detail.lower()

    def test_unknown_store_404(
        self, db_session: Session, make_store, make_user
    ):
        admin = make_user(role=UserRole.admin)
        store = make_store(code="asn-uk")
        target = make_user(role=UserRole.staff, store_id=store.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.assign_user_store(
                db_session,
                target.id,
                UserStoreAssignmentRequest(store_id=uuid.uuid4()),
                actor=admin,
            )
        assert excinfo.value.status_code == 404

    @pytest.mark.parametrize(
        "caller_role",
        [UserRole.owner, UserRole.manager, UserRole.staff, UserRole.driver],
    )
    def test_non_admin_caller_forbidden(
        self,
        db_session: Session,
        make_store,
        make_user,
        caller_role: UserRole,
    ):
        store_a = make_store(code=f"asn-na-{caller_role.value}")
        store_b = make_store(code=f"asn-nab-{caller_role.value}")
        actor = make_user(role=caller_role, store_id=store_a.id)
        target = make_user(role=UserRole.staff, store_id=store_a.id)
        with pytest.raises(HTTPException) as excinfo:
            svc.assign_user_store(
                db_session,
                target.id,
                UserStoreAssignmentRequest(store_id=store_b.id),
                actor=actor,
            )
        assert excinfo.value.status_code == 403

    def test_unknown_target_user_404(
        self, db_session: Session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.assign_user_store(
                db_session,
                uuid.uuid4(),
                UserStoreAssignmentRequest(store_id=None),
                actor=admin,
            )
        assert excinfo.value.status_code == 404


# --------------------------------------------------------------------- #
# F2.15.10 — existence-probe collapse for non-admin callers
# --------------------------------------------------------------------- #
#
# A non-admin caller (owner / manager) must not be able to probe whether
# a user_id exists by observing 404 (unknown) vs 403 (cross-store /
# admin target). The codebase's tenancy convention — see
# require_store_member — collapses both into 403 for non-admin callers.
# These tests lock the same protection on the user-management surface.


class TestNonAdminUnknownUserCollapse:
    """For each lookup-driven service function, a non-admin actor
    receives 403 (not 404) when the user_id does not exist. Admin
    actors continue to see 404 — that distinction is useful for admin
    tooling and not exploitable since admin already has global
    visibility."""

    def _build_owner(self, make_store, make_user):
        store = make_store(code=f"probe-o-{uuid.uuid4().hex[:6]}")
        return make_user(role=UserRole.owner, store_id=store.id)

    def _build_manager(self, make_store, make_user):
        store = make_store(code=f"probe-m-{uuid.uuid4().hex[:6]}")
        return make_user(role=UserRole.manager, store_id=store.id)

    # ---- get_user --------------------------------------------------- #

    def test_owner_unknown_user_returns_403(
        self, db_session: Session, make_store, make_user
    ):
        owner = self._build_owner(make_store, make_user)
        with pytest.raises(HTTPException) as excinfo:
            svc.get_user(db_session, uuid.uuid4(), actor=owner)
        assert excinfo.value.status_code == 403

    def test_manager_unknown_user_returns_403(
        self, db_session: Session, make_store, make_user
    ):
        manager = self._build_manager(make_store, make_user)
        with pytest.raises(HTTPException) as excinfo:
            svc.get_user(db_session, uuid.uuid4(), actor=manager)
        assert excinfo.value.status_code == 403

    # ---- update_user ------------------------------------------------ #

    def test_owner_unknown_user_update_returns_403(
        self, db_session: Session, make_store, make_user
    ):
        owner = self._build_owner(make_store, make_user)
        with pytest.raises(HTTPException) as excinfo:
            svc.update_user(
                db_session,
                uuid.uuid4(),
                UserUpdateRequest(full_name="x"),
                actor=owner,
            )
        assert excinfo.value.status_code == 403

    def test_manager_unknown_user_update_returns_403(
        self, db_session: Session, make_store, make_user
    ):
        manager = self._build_manager(make_store, make_user)
        with pytest.raises(HTTPException) as excinfo:
            svc.update_user(
                db_session,
                uuid.uuid4(),
                UserUpdateRequest(full_name="x"),
                actor=manager,
            )
        assert excinfo.value.status_code == 403

    # ---- deactivate_user ------------------------------------------- #

    def test_owner_unknown_user_deactivate_returns_403(
        self, db_session: Session, make_store, make_user
    ):
        owner = self._build_owner(make_store, make_user)
        with pytest.raises(HTTPException) as excinfo:
            svc.deactivate_user(db_session, uuid.uuid4(), actor=owner)
        assert excinfo.value.status_code == 403

    def test_manager_unknown_user_deactivate_returns_403(
        self, db_session: Session, make_store, make_user
    ):
        manager = self._build_manager(make_store, make_user)
        with pytest.raises(HTTPException) as excinfo:
            svc.deactivate_user(db_session, uuid.uuid4(), actor=manager)
        assert excinfo.value.status_code == 403

    # ---- reactivate_user ------------------------------------------- #

    def test_owner_unknown_user_reactivate_returns_403(
        self, db_session: Session, make_store, make_user
    ):
        owner = self._build_owner(make_store, make_user)
        with pytest.raises(HTTPException) as excinfo:
            svc.reactivate_user(db_session, uuid.uuid4(), actor=owner)
        assert excinfo.value.status_code == 403

    def test_manager_unknown_user_reactivate_returns_403(
        self, db_session: Session, make_store, make_user
    ):
        manager = self._build_manager(make_store, make_user)
        with pytest.raises(HTTPException) as excinfo:
            svc.reactivate_user(db_session, uuid.uuid4(), actor=manager)
        assert excinfo.value.status_code == 403

    # ---- change_user_role ----------------------------------------- #

    def test_owner_unknown_user_change_role_returns_403(
        self, db_session: Session, make_store, make_user
    ):
        owner = self._build_owner(make_store, make_user)
        with pytest.raises(HTTPException) as excinfo:
            svc.change_user_role(
                db_session,
                uuid.uuid4(),
                UserRoleChangeRequest(role=UserRole.staff),
                actor=owner,
            )
        assert excinfo.value.status_code == 403

    def test_manager_unknown_user_change_role_returns_403(
        self, db_session: Session, make_store, make_user
    ):
        manager = self._build_manager(make_store, make_user)
        with pytest.raises(HTTPException) as excinfo:
            svc.change_user_role(
                db_session,
                uuid.uuid4(),
                UserRoleChangeRequest(role=UserRole.staff),
                actor=manager,
            )
        assert excinfo.value.status_code == 403

    # ---- admin still sees 404 (regression on the carve-out) -------- #

    def test_admin_unknown_user_get_returns_404(
        self, db_session: Session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.get_user(db_session, uuid.uuid4(), actor=admin)
        assert excinfo.value.status_code == 404

    def test_admin_unknown_user_update_returns_404(
        self, db_session: Session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.update_user(
                db_session,
                uuid.uuid4(),
                UserUpdateRequest(full_name="x"),
                actor=admin,
            )
        assert excinfo.value.status_code == 404

    def test_admin_unknown_user_deactivate_returns_404(
        self, db_session: Session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.deactivate_user(db_session, uuid.uuid4(), actor=admin)
        assert excinfo.value.status_code == 404

    def test_admin_unknown_user_reactivate_returns_404(
        self, db_session: Session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.reactivate_user(db_session, uuid.uuid4(), actor=admin)
        assert excinfo.value.status_code == 404

    def test_admin_unknown_user_change_role_returns_404(
        self, db_session: Session, make_user
    ):
        admin = make_user(role=UserRole.admin)
        with pytest.raises(HTTPException) as excinfo:
            svc.change_user_role(
                db_session,
                uuid.uuid4(),
                UserRoleChangeRequest(role=UserRole.staff),
                actor=admin,
            )
        assert excinfo.value.status_code == 404
