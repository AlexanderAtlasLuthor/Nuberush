"""Dr.1.1.C — GET /driver/me API tests.

Confirms the single driver runtime endpoint: the success shape (and that it
leaks nothing), every 403/404 boundary, the non-blocking states, and that no
other /driver/* runtime route exists.
"""

from __future__ import annotations

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
from tests.helpers.driver import make_driver_profile


_ME_URL = "/driver/me"

_ALLOWED_KEYS = {
    "id",
    "user_id",
    "store_id",
    "status",
    "approval_status",
    "created_at",
    "updated_at",
    "activated_at",
    "deactivated_at",
    "approved_at",
}


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "DP-Api") -> Store:
        store = Store(name=name, code=f"dpa-{uuid.uuid4().hex[:8]}")
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


def _driver(db_session: Session, store: Store) -> User:
    return central_make_user(
        db_session, role=UserRole.driver, store_id=store.id
    )


def test_driver_with_profile_200_and_exact_shape(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    profile = make_driver_profile(db_session, user=user, store=store)

    resp = client.get(_ME_URL, headers=_auth(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert set(body.keys()) == _ALLOWED_KEYS
    assert body["id"] == str(profile.id)
    assert body["user_id"] == str(user.id)
    assert body["store_id"] == str(store.id)
    assert body["status"] == "active"
    assert body["approval_status"] == "approved"


def test_response_omits_forbidden_fields(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(db_session, user=user, store=store)

    body = client.get(_ME_URL, headers=_auth(user)).json()
    for forbidden in (
        "email",
        "role",
        "documents",
        "vehicle",
        "background_check",
        "payout",
        "earnings",
        "assignments",
        "orders",
        "customer",
        "audit",
        "compliance",
        "notes",
        "metadata",
    ):
        assert forbidden not in body


def test_driver_without_profile_404(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)

    resp = client.get(_ME_URL, headers=_auth(user))
    assert resp.status_code == 404, resp.text


def test_driver_without_store_403(
    client: TestClient, db_session: Session
) -> None:
    user = central_make_user(
        db_session, role=UserRole.driver, store_id=None
    )
    resp = client.get(_ME_URL, headers=_auth(user))
    assert resp.status_code == 403, resp.text


@pytest.mark.parametrize(
    "role",
    [UserRole.staff, UserRole.manager, UserRole.owner, UserRole.admin],
)
def test_non_driver_403(
    client: TestClient, db_session: Session, make_store, role: UserRole
) -> None:
    store_id = None if role == UserRole.admin else make_store().id
    user = central_make_user(db_session, role=role, store_id=store_id)
    resp = client.get(_ME_URL, headers=_auth(user))
    assert resp.status_code == 403, resp.text


def test_store_mismatch_403(
    client: TestClient, db_session: Session, make_store
) -> None:
    profile_store = make_store("profile-store")
    user = _driver(db_session, profile_store)
    make_driver_profile(db_session, user=user, store=profile_store)

    other_store = make_store("other-store")
    user.store_id = other_store.id
    db_session.commit()

    resp = client.get(_ME_URL, headers=_auth(user))
    assert resp.status_code == 403, resp.text


@pytest.mark.parametrize(
    ("status_value", "approval_value"),
    [
        ("inactive", "approved"),
        ("active", "pending"),
        ("active", "rejected"),
    ],
)
def test_non_blocking_states_return_200(
    client: TestClient,
    db_session: Session,
    make_store,
    status_value,
    approval_value,
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(
        db_session,
        user=user,
        store=store,
        status=status_value,
        approval_status=approval_value,
    )

    resp = client.get(_ME_URL, headers=_auth(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == status_value
    assert body["approval_status"] == approval_value


def test_anonymous_401(client: TestClient) -> None:
    assert client.get(_ME_URL).status_code == 401


def test_no_other_driver_routes_exist() -> None:
    """The driver runtime routes are GET /driver/me (Dr.1.1.C),
    GET /driver/eligibility (Dr.1.1.D), the two assignment reads (Dr.1.1.F),
    the delivery-state read (Dr.1.1.H), the accept/decline mutations
    (Dr.1.1.I), the start mutation (Dr.1.1.J), the arrive-store mutation
    (Dr.1.1.K), the pickup mutation (Dr.1.1.L), the depart-to-customer
    mutation (Dr.1.1.M), and the arrive-customer mutation (Dr.1.1.N) —
    nothing else."""
    from app.main import app

    driver_paths = {
        route.path
        for route in app.router.routes
        if getattr(route, "path", "").startswith("/driver")
    }
    assert driver_paths == {
        "/driver/me",
        "/driver/eligibility",
        "/driver/assignments",
        "/driver/assignments/{assignment_id}",
        "/driver/assignments/{assignment_id}/delivery-state",
        "/driver/assignments/{assignment_id}/accept",
        "/driver/assignments/{assignment_id}/decline",
        "/driver/assignments/{assignment_id}/start",
        "/driver/assignments/{assignment_id}/arrive-store",
        "/driver/assignments/{assignment_id}/pickup",
        "/driver/assignments/{assignment_id}/depart-to-customer",
        "/driver/assignments/{assignment_id}/arrive-customer",
        "/driver/assignments/{assignment_id}/verify-age",
        "/driver/assignments/{assignment_id}/proof",
        "/driver/assignments/{assignment_id}/complete",
    }
