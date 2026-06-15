"""Dr.1.1.D — GET /driver/eligibility API tests.

Confirms the eligible path, every reachable blocker code, the 401/403
boundaries (including that an inactive user is blocked upstream with 403,
never reaching the eligibility computation), the response/blocker shapes,
and the full /driver runtime route surface.
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


_URL = "/driver/eligibility"

_TOP_LEVEL_KEYS = {
    "can_go_online",
    "blockers",
    "driver_status",
    "driver_approval_status",
    "user_active",
    "store_active",
    "evaluated_at",
}

_BLOCKER_KEYS = {"code", "message", "source", "severity"}


@pytest.fixture
def make_store(db_session: Session) -> Callable[..., Store]:
    def _create(name: str = "DPE-Api", is_active: bool = True) -> Store:
        store = Store(
            name=name,
            code=f"dpea-{uuid.uuid4().hex[:8]}",
            is_active=is_active,
        )
        db_session.add(store)
        db_session.commit()
        db_session.refresh(store)
        return store

    return _create


def _driver(
    db_session: Session, store: Store, is_active: bool = True
) -> User:
    return central_make_user(
        db_session,
        role=UserRole.driver,
        store_id=store.id,
        is_active=is_active,
    )


def _codes(body: dict) -> set[str]:
    return {b["code"] for b in body["blockers"]}


def test_eligible_driver_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(
        db_session,
        user=user,
        store=store,
        status="active",
        approval_status="approved",
    )

    resp = client.get(_URL, headers=_auth(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["can_go_online"] is True
    assert body["blockers"] == []
    assert set(body.keys()) == _TOP_LEVEL_KEYS


def test_missing_profile_200_false(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)

    resp = client.get(_URL, headers=_auth(user))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["can_go_online"] is False
    assert "driver_profile_missing" in _codes(body)


def test_inactive_profile_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(
        db_session,
        user=user,
        store=store,
        status="inactive",
        approval_status="approved",
    )

    body = client.get(_URL, headers=_auth(user)).json()
    assert "driver_profile_inactive" in _codes(body)


def test_approval_pending_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(
        db_session,
        user=user,
        store=store,
        status="active",
        approval_status="pending",
    )

    body = client.get(_URL, headers=_auth(user)).json()
    assert "driver_approval_pending" in _codes(body)


def test_approval_rejected_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(
        db_session,
        user=user,
        store=store,
        status="active",
        approval_status="rejected",
    )

    body = client.get(_URL, headers=_auth(user)).json()
    assert "driver_approval_rejected" in _codes(body)


def test_inactive_store_200(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store(is_active=False)
    user = _driver(db_session, store)
    make_driver_profile(
        db_session,
        user=user,
        store=store,
        status="active",
        approval_status="approved",
    )

    body = client.get(_URL, headers=_auth(user)).json()
    assert "store_inactive" in _codes(body)
    assert body["store_active"] is False


def test_driver_without_store_403(
    client: TestClient, db_session: Session
) -> None:
    user = central_make_user(
        db_session, role=UserRole.driver, store_id=None
    )
    resp = client.get(_URL, headers=_auth(user))
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
    resp = client.get(_URL, headers=_auth(user))
    assert resp.status_code == 403, resp.text


def test_anonymous_401(client: TestClient) -> None:
    assert client.get(_URL).status_code == 401


def test_inactive_user_blocked_upstream_403(
    client: TestClient, db_session: Session, make_store
) -> None:
    # get_current_user rejects inactive users with 403 before the endpoint
    # runs, so the user_inactive blocker is never observable via the API.
    store = make_store()
    user = _driver(db_session, store, is_active=False)
    make_driver_profile(
        db_session,
        user=user,
        store=store,
        status="active",
        approval_status="approved",
    )

    resp = client.get(_URL, headers=_auth(user))
    assert resp.status_code == 403, resp.text


def test_response_and_blocker_shape(
    client: TestClient, db_session: Session, make_store
) -> None:
    store = make_store()
    user = _driver(db_session, store)
    make_driver_profile(
        db_session,
        user=user,
        store=store,
        status="active",
        approval_status="pending",
    )

    body = client.get(_URL, headers=_auth(user)).json()
    assert set(body.keys()) == _TOP_LEVEL_KEYS
    assert body["blockers"], "expected at least one blocker"
    for blocker in body["blockers"]:
        assert set(blocker.keys()) == _BLOCKER_KEYS
        assert blocker["severity"] == "blocker"
        assert blocker["source"] in {"user", "store", "driver_profile"}


def test_driver_runtime_route_surface() -> None:
    """The /driver runtime routes are the five self-scoped reads plus the
    accept/decline (Dr.1.1.I) and start (Dr.1.1.J) mutations — nothing else.
    The only write methods are POST on .../accept, .../decline and .../start;
    no PATCH/PUT/DELETE anywhere."""
    from app.main import app

    driver_routes = {
        (route.path, frozenset(route.methods))
        for route in app.router.routes
        if getattr(route, "path", "").startswith("/driver")
    }
    paths = {path for path, _ in driver_routes}
    assert paths == {
        "/driver/me",
        "/driver/eligibility",
        "/driver/assignments",
        "/driver/assignments/{assignment_id}",
        "/driver/assignments/{assignment_id}/delivery-state",
        "/driver/assignments/{assignment_id}/accept",
        "/driver/assignments/{assignment_id}/decline",
        "/driver/assignments/{assignment_id}/start",
    }

    _action_paths = {
        "/driver/assignments/{assignment_id}/accept",
        "/driver/assignments/{assignment_id}/decline",
        "/driver/assignments/{assignment_id}/start",
    }
    for path, methods in driver_routes:
        # PATCH/PUT/DELETE never appear on the /driver surface.
        assert "PATCH" not in methods
        assert "DELETE" not in methods
        assert "PUT" not in methods
        if path in _action_paths:
            assert "POST" in methods
            assert "GET" not in methods
        else:
            # Read-only surface: GET (plus HEAD/OPTIONS that FastAPI adds).
            assert "GET" in methods
            assert "POST" not in methods
