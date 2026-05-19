import uuid
from typing import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Store
from app.db.models import User
from app.db.models import UserRole
from tests.helpers.auth import auth_headers_for as _auth_headers
from tests.helpers.auth import make_user as central_make_user


# ---------------------------------------------------------------------------
# Fixtures local to this suite
# ---------------------------------------------------------------------------


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "Acme Vape", code: str | None = None) -> Store:
        store = Store(name=name, code=code or f"acme-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


@pytest.fixture
def make_user(db_session: Session) -> Callable[..., User]:
    # Thin adapter over tests.helpers.auth.make_user: keeps this
    # suite's historical positional `role` signature and default
    # password so call sites are untouched, while routing user
    # construction through the single F2.22.2 chokepoint.
    def _create(
        role: UserRole,
        store_id: uuid.UUID | None = None,
        email: str | None = None,
        is_active: bool = True,
    ) -> User:
        return central_make_user(
            db_session,
            role=role,
            store_id=store_id,
            email=email,
            is_active=is_active,
            password="irrelevant-pw-1234",
        )

    return _create


def _create_user_payload(
    role: UserRole,
    store_id: uuid.UUID | None = None,
    email: str | None = None,
) -> dict:
    return {
        "full_name": f"Created {role.value}",
        "email": email or f"new-{uuid.uuid4().hex[:8]}@example.com",
        "password": "supersecret123",
        "role": role.value,
        "store_id": str(store_id) if store_id else None,
    }


# ---------------------------------------------------------------------------
# Public /auth/register is disabled (covers H1 + H2)
# ---------------------------------------------------------------------------


class TestPublicRegisterDisabled:
    def test_register_returns_403_for_anonymous_caller(self, client: TestClient):
        response = client.post(
            "/auth/register",
            json={
                "full_name": "Attacker",
                "email": "attacker@example.com",
                "password": "supersecret123",
                "role": "admin",
            },
        )
        assert response.status_code == 403
        body = response.json()
        assert "disabled" in body["detail"].lower()
        assert "/auth/users" in body["detail"]

    def test_register_does_not_accept_role_field(self, client: TestClient):
        # No matter what payload is sent, register cannot escalate privileges.
        for role in ("admin", "owner", "manager", "staff"):
            resp = client.post(
                "/auth/register",
                json={
                    "full_name": "x",
                    "email": f"{role}@example.com",
                    "password": "supersecret123",
                    "role": role,
                    "store_id": str(uuid.uuid4()),
                },
            )
            assert resp.status_code == 403, role

    def test_register_does_not_accept_arbitrary_store_id(
        self, client: TestClient, make_store
    ):
        # Even with a real store, register never creates the user.
        target_store = make_store()
        resp = client.post(
            "/auth/register",
            json={
                "full_name": "Attacker",
                "email": "attacker@example.com",
                "password": "supersecret123",
                "role": "manager",
                "store_id": str(target_store.id),
            },
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# /auth/users requires authentication
# ---------------------------------------------------------------------------


class TestCreateUserRequiresAuth:
    def test_anonymous_cannot_create_user(self, client: TestClient):
        resp = client.post("/auth/users", json=_create_user_payload(UserRole.staff))
        # S2.2 changed HTTPBearer to auto_error=False so missing credentials
        # return 401 with WWW-Authenticate, not 403.
        assert resp.status_code == 401
        assert resp.headers.get("www-authenticate", "").lower() == "bearer"

    def test_invalid_token_is_rejected(self, client: TestClient):
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(UserRole.staff),
            headers={"Authorization": "Bearer not-a-real-token"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# RBAC matrix
# ---------------------------------------------------------------------------


class TestStaffCannotCreateUsers:
    def test_staff_is_rejected(self, client: TestClient, make_store, make_user):
        store = make_store()
        staff = make_user(UserRole.staff, store_id=store.id)
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(UserRole.staff, store_id=store.id),
            headers=_auth_headers(staff),
        )
        assert resp.status_code == 403


class TestManagerCanOnlyCreateStaff:
    def test_manager_creates_staff_in_own_store(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        manager = make_user(UserRole.manager, store_id=store.id)
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(UserRole.staff, store_id=store.id),
            headers=_auth_headers(manager),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["role"] == "staff"
        assert body["store_id"] == str(store.id)
        assert "password_hash" not in body
        assert "password" not in body

    def test_manager_cannot_create_manager(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        manager = make_user(UserRole.manager, store_id=store.id)
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(UserRole.manager, store_id=store.id),
            headers=_auth_headers(manager),
        )
        assert resp.status_code == 403

    def test_manager_cannot_create_owner(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        manager = make_user(UserRole.manager, store_id=store.id)
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(UserRole.owner, store_id=store.id),
            headers=_auth_headers(manager),
        )
        assert resp.status_code == 403

    def test_manager_cannot_create_admin(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        manager = make_user(UserRole.manager, store_id=store.id)
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(UserRole.admin),
            headers=_auth_headers(manager),
        )
        assert resp.status_code == 403


class TestOwnerCanCreateManagerAndStaffInOwnStore:
    def test_owner_creates_manager_in_own_store(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(UserRole.manager, store_id=store.id),
            headers=_auth_headers(owner),
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "manager"

    def test_owner_creates_staff_in_own_store(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(UserRole.staff, store_id=store.id),
            headers=_auth_headers(owner),
        )
        assert resp.status_code == 201

    def test_owner_cannot_create_owner(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(UserRole.owner, store_id=store.id),
            headers=_auth_headers(owner),
        )
        assert resp.status_code == 403

    def test_owner_cannot_create_admin(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        owner = make_user(UserRole.owner, store_id=store.id)
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(UserRole.admin),
            headers=_auth_headers(owner),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Cross-store enforcement
# ---------------------------------------------------------------------------


class TestCrossStoreInjection:
    def test_owner_cannot_create_user_in_another_store(
        self, client: TestClient, make_store, make_user
    ):
        own_store = make_store(code="own-store")
        other_store = make_store(code="other-store")
        owner = make_user(UserRole.owner, store_id=own_store.id)
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(UserRole.staff, store_id=other_store.id),
            headers=_auth_headers(owner),
        )
        assert resp.status_code == 403

    def test_manager_cannot_create_user_in_another_store(
        self, client: TestClient, make_store, make_user
    ):
        own_store = make_store(code="own-store-m")
        other_store = make_store(code="other-store-m")
        manager = make_user(UserRole.manager, store_id=own_store.id)
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(UserRole.staff, store_id=other_store.id),
            headers=_auth_headers(manager),
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Admin rules
# ---------------------------------------------------------------------------


class TestAdminCanCreateScopedUsers:
    @pytest.mark.parametrize(
        "target_role",
        [UserRole.owner, UserRole.manager, UserRole.staff],
    )
    def test_admin_creates_role_with_store(
        self, client: TestClient, make_store, make_user, target_role: UserRole
    ):
        store = make_store(code=f"admin-store-{target_role.value}")
        admin = make_user(UserRole.admin, store_id=None)
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(target_role, store_id=store.id),
            headers=_auth_headers(admin),
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["role"] == target_role.value
        assert body["store_id"] == str(store.id)
        assert "password_hash" not in body

    @pytest.mark.parametrize(
        "target_role",
        [UserRole.owner, UserRole.manager, UserRole.staff],
    )
    def test_admin_cannot_create_role_without_store(
        self, client: TestClient, make_user, target_role: UserRole
    ):
        admin = make_user(UserRole.admin, store_id=None)
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(target_role, store_id=None),
            headers=_auth_headers(admin),
        )
        assert resp.status_code == 400
        assert "store" in resp.json()["detail"].lower()


class TestAdminTargetRules:
    def test_admin_cannot_create_admin_in_mvp(
        self, client: TestClient, make_store, make_user
    ):
        # MVP policy: no role can create admin via the API. The route's RBAC
        # check (matrix in core/permissions.py) rejects this before any
        # store_id rule is evaluated, so the response is 403, not 400.
        store = make_store(code="admin-target")
        admin = make_user(UserRole.admin, store_id=None)
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(UserRole.admin, store_id=store.id),
            headers=_auth_headers(admin),
        )
        assert resp.status_code == 403


class TestStoreIdResolverRules:
    """Direct unit tests for resolve_target_store_id.

    These cover guarantees the route doesn't currently exercise (e.g. the
    admin-cannot-have-store-id rule) so the helper stays correct even if the
    creation matrix is widened in a future session.
    """

    def test_admin_target_with_store_id_is_rejected(self):
        from app.core.permissions import resolve_target_store_id

        actor = User(
            full_name="root",
            email="root@example.com",
            password_hash="x",
            role=UserRole.admin,
            store_id=None,
        )
        with pytest.raises(Exception) as excinfo:
            resolve_target_store_id(
                caller=actor,
                target_role=UserRole.admin,
                requested_store_id=uuid.uuid4(),
            )
        assert excinfo.value.status_code == 400  # type: ignore[attr-defined]
        assert "store" in excinfo.value.detail.lower()  # type: ignore[attr-defined]

    def test_admin_target_with_null_store_id_is_accepted(self):
        from app.core.permissions import resolve_target_store_id

        actor = User(
            full_name="root",
            email="root2@example.com",
            password_hash="x",
            role=UserRole.admin,
            store_id=None,
        )
        result = resolve_target_store_id(
            caller=actor, target_role=UserRole.admin, requested_store_id=None
        )
        assert result is None

    def test_admin_creating_store_user_requires_store_id(self):
        from app.core.permissions import resolve_target_store_id

        actor = User(
            full_name="root",
            email="root3@example.com",
            password_hash="x",
            role=UserRole.admin,
            store_id=None,
        )
        with pytest.raises(Exception) as excinfo:
            resolve_target_store_id(
                caller=actor,
                target_role=UserRole.staff,
                requested_store_id=None,
            )
        assert excinfo.value.status_code == 400  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# Email uniqueness
# ---------------------------------------------------------------------------


class TestDuplicateEmail:
    def test_duplicate_email_returns_409(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        admin = make_user(UserRole.admin, store_id=None)
        existing = make_user(
            UserRole.staff, store_id=store.id, email="taken@example.com"
        )
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(
                UserRole.staff, store_id=store.id, email=existing.email
            ),
            headers=_auth_headers(admin),
        )
        assert resp.status_code == 409
        assert "already" in resp.json()["detail"].lower()

    def test_duplicate_email_is_case_insensitive(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        admin = make_user(UserRole.admin, store_id=None)
        make_user(UserRole.staff, store_id=store.id, email="case@example.com")
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(
                UserRole.staff, store_id=store.id, email="CASE@example.com"
            ),
            headers=_auth_headers(admin),
        )
        assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


class TestResponseShape:
    def test_response_does_not_leak_password_hash(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        admin = make_user(UserRole.admin, store_id=None)
        resp = client.post(
            "/auth/users",
            json=_create_user_payload(UserRole.staff, store_id=store.id),
            headers=_auth_headers(admin),
        )
        assert resp.status_code == 201
        body = resp.json()
        assert "password_hash" not in body
        assert "password" not in body
        assert set(body.keys()) == {
            "id",
            "full_name",
            "email",
            "role",
            "store_id",
            "is_active",
        }

    def test_payload_short_password_is_rejected(
        self, client: TestClient, make_store, make_user
    ):
        store = make_store()
        admin = make_user(UserRole.admin, store_id=None)
        payload = _create_user_payload(UserRole.staff, store_id=store.id)
        payload["password"] = "short"
        resp = client.post(
            "/auth/users", json=payload, headers=_auth_headers(admin)
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# F2.22.2.E — Supabase Admin API atomic creation
# ---------------------------------------------------------------------------


class TestSupabaseAdminAtomicCreation:
    """POST /auth/users creates auth.users (Supabase) + public.users atomically.

    The Supabase Admin wrapper is faked offline by the autouse
    `supabase_admin_fake` fixture (tests/conftest.py).
    """

    def test_create_user_calls_supabase_admin(
        self, client: TestClient, make_store, make_user, supabase_admin_fake
    ):
        store = make_store()
        admin = make_user(UserRole.admin, store_id=None)
        payload = _create_user_payload(
            UserRole.staff, store_id=store.id, email="New-Person@Example.com"
        )
        resp = client.post(
            "/auth/users", json=payload, headers=_auth_headers(admin)
        )
        assert resp.status_code == 201, resp.text
        # Exactly one Supabase auth.users record was created, with the
        # normalized (lowercased) email.
        assert len(supabase_admin_fake.created) == 1
        assert supabase_admin_fake.created[0]["email"] == "new-person@example.com"
        assert supabase_admin_fake.deleted == []

    def test_created_row_has_auth_user_id_from_supabase(
        self,
        client: TestClient,
        db_session: Session,
        make_store,
        make_user,
        supabase_admin_fake,
    ):
        store = make_store()
        admin = make_user(UserRole.admin, store_id=None)
        pinned_id = uuid.uuid4()
        supabase_admin_fake.next_auth_user_id = pinned_id
        payload = _create_user_payload(UserRole.staff, store_id=store.id)
        resp = client.post(
            "/auth/users", json=payload, headers=_auth_headers(admin)
        )
        assert resp.status_code == 201, resp.text
        created = db_session.scalar(
            select(User).where(User.email == payload["email"].lower())
        )
        assert created is not None
        # public.users.auth_user_id == the UUID Supabase returned.
        assert created.auth_user_id == pinned_id

    def test_created_row_preserves_role_store_and_profile(
        self,
        client: TestClient,
        db_session: Session,
        make_store,
        make_user,
        supabase_admin_fake,
    ):
        store = make_store()
        admin = make_user(UserRole.admin, store_id=None)
        payload = _create_user_payload(UserRole.manager, store_id=store.id)
        payload["full_name"] = "Persisted Manager"
        resp = client.post(
            "/auth/users", json=payload, headers=_auth_headers(admin)
        )
        assert resp.status_code == 201, resp.text
        created = db_session.scalar(
            select(User).where(User.email == payload["email"].lower())
        )
        assert created is not None
        assert created.role == UserRole.manager
        assert created.store_id == store.id
        assert created.is_active is True
        assert created.full_name == "Persisted Manager"

    def test_supabase_metadata_is_informational_only(
        self, client: TestClient, make_store, make_user, supabase_admin_fake
    ):
        # The metadata sent to Supabase carries role/store for human
        # context, but it is NOT authority — public.users is. (The
        # verifier in app.core.supabase_auth discards all claims but sub.)
        store = make_store()
        admin = make_user(UserRole.admin, store_id=None)
        payload = _create_user_payload(UserRole.staff, store_id=store.id)
        resp = client.post(
            "/auth/users", json=payload, headers=_auth_headers(admin)
        )
        assert resp.status_code == 201, resp.text
        metadata = supabase_admin_fake.created[0]["user_metadata"]
        assert metadata["nuberush_role"] == "staff"
        assert metadata["nuberush_store_id"] == str(store.id)
        assert metadata["full_name"] == payload["full_name"]

    def test_supabase_create_failure_inserts_no_public_user(
        self,
        client: TestClient,
        db_session: Session,
        make_store,
        make_user,
        supabase_admin_fake,
    ):
        store = make_store()
        admin = make_user(UserRole.admin, store_id=None)
        supabase_admin_fake.create_should_fail = True
        payload = _create_user_payload(UserRole.staff, store_id=store.id)
        resp = client.post(
            "/auth/users", json=payload, headers=_auth_headers(admin)
        )
        assert resp.status_code == 502
        # No public.users row, no orphan cleanup needed.
        assert (
            db_session.scalar(
                select(User).where(User.email == payload["email"].lower())
            )
            is None
        )
        assert supabase_admin_fake.created == []
        assert supabase_admin_fake.deleted == []

    def test_db_failure_after_supabase_create_triggers_cleanup(
        self,
        client: TestClient,
        db_session: Session,
        make_store,
        make_user,
        supabase_admin_fake,
    ):
        # Pin the Supabase-returned id to an auth_user_id already in use,
        # so the public.users insert hits the unique index and fails
        # AFTER the auth.users record was created.
        store = make_store()
        admin = make_user(UserRole.admin, store_id=None)
        collision_id = uuid.uuid4()
        central_make_user(
            db_session,
            role=UserRole.staff,
            store_id=store.id,
            auth_user_id=collision_id,
        )
        supabase_admin_fake.next_auth_user_id = collision_id
        payload = _create_user_payload(UserRole.staff, store_id=store.id)
        resp = client.post(
            "/auth/users", json=payload, headers=_auth_headers(admin)
        )
        assert resp.status_code == 500
        # The orphaned Supabase auth user was deleted (rollback).
        assert supabase_admin_fake.deleted == [collision_id]
        # No public.users row for the failed create.
        assert (
            db_session.scalar(
                select(User).where(User.email == payload["email"].lower())
            )
            is None
        )

    def test_cleanup_failure_is_controlled_and_leaks_no_secret(
        self,
        client: TestClient,
        db_session: Session,
        make_store,
        make_user,
        supabase_admin_fake,
    ):
        # DB insert fails after Supabase create AND the cleanup delete
        # also fails: the endpoint must still return a controlled 500
        # with a generic, secret-free message — not crash.
        store = make_store()
        admin = make_user(UserRole.admin, store_id=None)
        collision_id = uuid.uuid4()
        central_make_user(
            db_session,
            role=UserRole.staff,
            store_id=store.id,
            auth_user_id=collision_id,
        )
        supabase_admin_fake.next_auth_user_id = collision_id
        supabase_admin_fake.delete_should_fail = True
        payload = _create_user_payload(UserRole.staff, store_id=store.id)
        resp = client.post(
            "/auth/users", json=payload, headers=_auth_headers(admin)
        )
        # Still a controlled 500 — the cleanup failure is swallowed/logged.
        assert resp.status_code == 500
        # The cleanup delete was attempted (even though it failed).
        assert supabase_admin_fake.deleted == [collision_id]
        # Generic message: no service-role key, no provider internals.
        detail = resp.json()["detail"]
        assert detail == "Failed to persist the new user."
        assert "key" not in detail.lower()
        assert "supabase" not in detail.lower()
